from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.infrastructure.persistence.tables.checks import text_embeddings


class SqlTextEmbeddingRepository:
    """Vectors of the tenant's passages. Row-level security scopes them to the
    tenant of the transaction, so one tenant never reads another's vectors."""

    def __init__(self, connection: AsyncConnection, organization_id: object) -> None:
        self._connection = connection
        self._organization_id = organization_id

    async def get_many(
        self, space: EmbeddingSpace, hashes: Collection[str]
    ) -> Mapping[str, Sequence[float]]:
        if not hashes:
            return {}
        result = await self._connection.execute(
            select(text_embeddings.c.sha256, text_embeddings.c.embedding).where(
                text_embeddings.c.space_code == space.code,
                text_embeddings.c.sha256.in_(list(hashes)),
            )
        )
        return {row.sha256: list(row.embedding) for row in result}

    async def put_many(self, space: EmbeddingSpace, vectors: Mapping[str, Sequence[float]]) -> None:
        if not vectors:
            return
        # The cache time is bookkeeping of the store itself, not domain time.
        now = datetime.now(UTC)
        statement = pg_insert(text_embeddings).values(
            [
                {
                    "organization_id": self._organization_id,
                    "space_code": space.code,
                    "sha256": digest,
                    "embedding": list(vector),
                    "created_at": now,
                }
                for digest, vector in vectors.items()
            ]
        )
        await self._connection.execute(statement.on_conflict_do_nothing())
