from __future__ import annotations

from collections.abc import Sequence

from snoska.domain.shared.errors import NotFoundError
from snoska.domain.tenancy.access import OrganizationAccess
from snoska.domain.tenancy.organization import Workspace
from snoska.domain.tenancy.permissions import Permission
from snoska.ports.unit_of_work import UnitOfWorkFactory


class WorkspaceNotFoundError(NotFoundError):
    code = "workspace_not_found"


class WorkspaceQueries:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def list(self, access: OrganizationAccess) -> Sequence[Workspace]:
        access.require(Permission.DOCUMENTS_READ)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            return await uow.workspaces.list()

    async def get(self, access: OrganizationAccess, slug: str) -> Workspace:
        access.require(Permission.DOCUMENTS_READ)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            workspace = await uow.workspaces.get_by_slug(slug)
        if workspace is None:
            raise WorkspaceNotFoundError(f"workspace {slug!r} not found")
        return workspace
