from __future__ import annotations

import json

import httpx
import pytest
import respx

from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.infrastructure.ai.http import HttpPolicy
from snoska.infrastructure.ai.ollama import OllamaEmbedder, OllamaLanguageModel
from snoska.infrastructure.ai.openai_compatible import (
    OpenAiCompatibleEmbedder,
    OpenAiCompatibleLanguageModel,
)
from snoska.ports.ai import AiProviderError, ChatMessage, CompletionRequest, MessageRole

SPACE = EmbeddingSpace("test", 3)
POLICY = HttpPolicy(attempts=2, backoff_seconds=0)
SCHEMA = {"type": "object", "properties": {"article": {"type": "string"}}, "required": ["article"]}
REQUEST = CompletionRequest(
    messages=(ChatMessage(MessageRole.USER, "Какая статья?"),), response_schema=SCHEMA
)


@respx.mock
async def test_ollama_embed_contract() -> None:
    route = respx.post("http://ollama.test/api/embed").mock(
        return_value=httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3], [0.3, 0.2, 0.1]]})
    )
    async with httpx.AsyncClient(base_url="http://ollama.test") as client:
        vectors = await OllamaEmbedder(client, "bge-m3", SPACE, POLICY).embed(["a", "b"])
    assert vectors == [[0.1, 0.2, 0.3], [0.3, 0.2, 0.1]]
    sent = json.loads(route.calls[0].request.content)
    assert sent == {"model": "bge-m3", "input": ["a", "b"], "truncate": True}


@respx.mock
async def test_ollama_structured_chat_uses_json_mode_and_validates() -> None:
    route = respx.post("http://ollama.test/api/chat").mock(
        return_value=httpx.Response(
            200, json={"model": "qwen", "message": {"content": '{"article": "9"}'}, "eval_count": 7}
        )
    )
    async with httpx.AsyncClient(base_url="http://ollama.test") as client:
        completion = await OllamaLanguageModel(client, "qwen", POLICY).complete(REQUEST)
    assert json.loads(completion.text) == {"article": "9"}
    sent = json.loads(route.calls[0].request.content)
    assert sent["format"] == "json"
    assert sent["think"] is False
    assert sent["messages"][0]["role"] == "system"
    assert '"article"' in sent["messages"][0]["content"]


@respx.mock
async def test_ollama_free_text_for_structured_request_is_an_error() -> None:
    respx.post("http://ollama.test/api/chat").mock(
        return_value=httpx.Response(200, json={"message": {"content": "Статья 9"}})
    )
    async with httpx.AsyncClient(base_url="http://ollama.test") as client:
        with pytest.raises(AiProviderError):
            await OllamaLanguageModel(client, "qwen", POLICY).complete(REQUEST)


@respx.mock
async def test_transient_failures_are_retried_then_surface() -> None:
    route = respx.post("http://ollama.test/api/embed").mock(return_value=httpx.Response(503))
    async with httpx.AsyncClient(base_url="http://ollama.test") as client:
        with pytest.raises(AiProviderError):
            await OllamaEmbedder(client, "bge-m3", SPACE, POLICY).embed(["a"])
    assert route.call_count == POLICY.attempts


@respx.mock
async def test_openai_compatible_contract() -> None:
    respx.post("http://llm.test/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [{"index": 1, "embedding": [0, 0, 1]}, {"index": 0, "embedding": [1, 0, 0]}]
            },
        )
    )
    chat = respx.post("http://llm.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "m",
                "choices": [{"message": {"content": '{"article": "6"}'}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
        )
    )
    async with httpx.AsyncClient(base_url="http://llm.test/v1/") as client:
        vectors = await OpenAiCompatibleEmbedder(client, "e", SPACE, POLICY).embed(["x", "y"])
        completion = await OpenAiCompatibleLanguageModel(client, "m", POLICY).complete(REQUEST)
    assert vectors == [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    assert completion.completion_tokens == 3
    sent = json.loads(chat.calls[0].request.content)
    assert sent["response_format"]["json_schema"]["schema"] == SCHEMA
