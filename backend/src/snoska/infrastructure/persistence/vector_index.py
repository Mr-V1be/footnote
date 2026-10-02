from __future__ import annotations

import re
from typing import Any

from pgvector.sqlalchemy import HALFVEC, Vector
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.infrastructure.persistence.tables.corpus import embedding_spaces

# Space codes are interpolated into SQL so the planner can match the partial
# HNSW index of the space; only this shape is ever accepted.
_SPACE_CODE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")
# HNSW indexes full-precision vectors up to this size; larger ones are
# indexed (and compared) as half-precision vectors.
MAX_FULL_PRECISION_DIMENSIONS = 2000
# Tables whose rows carry vectors of a space.
_VECTOR_TABLES = ("norm_embeddings", "text_embeddings")


class EmbeddingSpaceConflictError(RuntimeError):
    """A space code is registered with another vector size."""


def checked_code(space: EmbeddingSpace) -> str:
    if not _SPACE_CODE.fullmatch(space.code):
        raise ValueError(f"invalid embedding space code {space.code!r}")
    return space.code


def space_predicate(space: EmbeddingSpace, table: str | None = None) -> str:
    """``space_code = '<code>'``, literal so the planner can use the space's
    partial index; ``table`` qualifies the column in joins."""
    column = f"{table}.space_code" if table else "space_code"
    return f"{column} = '{checked_code(space)}'"


def half_precision(space: EmbeddingSpace) -> bool:
    return space.dimensions > MAX_FULL_PRECISION_DIMENSIONS


def comparable_type(space: EmbeddingSpace) -> Any:
    """The SQL type vectors of the space are cast to for comparison and indexing."""
    return HALFVEC(space.dimensions) if half_precision(space) else Vector(space.dimensions)


def index_name(space: EmbeddingSpace) -> str:
    return f"ix_norm_embeddings_{re.sub(r'[^a-z0-9]', '_', checked_code(space))}_hnsw"[:63]


async def ensure_space(owner: AsyncEngine, space: EmbeddingSpace) -> None:
    """Register a space and its search index; runs as the schema owner."""
    if space.dimensions <= 0:
        raise ValueError("no embedding model is configured")
    code = checked_code(space)
    cast_type = "halfvec" if half_precision(space) else "vector"
    async with owner.begin() as connection:
        registered = await connection.scalar(
            select(embedding_spaces.c.dimensions).where(embedding_spaces.c.code == code)
        )
        if registered is not None and int(registered) != space.dimensions:
            raise EmbeddingSpaceConflictError(
                f"space {code!r} is registered with {registered} dimensions"
            )
        if registered is None:
            await connection.execute(
                embedding_spaces.insert().values(code=code, dimensions=space.dimensions)
            )
        await connection.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {index_name(space)} ON norm_embeddings "
                f"USING hnsw ((embedding::{cast_type}({space.dimensions})) "
                f"{cast_type}_cosine_ops) WHERE {space_predicate(space)}"
            )
        )


async def drop_spaces_except(owner: AsyncEngine, keep: EmbeddingSpace) -> list[str]:
    """Remove the vectors, indexes and registrations of every other space."""
    async with owner.begin() as connection:
        others = [
            row.code
            for row in await connection.execute(
                select(embedding_spaces.c.code, embedding_spaces.c.dimensions).where(
                    embedding_spaces.c.code != keep.code
                )
            )
        ]
        for code in others:
            space = EmbeddingSpace(code=code, dimensions=1)
            await connection.execute(text(f"DROP INDEX IF EXISTS {index_name(space)}"))
            for table in _VECTOR_TABLES:
                await connection.execute(
                    text(f"DELETE FROM {table} WHERE {space_predicate(space)}")  # noqa: S608
                )
            await connection.execute(
                embedding_spaces.delete().where(embedding_spaces.c.code == code)
            )
    return others
