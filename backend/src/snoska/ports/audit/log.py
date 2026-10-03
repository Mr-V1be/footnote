from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from snoska.domain.audit.event import AuditAction, AuditEvent
from snoska.domain.tenancy.access import ActorKind


@dataclass(frozen=True, slots=True)
class AuditFilter:
    actions: frozenset[AuditAction] = frozenset()
    actor_kind: ActorKind | None = None
    actor_id: UUID | None = None
    since: datetime | None = None
    until: datetime | None = None


@dataclass(frozen=True, slots=True)
class AuditCursor:
    occurred_at: datetime
    id: UUID


class AuditLog(Protocol):
    """Tenant-scoped, append-only."""

    async def record(self, event: AuditEvent) -> None: ...

    async def page(
        self, where: AuditFilter, after: AuditCursor | None, limit: int
    ) -> Sequence[AuditEvent]:
        """Newest first."""
        ...

    def export(self, where: AuditFilter) -> AsyncIterator[AuditEvent]:
        """Every matching event, newest first, without loading them all."""
        ...
