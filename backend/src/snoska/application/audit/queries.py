from __future__ import annotations

from collections.abc import AsyncIterator

from snoska.application.shared.pagination import Page, clamp_page_size, next_page
from snoska.domain.audit.event import AuditEvent
from snoska.domain.tenancy.access import OrganizationAccess
from snoska.domain.tenancy.permissions import Permission
from snoska.ports.audit.log import AuditFilter
from snoska.ports.pagination import TimeCursor
from snoska.ports.unit_of_work import UnitOfWorkFactory


class AuditQueries:
    """Reads of an organization's audit log: pages for the screen, a full
    export for an auditor."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def page(
        self,
        access: OrganizationAccess,
        where: AuditFilter,
        after: TimeCursor | None,
        limit: int | None,
    ) -> Page[AuditEvent, TimeCursor]:
        access.require(Permission.AUDIT_READ)
        size = clamp_page_size(limit)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            rows = await uow.audit.page(where, after, size + 1)
        return next_page(rows, size, lambda event: TimeCursor(event.occurred_at, event.id))

    async def export(
        self, access: OrganizationAccess, where: AuditFilter
    ) -> AsyncIterator[AuditEvent]:
        """Streams inside one read transaction, newest first."""
        access.require(Permission.AUDIT_READ)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            async for event in uow.audit.export(where):
                yield event
