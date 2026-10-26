from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from footnote.domain.audit.event import AuditAction, AuditEvent, AuditTarget, AuditValue
from footnote.domain.shared.ids import new_id
from footnote.domain.tenancy.access import Actor, OrganizationAccess
from footnote.ports.clock import Clock
from footnote.ports.unit_of_work import UnitOfWork


class AuditTrail:
    """Writes audit entries inside the caller's transaction, so an entry
    exists exactly when the change it describes was committed."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    async def record(
        self,
        uow: UnitOfWork,
        access: OrganizationAccess,
        action: AuditAction,
        target: AuditTarget,
        details: Mapping[str, AuditValue] | None = None,
    ) -> None:
        await self.record_as(uow, access.organization_id, access.actor, action, target, details)

    async def record_as(
        self,
        uow: UnitOfWork,
        organization_id: UUID,
        actor: Actor,
        action: AuditAction,
        target: AuditTarget,
        details: Mapping[str, AuditValue] | None = None,
    ) -> None:
        """For changes made without a member's request (a payment, the system)."""
        await uow.audit.record(
            AuditEvent(
                id=new_id(),
                organization_id=organization_id,
                occurred_at=self._clock.now(),
                actor=actor,
                action=action,
                target=target,
                details=dict(details or {}),
            )
        )
