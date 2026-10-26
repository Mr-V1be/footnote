from __future__ import annotations

import json

import httpx
import pytest
import respx

from footnote.domain.corpus.embedding import EmbeddingSpace
from footnote.infrastructure.ai.cache import CachingLanguageModel
from footnote.infrastructure.ai.http import HttpPolicy
from footnote.infrastructure.ai.openai_compatible import (
    OpenAiCompatibleEmbedder,
    OpenAiCompatibleLanguageModel,
)
from footnote.infrastructure.ai.unconfigured import UnconfiguredEmbedder, UnconfiguredLanguageModel
from footnote.ports.ai import (
    AiProviderError,
    ChatMessage,
    Completion,
    CompletionRequest,
    MessageRole,
    ModelBudgetExhaustedError,
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


class CountingBudget:
    """Counts the requests taken and those that count (taken less the ones
    given back); refuses after ``allowance`` of them."""

    def __init__(self, allowance: int | None = None) -> None:
        self.spent = 0
        self.taken = 0
        self._allowance = allowance

    async def spend(self) -> None:
        if self._allowance is not None and self.spent >= self._allowance:
            raise ModelBudgetExhaustedError("spent")
        self.spent += 1
        self.taken += 1

    async def refund(self) -> None:
        self.spent -= 1

    async def remaining_today(self) -> int | None:
        return None if self._allowance is None else self._allowance - self.spent


def answered(model: str) -> httpx.Response:
    return httpx.Response(
        200, json={"model": model, "choices": [{"message": {"content": '{"article": "21"}'}}]}
    )


@respx.mock
async def test_a_busy_model_is_retried_then_the_next_of_the_chain_answers() -> None:
    def route(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        return (
            httpx.Response(429, text="rate-limited upstream")
            if model == "first"
            else answered(model)
        )

    chat = respx.post("http://llm.test/v1/chat/completions").mock(side_effect=route)
    budget = CountingBudget()
    async with httpx.AsyncClient(base_url="http://llm.test/v1/") as client:
        model = OpenAiCompatibleLanguageModel(
            client, "first", POLICY, fallbacks=("second",), budget=budget
        )
        completion = await model.complete(REQUEST)
    assert completion.model == "second"
    assert chat.call_count == POLICY.attempts + 1
    assert budget.taken == chat.call_count, "every request is taken from the budget"
    assert budget.spent == 1, "requests refused as busy are given back"


@respx.mock
async def test_the_providers_daily_limit_stops_the_chain() -> None:
    chat = respx.post("http://llm.test/v1/chat/completions").mock(
        return_value=httpx.Response(429, text="Rate limit exceeded: free-models-per-day")
    )
    async with httpx.AsyncClient(base_url="http://llm.test/v1/") as client:
        model = OpenAiCompatibleLanguageModel(client, "first", POLICY, fallbacks=("second",))
        with pytest.raises(ModelBudgetExhaustedError):
            await model.complete(REQUEST)
    assert chat.call_count == 1


@respx.mock
async def test_a_spent_budget_sends_nothing() -> None:
    chat = respx.post("http://llm.test/v1/chat/completions").mock(return_value=answered("first"))
    async with httpx.AsyncClient(base_url="http://llm.test/v1/") as client:
        model = OpenAiCompatibleLanguageModel(
            client, "first", POLICY, budget=CountingBudget(allowance=0)
        )
        with pytest.raises(ModelBudgetExhaustedError):
            await model.complete(REQUEST)
    assert chat.call_count == 0


class MemoryCache:
    def __init__(self) -> None:
        self.entries: dict[str, Completion] = {}

    async def get(self, key: str) -> Completion | None:
        return self.entries.get(key)

    async def put(self, key: str, completion: Completion) -> None:
        self.entries[key] = completion


@respx.mock
async def test_a_repeated_request_is_answered_from_the_cache() -> None:
    chat = respx.post("http://llm.test/v1/chat/completions").mock(return_value=answered("first"))
    cache = MemoryCache()
    async with httpx.AsyncClient(base_url="http://llm.test/v1/") as client:
        inner = OpenAiCompatibleLanguageModel(client, "first", POLICY)
        model = CachingLanguageModel(inner, cache, inner.chain)
        first = await model.complete(REQUEST)
        again = await model.complete(REQUEST)
        other = await model.complete(
            CompletionRequest(messages=(ChatMessage(MessageRole.USER, "Другой вопрос"),))
        )
    assert first.text == again.text == other.text
    assert chat.call_count == 2, "the repeated request cost nothing"


@respx.mock
async def test_without_reading_every_request_reaches_the_model_and_is_kept() -> None:
    chat = respx.post("http://llm.test/v1/chat/completions").mock(return_value=answered("first"))
    cache = MemoryCache()
    async with httpx.AsyncClient(base_url="http://llm.test/v1/") as client:
        inner = OpenAiCompatibleLanguageModel(client, "first", POLICY)
        measuring = CachingLanguageModel(inner, cache, inner.chain, read=False)
        await measuring.complete(REQUEST)
        await measuring.complete(REQUEST)
        serving = CachingLanguageModel(inner, cache, inner.chain)
        await serving.complete(REQUEST)
    assert chat.call_count == 2, "the stand is answered from what the measurement kept"
