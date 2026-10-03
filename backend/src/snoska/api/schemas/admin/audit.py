from __future__ import annotations

from datetime import datetime
from uuid import UUID

from snoska.api.schemas.common import ApiModel
from snoska.domain.audit.event import AuditAction, AuditEvent
from snoska.domain.tenancy.access import ActorKind


class ActorOut(ApiModel):
    kind: ActorKind
    id: UUID | None
    label: str


class AuditTargetOut(ApiModel):
    type: str
    id: str
    label: str


class AuditEventOut(ApiModel):
    id: UUID
    occurred_at: datetime
    actor: ActorOut
    action: AuditAction
    category: str
    target: AuditTargetOut
    details: dict[str, str | int | bool]

    @classmethod
    def of(cls, event: AuditEvent) -> AuditEventOut:
        return cls(
            id=event.id,
            occurred_at=event.occurred_at,
            actor=ActorOut(kind=event.actor.kind, id=event.actor.id, label=event.actor.label),
            action=event.action,
            category=event.action.category,
            target=AuditTargetOut(
                type=event.target.type, id=event.target.id, label=event.target.label
            ),
            details=dict(event.details),
        )


class AuditPageOut(ApiModel):
    items: list[AuditEventOut]
    next_cursor: str | None
