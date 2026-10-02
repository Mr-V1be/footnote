from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import httpx

from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.infrastructure.ai.http import HttpPolicy, ensure_json_object, post_json
from snoska.ports.ai import AiProviderError, Completion, CompletionRequest

SCHEMA_INSTRUCTION = "Отвечай только JSON-объектом, соответствующим JSON-схеме:"


class OllamaEmbedder:
    """Embeddings from a local Ollama server (``/api/embed``)."""

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
            self._client,
            "/api/embed",
            {"model": self.model, "input": list(texts), "truncate": True},
            self._policy,
        )
        embeddings = body.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise AiProviderError("unexpected embedding response")
        return [[float(value) for value in vector] for vector in embeddings]


class OllamaLanguageModel:
    """Chat completions from Ollama.

    Structured answers use Ollama's JSON mode with the schema stated in a
    system message. Schema-constrained decoding (``format`` set to a schema) is
    not honoured by the server for thinking models when thinking is disabled,
    so the adapter relies on JSON mode and checks the answer is a JSON object.
    """

    def __init__(self, client: httpx.AsyncClient, model: str, policy: HttpPolicy) -> None:
        self._client = client
        self.model = model
        self._policy = policy

    async def complete(self, request: CompletionRequest) -> Completion:
        messages = [{"role": m.role.value, "content": m.content} for m in request.messages]
        payload: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            # Reasoning traces are not used; answers must come straight back.
            "think": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
                **request.options,
            },
        }
        if request.response_schema is not None:
            schema = json.dumps(request.response_schema, ensure_ascii=False)
            messages.insert(0, {"role": "system", "content": f"{SCHEMA_INSTRUCTION}\n{schema}"})
            payload["format"] = "json"
        payload["messages"] = messages
        body = await post_json(self._client, "/api/chat", payload, self._policy)
        message = body.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise AiProviderError("unexpected chat response")
        text = message["content"]
        if request.response_schema is not None:
            ensure_json_object(text)
        return Completion(
            text=text,
            model=str(body.get("model", self.model)),
            prompt_tokens=body.get("prompt_eval_count"),
            completion_tokens=body.get("eval_count"),
        )
