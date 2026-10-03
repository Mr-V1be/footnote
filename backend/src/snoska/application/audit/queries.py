from __future__ import annotations

from collections.abc import AsyncIterator

from snoska.application.shared.pagination import Page, clamp_page_size
from snoska.domain.audit.event import AuditEvent
from snoska.domain.tenancy.access import OrganizationAccess
from snoska.domain.tenancy.permissions import Permission
from snoska.ports.audit.log import AuditCursor, AuditFilter
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
        after: AuditCursor | None,
        limit: int | None,
    ) -> Page[AuditEvent, AuditCursor]:
        access.require(Permission.AUDIT_READ)
        size = clamp_page_size(limit)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            rows = await uow.audit.page(where, after, size + 1)
        items = rows[:size]
        next_cursor = (
            AuditCursor(occurred_at=items[-1].occurred_at, id=items[-1].id)
            if len(rows) > size
            else None
        )
        return Page(items=items, next_cursor=next_cursor)

    async def export(
        self, access: OrganizationAccess, where: AuditFilter
    ) -> AsyncIterator[AuditEvent]:
        """Streams inside one read transaction, newest first."""
        access.require(Permission.AUDIT_READ)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            async for event in uow.audit.export(where):
                yield event
