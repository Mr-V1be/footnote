from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import Protocol

from snoska.domain.corpus.embedding import EmbeddingSpace


class EmbeddingCache(Protocol):
    """Vectors of texts by content hash, so unchanged text is never embedded twice.

    The tenant's stored vectors implement it inside a unit of work; a run
    outside the database (the reference benchmark) keeps them in memory.
    """

    async def get_many(
        self, space: EmbeddingSpace, hashes: Collection[str]
    ) -> Mapping[str, Sequence[float]]: ...

    async def put_many(
        self, space: EmbeddingSpace, vectors: Mapping[str, Sequence[float]]
    ) -> None: ...
