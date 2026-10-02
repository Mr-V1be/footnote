from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.infrastructure.ai.http import HttpPolicy, ensure_json_object, post_json
from snoska.ports.ai import AiProviderError, Completion, CompletionRequest

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


class OpenAiCompatibleLanguageModel:
    """Chat completions from any server implementing ``POST /chat/completions``."""

    def __init__(self, client: httpx.AsyncClient, model: str, policy: HttpPolicy) -> None:
        self._client = client
        self.model = model
        self._policy = policy

    async def complete(self, request: CompletionRequest) -> Completion:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
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
        body = await post_json(self._client, "chat/completions", payload, self._policy)
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AiProviderError("unexpected chat response")
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str):
            raise AiProviderError("chat response has no content")
        if request.response_schema is not None:
            ensure_json_object(content)
        usage = body.get("usage") or {}
        return Completion(
            text=content,
            model=str(body.get("model", self.model)),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
