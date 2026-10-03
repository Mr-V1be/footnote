from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import RowMapping, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from snoska.domain.operations.schedule import EditionCheck, TaskState, WatchOutcome
from snoska.infrastructure.persistence.tables.operations import edition_checks, task_states


def _state(row: RowMapping) -> TaskState:
    return TaskState(
        name=row["name"], next_run_at=row["next_run_at"], last_run_at=row["last_run_at"]
    )


class SqlTaskStateRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def ensure(self, state: TaskState) -> None:
        await self._connection.execute(
            pg_insert(task_states)
            .values(name=state.name, next_run_at=state.next_run_at, last_run_at=state.last_run_at)
            .on_conflict_do_nothing(index_elements=[task_states.c.name])
        )

    async def claim_due(self, now: datetime, names: Sequence[str]) -> Sequence[TaskState]:
        result = await self._connection.execute(
            select(task_states)
            .where(task_states.c.name.in_(list(names)), task_states.c.next_run_at <= now)
            .with_for_update(skip_locked=True)
        )
        return [_state(row) for row in result.mappings()]

    async def save(self, state: TaskState) -> None:
        await self._connection.execute(
            update(task_states)
            .where(task_states.c.name == state.name)
            .values(next_run_at=state.next_run_at, last_run_at=state.last_run_at)
        )

    async def get(self, name: str) -> TaskState | None:
        row = (
            (await self._connection.execute(select(task_states).where(task_states.c.name == name)))
            .mappings()
            .first()
        )
        return _state(row) if row else None


class SqlEditionCheckLog:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, check: EditionCheck) -> None:
        await self._connection.execute(
            insert(edition_checks).values(
                id=check.id,
                act_code=check.act_code,
                checked_at=check.checked_at,
                outcome=check.outcome.value,
                revision=check.revision,
                edition_id=check.edition_id,
                error=check.error,
            )
        )

    async def latest(self, *, limit: int) -> Sequence[EditionCheck]:
        result = await self._connection.execute(
            select(edition_checks).order_by(edition_checks.c.checked_at.desc()).limit(limit)
        )
        return [
            EditionCheck(
                id=row["id"],
                act_code=row["act_code"],
                checked_at=row["checked_at"],
                outcome=WatchOutcome(row["outcome"]),
                revision=row["revision"],
                edition_id=row["edition_id"],
                error=row["error"],
            )
            for row in result.mappings()
        ]
