from __future__ import annotations

from collections.abc import Sequence

from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.ports.ai import Completion, CompletionRequest, ModelNotConfiguredError


class UnconfiguredLanguageModel:
    """Stands in while no model API is configured: every call says so."""

    model = ""

    async def complete(self, request: CompletionRequest) -> Completion:
        raise ModelNotConfiguredError("no language model API is configured")


class UnconfiguredEmbedder:
    """Stands in while no embedding API is configured: every call says so."""

    model = ""

    def __init__(self, space: EmbeddingSpace) -> None:
        self.space = space

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise ModelNotConfiguredError("no embedding model API is configured")
