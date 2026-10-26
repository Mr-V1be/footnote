from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from footnote.infrastructure.persistence.tables.outbox import outbox_messages
from footnote.ports.outbox import OutboxMessage


class SqlOutboxRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, message: OutboxMessage) -> None:
        await self._connection.execute(
            insert(outbox_messages).values(
                id=message.id,
                job_name=message.job_name,
                payload=dict(message.payload),
                created_at=message.created_at,
                available_at=message.available_at or message.created_at,
                attempts=message.attempts,
            )
        )

    async def claim_due(self, now: datetime, limit: int) -> Sequence[OutboxMessage]:
        result = await self._connection.execute(
            select(outbox_messages)
            .where(outbox_messages.c.dispatched_at.is_(None), outbox_messages.c.available_at <= now)
            .order_by(outbox_messages.c.available_at, outbox_messages.c.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return [
            OutboxMessage(
                id=row["id"],
                job_name=row["job_name"],
                payload=row["payload"],
                created_at=row["created_at"],
                attempts=row["attempts"],
            )
            for row in result.mappings()
        ]

    async def mark_dispatched(self, message_id: UUID, now: datetime) -> None:
        await self._connection.execute(
            update(outbox_messages)
            .where(outbox_messages.c.id == message_id)
            .values(dispatched_at=now, last_error=None)
        )

    async def pending_count(self) -> int:
        result = await self._connection.execute(
            select(func.count()).where(outbox_messages.c.dispatched_at.is_(None))
        )
        return int(result.scalar_one())

    async def postpone(self, message_id: UUID, until: datetime, error: str) -> None:
        await self._connection.execute(
            update(outbox_messages)
            .where(outbox_messages.c.id == message_id)
            .values(
                available_at=until,
                attempts=outbox_messages.c.attempts + 1,
                last_error=error[:2000],
            )
        )
