from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

import httpx

from snoska.bootstrap.settings import AiProvider, AiSettings
from snoska.infrastructure.ai.http import HttpPolicy
from snoska.infrastructure.ai.openai_compatible import (
    OpenAiCompatibleEmbedder,
    OpenAiCompatibleLanguageModel,
)
from snoska.infrastructure.ai.unconfigured import UnconfiguredEmbedder, UnconfiguredLanguageModel
from snoska.ports.ai import Embedder, LanguageModel


@dataclass(frozen=True, slots=True)
class AiAdapters:
    """The language model and the embedder of a process.

    Models run only behind an external API. Without one configured, both
    adapters say so on every call, and the product reports "model not
    connected" instead of a result.
    """

    provider: AiProvider
    embedder: Embedder
    language_model: LanguageModel
    close: Callable[[], Awaitable[None]]

    @property
    def configured(self) -> bool:
        return self.provider is not AiProvider.NONE


def _policy(settings: AiSettings) -> HttpPolicy:
    return HttpPolicy(read_timeout=settings.request_timeout_seconds)


async def _nothing_to_close() -> None:
    return None


def _unconfigured(settings: AiSettings) -> AiAdapters:
    return AiAdapters(
        provider=AiProvider.NONE,
        embedder=UnconfiguredEmbedder(settings.embedding_space()),
        language_model=UnconfiguredLanguageModel(),
        close=_nothing_to_close,
    )


def _client(base_url: str, api_key: str, policy: HttpPolicy) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/") + "/",
        headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        timeout=policy.timeout(),
    )


def _openai_compatible(settings: AiSettings) -> AiAdapters:
    settings.require_api()
    policy = _policy(settings)
    llm_key = settings.llm_api_key.get_secret_value()
    chat = _client(settings.llm_base_url, llm_key, policy)
    embeddings = _client(
        settings.embedding_base_url or settings.llm_base_url,
        settings.embedding_api_key.get_secret_value() or llm_key,
        policy,
    )

    async def close() -> None:
        await chat.aclose()
        await embeddings.aclose()

    return AiAdapters(
        provider=AiProvider.OPENAI_COMPATIBLE,
        embedder=OpenAiCompatibleEmbedder(
            embeddings, settings.embedding_model, settings.embedding_space(), policy
        ),
        language_model=OpenAiCompatibleLanguageModel(chat, settings.llm_model, policy),
        close=close,
    )


AI_PROVIDERS: Mapping[AiProvider, Callable[[AiSettings], AiAdapters]] = {
    AiProvider.NONE: _unconfigured,
    AiProvider.OPENAI_COMPATIBLE: _openai_compatible,
}


def build_ai_adapters(settings: AiSettings) -> AiAdapters:
    return AI_PROVIDERS[settings.ai_provider](settings)
