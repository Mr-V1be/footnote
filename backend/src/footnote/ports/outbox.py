from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from footnote.ports.jobs import JobPayload


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    """A job recorded in the same transaction as the change that causes it."""

    id: UUID
    job_name: str
    payload: JobPayload
    created_at: datetime
    attempts: int = 0
    # Not before this moment (a delayed retry); None means at once.
    available_at: datetime | None = None


class OutboxRepository(Protocol):
    async def add(self, message: OutboxMessage) -> None: ...

    async def claim_due(self, now: datetime, limit: int) -> Sequence[OutboxMessage]:
        """Lock due messages for this transaction, skipping ones locked elsewhere."""
        ...

    async def mark_dispatched(self, message_id: UUID, now: datetime) -> None: ...

    async def postpone(self, message_id: UUID, until: datetime, error: str) -> None: ...

    async def pending_count(self) -> int:
        """Messages not yet handed to the queue (an operator's health signal)."""
        ...
