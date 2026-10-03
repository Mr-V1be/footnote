from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from snoska.domain.autofix.actions import AppliedChange, ChangeKind
from snoska.infrastructure.persistence.tables.autofix import version_changes


class SqlChangeJournal:
    def __init__(self, connection: AsyncConnection, organization_id: UUID | None) -> None:
        self._connection = connection
        self._organization_id = organization_id

    async def record(self, version_id: UUID, changes: Sequence[AppliedChange]) -> None:
        if not changes:
            return
        if self._organization_id is None:
            raise RuntimeError("the journal is written in a tenant unit of work")
        await self._connection.execute(
            insert(version_changes),
            [
                {
                    "organization_id": self._organization_id,
                    "version_id": version_id,
                    "ordinal": ordinal,
                    "check_code": change.check_code,
                    "kind": change.kind.value,
                    "block_ordinal": change.block_ordinal,
                    "before": change.before,
                    "after": change.after,
                    "places": change.places,
                }
                for ordinal, change in enumerate(changes)
            ],
        )

    async def list_for_version(self, version_id: UUID) -> Sequence[AppliedChange]:
        result = await self._connection.execute(
            select(version_changes)
            .where(version_changes.c.version_id == version_id)
            .order_by(version_changes.c.ordinal)
        )
        return [
            AppliedChange(
                check_code=row["check_code"],
                kind=ChangeKind(row["kind"]),
                block_ordinal=row["block_ordinal"],
                before=row["before"],
                after=row["after"],
                places=row["places"],
            )
            for row in result.mappings()
        ]
