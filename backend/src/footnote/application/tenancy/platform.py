from __future__ import annotations

from collections.abc import Sequence

from footnote.domain.tenancy.access import PlatformAccess
from footnote.domain.tenancy.organization import Organization
from footnote.domain.tenancy.permissions import Permission
from footnote.ports.unit_of_work import UnitOfWorkFactory


class PlatformTenantQueries:
    """Cross-tenant registry for platform operators. Never exposes tenant data."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def organizations(
        self, access: PlatformAccess, *, limit: int, offset: int
    ) -> Sequence[Organization]:
        access.require(Permission.PLATFORM_TENANTS_READ)
        async with self._uow_factory.for_platform() as uow:
            return await uow.organizations.list_all(limit=limit, offset=offset)
