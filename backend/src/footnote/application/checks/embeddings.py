from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from uuid import UUID

from footnote.domain.corpus.embedding import EmbeddingSpace
from footnote.ports.unit_of_work import UnitOfWorkFactory


class TenantEmbeddings:
    """The tenant's stored passage vectors, each call in its own short transaction."""

    def __init__(self, uow_factory: UnitOfWorkFactory, organization_id: UUID) -> None:
        self._uow_factory = uow_factory
        self._organization_id = organization_id

    async def get_many(
        self, space: EmbeddingSpace, hashes: Collection[str]
    ) -> Mapping[str, Sequence[float]]:
        async with self._uow_factory.for_tenant(self._organization_id) as uow:
            return await uow.embeddings.get_many(space, hashes)

    async def put_many(self, space: EmbeddingSpace, vectors: Mapping[str, Sequence[float]]) -> None:
        async with self._uow_factory.for_tenant(self._organization_id) as uow:
            await uow.embeddings.put_many(space, vectors)
            await uow.commit()


class MemoryEmbeddings:
    """Passage vectors kept for the lifetime of one process (benchmark runs)."""

    def __init__(self) -> None:
        self._vectors: dict[tuple[str, str], Sequence[float]] = {}

    async def get_many(
        self, space: EmbeddingSpace, hashes: Collection[str]
    ) -> Mapping[str, Sequence[float]]:
        return {
            digest: self._vectors[(space.code, digest)]
            for digest in hashes
            if (space.code, digest) in self._vectors
        }

    async def put_many(self, space: EmbeddingSpace, vectors: Mapping[str, Sequence[float]]) -> None:
        for digest, vector in vectors.items():
            self._vectors[(space.code, digest)] = vector
