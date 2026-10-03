from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.infrastructure.ai.budget import UnlimitedBudget
from snoska.infrastructure.ai.http import HttpPolicy, json_object_text, post_json
from snoska.ports.ai import (
    AiProviderError,
    Completion,
    CompletionRequest,
    ModelBudgetExhaustedError,
    ModelOutputError,
    RequestBudget,
)

log = structlog.get_logger(__name__)

SCHEMA_NAME = "answer"


class OpenAiCompatibleEmbedder:
    """Embeddings from any server implementing ``POST /embeddings``."""

    def __init__(
        self, client: httpx.AsyncClient, model: str, space: EmbeddingSpace, policy: HttpPolicy
    ) -> None:
        self._client = client
        self.model = model
        self.space = space
        self._policy = policy

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        body = await post_json(
            self._client, "embeddings", {"model": self.model, "input": list(texts)}, self._policy
        )
        data = body.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise AiProviderError("unexpected embedding response")
        ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
        return [[float(value) for value in item["embedding"]] for item in ordered]


# A model of the chain cannot serve the request (unknown model, no structured
# output): the next one may.
_UNSERVED_STATUS = frozenset({400, 404, 422})
_TRANSIENT_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
_MAX_RETRY_AFTER_SECONDS = 30.0
# How free tiers say the account's daily allowance is spent (a 429 like the
# transient ones, but no other model of the tier will answer either).
_DAILY_LIMIT_MARKERS = ("per-day", "per day", "free-models-per-day")
_NOT_JSON = "not a JSON object"


class OpenAiCompatibleLanguageModel:
    """Chat completions from any server implementing ``POST /chat/completions``.

    Requests go to the first model of a chain; a model that is rate-limited
    or overloaded is retried with a growing pause, then the next model of
    the chain answers. Every request is first taken from the budget, so the
    installation keeps to the provider's pace and daily allowance; one the
    provider refused as busy or unserved is given back, as it does not count.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        model: str,
        policy: HttpPolicy,
        *,
        fallbacks: Sequence[str] = (),
        budget: RequestBudget | None = None,
        extra_body: Mapping[str, Any] | None = None,
    ) -> None:
        self._client = client
        self.model = model
        self.chain = (model, *(item for item in fallbacks if item and item != model))
        self._policy = policy
        self._budget = budget or UnlimitedBudget()
        # Provider-specific request fields (e.g. how much a reasoning model thinks).
        self._extra = dict(extra_body or {})

    def _payload(self, model: str, request: CompletionRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            **self._extra,
            **request.options,
        }
        if request.response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": SCHEMA_NAME,
                    "schema": dict(request.response_schema),
                    "strict": True,
                },
            }
        return payload

    async def complete(self, request: CompletionRequest) -> Completion:
        last: str = "no attempt"
        for model in self.chain:
            for attempt in range(1, self._policy.attempts + 1):
                await self._budget.spend()
                try:
                    response = await self._client.post(
                        "chat/completions", json=self._payload(model, request)
                    )
                except httpx.TransportError as exc:
                    last = f"{model}: {exc!r}"
                    await self._pause(attempt, None)
                    continue
                if response.status_code in _TRANSIENT_STATUS:
                    if response.status_code == 429 and _daily_limit(response):
                        raise ModelBudgetExhaustedError("the provider's daily allowance is spent")
                    last = f"{model}: {response.status_code}"
                    log.warning("ai.model_busy", model=model, status=response.status_code)
                    if response.status_code == 429:
                        await self._budget.refund()
                    await self._pause(attempt, response)
                    continue
                if response.status_code in _UNSERVED_STATUS:
                    last = f"{model}: {response.status_code}"
                    log.warning("ai.model_unserved", model=model, status=response.status_code)
                    await self._budget.refund()
                    break
                if response.is_error:
                    raise AiProviderError(f"provider rejected the request: {response.status_code}")
                reply = _reply(response, model, request)
                if isinstance(reply, Completion):
                    return reply
                last = f"{model}: {reply.reason}"
                if not reply.transient:
                    # The same request gets the same failure from this model.
                    break
                await self._pause(attempt, None)
            log.warning("ai.model_fallback", model=model, reason=last)
        if last.endswith(_NOT_JSON):
            # The models answered, just not in the requested form: the caller
            # may ask again with a correction.
            raise ModelOutputError(f"no answer in the requested form ({last})")
        raise AiProviderError(f"no model of the chain answered ({last})")

    async def _pause(self, attempt: int, response: httpx.Response | None) -> None:
        if attempt >= self._policy.attempts:
            return
        after = response.headers.get("retry-after") if response is not None else None
        try:
            wait = min(float(after), _MAX_RETRY_AFTER_SECONDS) if after else None
        except ValueError:
            wait = None
        await asyncio.sleep(wait or self._policy.backoff_seconds * 2 ** (attempt - 1))


def _daily_limit(response: httpx.Response) -> bool:
    text = response.text.lower()
    return any(marker in text for marker in _DAILY_LIMIT_MARKERS)


@dataclass(frozen=True, slots=True)
class _NoAnswer:
    reason: str
    # An overloaded upstream may answer next time; a cut or malformed answer
    # to the same request will not.
    transient: bool


def _reply(
    response: httpx.Response, model: str, request: CompletionRequest
) -> Completion | _NoAnswer:
    """The answer of a successful response, or why there is none (some
    providers answer 200 with an error inside)."""
    body = response.json()
    if not isinstance(body, dict) or body.get("error"):
        error = body.get("error") if isinstance(body, dict) else None
        log.warning("ai.empty_answer", model=model, error=str(error)[:300])
        return _NoAnswer("error in the answer", transient=True)
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        log.warning("ai.empty_answer", model=model, error="no choices")
        return _NoAnswer("no choices", transient=True)
    choice = choices[0]
    content = choice.get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        finish = choice.get("finish_reason")
        log.warning("ai.empty_answer", model=model, finish=finish)
        return _NoAnswer(f"empty answer ({finish})", transient=finish != "length")
    if request.response_schema is not None:
        try:
            content = json_object_text(content)
        except ModelOutputError:
            log.warning("ai.not_json", model=model, finish=choice.get("finish_reason"))
            return _NoAnswer(_NOT_JSON, transient=False)
    usage = body.get("usage") or {}
    return Completion(
        text=content,
        model=str(body.get("model", model)),
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
    )
