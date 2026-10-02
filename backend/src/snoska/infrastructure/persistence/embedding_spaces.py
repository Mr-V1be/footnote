from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.infrastructure.persistence.tables.corpus import embedding_spaces


class UnknownEmbeddingSpaceError(RuntimeError):
    """The configured vector space has no migration (and no index) yet."""


async def load_embedding_space(engine: AsyncEngine, code: str) -> EmbeddingSpace:
    async with engine.connect() as connection:
        dimensions = await connection.scalar(
            select(embedding_spaces.c.dimensions).where(embedding_spaces.c.code == code)
        )
    if dimensions is None:
        raise UnknownEmbeddingSpaceError(
            f"embedding space {code!r} is not registered; add a migration for it"
        )
    return EmbeddingSpace(code=code, dimensions=int(dimensions))
