"""Answers of the model kept by the request that produced them."""

from __future__ import annotations

import hashlib
import json

from snoska.ports.ai import Completion, CompletionCache, CompletionRequest, LanguageModel


def request_key(chain: tuple[str, ...], request: CompletionRequest) -> str:
    """Everything the answer depends on: the models, the messages (document
    text, checks with their wording, the prompt) and the answer's form."""
    material = {
        "models": list(chain),
        "messages": [[m.role.value, m.content] for m in request.messages],
        "schema": request.response_schema,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "options": dict(request.options),
    }
    encoded = json.dumps(material, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


class CachingLanguageModel:
    """A language model that answers a repeated request from its cache: a
    document checked again, unchanged, costs no request at all."""

    def __init__(
        self, inner: LanguageModel, cache: CompletionCache, chain: tuple[str, ...]
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._chain = chain
        self.model = inner.model

    async def complete(self, request: CompletionRequest) -> Completion:
        key = request_key(self._chain, request)
        cached = await self._cache.get(key)
        if cached is not None:
            return cached
        completion = await self._inner.complete(request)
        await self._cache.put(key, completion)
        return completion
