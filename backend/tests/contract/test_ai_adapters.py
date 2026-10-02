from __future__ import annotations

import json

import httpx
import pytest
import respx

from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.infrastructure.ai.http import HttpPolicy
from snoska.infrastructure.ai.openai_compatible import (
    OpenAiCompatibleEmbedder,
    OpenAiCompatibleLanguageModel,
)
from snoska.infrastructure.ai.unconfigured import UnconfiguredEmbedder, UnconfiguredLanguageModel
from snoska.ports.ai import (
    AiProviderError,
    ChatMessage,
    CompletionRequest,
    MessageRole,
    ModelNotConfiguredError,
    ModelOutputError,
)

SPACE = EmbeddingSpace("test", 3)
POLICY = HttpPolicy(attempts=2, backoff_seconds=0)
SCHEMA = {"type": "object", "properties": {"article": {"type": "string"}}, "required": ["article"]}
REQUEST = CompletionRequest(
    messages=(ChatMessage(MessageRole.USER, "Какая статья?"),), response_schema=SCHEMA
)


@respx.mock
async def test_transient_failures_are_retried_then_surface() -> None:
    route = respx.post("http://llm.test/v1/embeddings").mock(return_value=httpx.Response(503))
    async with httpx.AsyncClient(base_url="http://llm.test/v1/") as client:
        with pytest.raises(AiProviderError):
            await OpenAiCompatibleEmbedder(client, "e", SPACE, POLICY).embed(["a"])
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


@respx.mock
async def test_openai_compatible_free_text_for_structured_request_is_an_output_error() -> None:
    respx.post("http://llm.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "Статья 9"}}]})
    )
    async with httpx.AsyncClient(base_url="http://llm.test/v1/") as client:
        with pytest.raises(ModelOutputError):
            await OpenAiCompatibleLanguageModel(client, "m", POLICY).complete(REQUEST)


async def test_without_a_configured_api_every_call_says_so() -> None:
    with pytest.raises(ModelNotConfiguredError):
        await UnconfiguredLanguageModel().complete(REQUEST)
    with pytest.raises(ModelNotConfiguredError):
        await UnconfiguredEmbedder(SPACE).embed(["a"])
