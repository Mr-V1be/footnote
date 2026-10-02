"""In-memory stand-ins for external providers."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from uuid import UUID

from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.ports.identity import OrganizationProfile


class FakeDirectory:
    def __init__(self, organizations: Sequence[OrganizationProfile]) -> None:
        self._organizations = {org.id: org for org in organizations}

    async def get_organization(self, organization_id: UUID) -> OrganizationProfile | None:
        return self._organizations.get(organization_id)


class HashEmbedder:
    """Deterministic unit vectors: equal texts get equal vectors."""

    model = "hash-embedder"

    def __init__(self, space: EmbeddingSpace) -> None:
        self.space = space

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.space.dimensions:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            values.extend((byte - 127.5) / 127.5 for byte in digest)
            counter += 1
        vector = values[: self.space.dimensions]
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]
