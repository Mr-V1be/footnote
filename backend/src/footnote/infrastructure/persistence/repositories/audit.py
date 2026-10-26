from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, RowMapping, Select, and_, insert, select, tuple_
from sqlalchemy.ext.asyncio import AsyncConnection

from footnote.domain.audit.event import AuditAction, AuditEvent, AuditTarget
from footnote.domain.tenancy.access import Actor, ActorKind
from footnote.infrastructure.persistence.tables.audit import audit_events
from footnote.ports.audit.log import AuditFilter
from footnote.ports.pagination import TimeCursor

EXPORT_BATCH = 500


def _event(row: RowMapping) -> AuditEvent:
    return AuditEvent(
        id=row["id"],
        organization_id=row["organization_id"],
        occurred_at=row["occurred_at"],
        actor=Actor(
            kind=ActorKind(row["actor_kind"]), id=row["actor_id"], label=row["actor_label"]
        ),
        action=AuditAction(row["action"]),
        target=AuditTarget(type=row["target_type"], id=row["target_id"], label=row["target_label"]),
        details=dict(row["details"]),
    )


def _filtered(statement: Select[Any], where: AuditFilter) -> Select[Any]:
    conditions: list[ColumnElement[bool]] = []
    if where.actions:
        conditions.append(audit_events.c.action.in_([action.value for action in where.actions]))
    if where.actor_kind is not None:
        conditions.append(audit_events.c.actor_kind == where.actor_kind.value)
    if where.actor_id is not None:
        conditions.append(audit_events.c.actor_id == where.actor_id)
    if where.since is not None:
        conditions.append(audit_events.c.occurred_at >= where.since)
    if where.until is not None:
        conditions.append(audit_events.c.occurred_at < where.until)
    return statement.where(and_(*conditions)) if conditions else statement


def _newest_first(statement: Select[Any]) -> Select[Any]:
    return statement.order_by(audit_events.c.occurred_at.desc(), audit_events.c.id.desc())


class SqlAuditLog:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def record(self, event: AuditEvent) -> None:
        await self._connection.execute(
            insert(audit_events).values(
                id=event.id,
                organization_id=event.organization_id,
                occurred_at=event.occurred_at,
                actor_kind=event.actor.kind.value,
                actor_id=event.actor.id,
                actor_label=event.actor.label,
                action=event.action.value,
                target_type=event.target.type,
                target_id=event.target.id,
                target_label=event.target.label,
                details=dict(event.details),
            )
        )

    async def page(
        self, where: AuditFilter, after: TimeCursor | None, limit: int
    ) -> Sequence[AuditEvent]:
        statement = _filtered(select(audit_events), where)
        if after is not None:
            statement = statement.where(
                tuple_(audit_events.c.occurred_at, audit_events.c.id) < tuple_(after.at, after.id)
            )
        result = await self._connection.execute(_newest_first(statement).limit(limit))
        return [_event(row) for row in result.mappings()]

    async def export(self, where: AuditFilter) -> AsyncIterator[AuditEvent]:
        last: tuple[object, UUID] | None = None
        while True:
            statement = _filtered(select(audit_events), where)
            if last is not None:
                statement = statement.where(
                    tuple_(audit_events.c.occurred_at, audit_events.c.id) < tuple_(*last)
                )
            result = await self._connection.execute(_newest_first(statement).limit(EXPORT_BATCH))
            rows = list(result.mappings())
            for row in rows:
                yield _event(row)
            if len(rows) < EXPORT_BATCH:
                return
            last = (rows[-1]["occurred_at"], rows[-1]["id"])
