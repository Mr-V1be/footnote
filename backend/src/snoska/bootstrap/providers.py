from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

import httpx

from snoska.bootstrap.settings import AiProvider, AiSettings
from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.infrastructure.ai.http import HttpPolicy
from snoska.infrastructure.ai.ollama import OllamaEmbedder, OllamaLanguageModel
from snoska.infrastructure.ai.openai_compatible import (
    OpenAiCompatibleEmbedder,
    OpenAiCompatibleLanguageModel,
)
from snoska.ports.ai import Embedder, LanguageModel


@dataclass(frozen=True, slots=True)
class AiAdapters:
    provider: AiProvider
    embedder: Embedder
    language_model: LanguageModel
    close: Callable[[], Awaitable[None]]


def _policy(settings: AiSettings) -> HttpPolicy:
    return HttpPolicy(read_timeout=settings.request_timeout_seconds)


def _ollama(settings: AiSettings, space: EmbeddingSpace) -> AiAdapters:
    policy = _policy(settings)
    client = httpx.AsyncClient(base_url=settings.ollama_url, timeout=policy.timeout())
    return AiAdapters(
        provider=AiProvider.OLLAMA,
        embedder=OllamaEmbedder(client, settings.embedding_model, space, policy),
        language_model=OllamaLanguageModel(client, settings.llm_model, policy),
        close=client.aclose,
    )


def _openai_compatible(settings: AiSettings, space: EmbeddingSpace) -> AiAdapters:
    if not settings.openai_base_url:
        raise ValueError("SNOSKA_OPENAI_BASE_URL is required for the openai_compatible provider")
    policy = _policy(settings)
    key = settings.openai_api_key.get_secret_value()
    client = httpx.AsyncClient(
        base_url=settings.openai_base_url.rstrip("/") + "/",
        headers={"Authorization": f"Bearer {key}"} if key else {},
        timeout=policy.timeout(),
    )
    return AiAdapters(
        provider=AiProvider.OPENAI_COMPATIBLE,
        embedder=OpenAiCompatibleEmbedder(client, settings.embedding_model, space, policy),
        language_model=OpenAiCompatibleLanguageModel(client, settings.llm_model, policy),
        close=client.aclose,
    )


AI_PROVIDERS: Mapping[AiProvider, Callable[[AiSettings, EmbeddingSpace], AiAdapters]] = {
    AiProvider.OLLAMA: _ollama,
    AiProvider.OPENAI_COMPATIBLE: _openai_compatible,
}


def build_ai_adapters(settings: AiSettings, space: EmbeddingSpace) -> AiAdapters:
    return AI_PROVIDERS[settings.ai_provider](settings, space)
