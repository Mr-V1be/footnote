from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from footnote.ports.ai import AiProviderError, ModelOutputError

log = structlog.get_logger(__name__)

_RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class HttpPolicy:
    connect_timeout: float = 5.0
    read_timeout: float = 120.0
    attempts: int = 3
    backoff_seconds: float = 1.0

    def timeout(self) -> httpx.Timeout:
        return httpx.Timeout(self.read_timeout, connect=self.connect_timeout)


# Recognises a failure that repeating the same request cannot fix.
FailureClassifier = Callable[[httpx.Response], AiProviderError | None]


async def post_json(
    client: httpx.AsyncClient,
    path: str,
    payload: Mapping[str, Any],
    policy: HttpPolicy,
    classify: FailureClassifier | None = None,
) -> dict[str, Any]:
    """POST with retries on transport errors and transient statuses.

    Model calls are pure functions of their input, so repeating them is safe.
    ``classify`` lets an adapter name failures that a retry would only repeat.
    """
    last_error: Exception | None = None
    for attempt in range(1, policy.attempts + 1):
        try:
            response = await client.post(path, json=payload)
            permanent = classify(response) if classify is not None and response.is_error else None
            if permanent is not None:
                raise permanent
            if response.status_code in _RETRYABLE_STATUS:
                raise httpx.HTTPStatusError(
                    f"transient status {response.status_code}",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise AiProviderError("provider returned a non-object response")
            return body
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            if status is not None and status not in _RETRYABLE_STATUS:
                raise AiProviderError(f"provider rejected the request: {status}") from exc
            last_error = exc
            log.warning("ai.request_retry", path=path, attempt=attempt, error=repr(exc))
            if attempt < policy.attempts:
                await asyncio.sleep(policy.backoff_seconds * 2 ** (attempt - 1))
    raise AiProviderError(f"provider unavailable: {last_error!r}") from last_error


def json_object_text(text: str) -> str:
    """The JSON object of a structured answer. Some models wrap it in a code
    fence or a sentence despite the requested format; the object inside is
    the answer. Anything without one is a provider fault."""
    stripped = text.strip()
    candidates = [stripped]
    start, end = stripped.find("{"), stripped.rfind("}")
    if 0 <= start < end:
        candidates.append(stripped[start : end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return candidate
    raise ModelOutputError("model answer is not a JSON object")
