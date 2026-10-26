from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from footnote.domain.documents.document import Document, DocumentNotFoundError
from footnote.domain.tenancy.access import OrganizationAccess
from footnote.domain.tenancy.organization import Workspace
from footnote.domain.tenancy.permissions import Permission
from footnote.domain.tenancy.roles import RoleCatalog
from footnote.domain.tenancy.workspace_access import (
    WorkspaceAccess,
    WorkspaceUnavailableError,
    workspace_access,
)
from footnote.ports.unit_of_work import UnitOfWork


class WorkspaceGate:
    """What a member may do in a workspace, and through it with a document.

    Every read or change of a document goes through here, inside the
    caller's transaction. A document of a workspace the member cannot reach
    is reported as not found, like a document that does not exist.
    """

    def __init__(self, roles: RoleCatalog) -> None:
        self._roles = roles

    async def access(
        self, uow: UnitOfWork, access: OrganizationAccess, workspace: Workspace
    ) -> WorkspaceAccess:
        member = await uow.workspace_members.get(workspace.id, access.user_id)
        role = self._roles.get(member.role_code) if member is not None else None
        return workspace_access(access, workspace, role)

    async def require(
        self,
        uow: UnitOfWork,
        access: OrganizationAccess,
        workspace: Workspace | None,
        permission: Permission,
    ) -> WorkspaceAccess:
        if workspace is None:
            raise WorkspaceUnavailableError("workspace not found")
        granted = await self.access(uow, access, workspace)
        granted.require(permission)
        return granted

    async def require_slug(
        self, uow: UnitOfWork, access: OrganizationAccess, slug: str, permission: Permission
    ) -> WorkspaceAccess:
        return await self.require(uow, access, await uow.workspaces.get_by_slug(slug), permission)

    async def require_document(
        self,
        uow: UnitOfWork,
        access: OrganizationAccess,
        document_id: UUID,
        permission: Permission,
    ) -> Document:
        document, _ = await self.document_access(uow, access, document_id, permission)
        return document

    async def document_access(
        self,
        uow: UnitOfWork,
        access: OrganizationAccess,
        document_id: UUID,
        permission: Permission,
    ) -> tuple[Document, WorkspaceAccess]:
        """The document and what the member may do in its workspace."""
        document = await uow.documents.get(document_id)
        if document is None:
            raise DocumentNotFoundError("document not found")
        workspace = await uow.workspaces.get(document.workspace_id)
        try:
            granted = await self.require(uow, access, workspace, permission)
        except WorkspaceUnavailableError as exc:
            raise DocumentNotFoundError("document not found") from exc
        return document, granted

    async def visible(
        self, uow: UnitOfWork, access: OrganizationAccess
    ) -> Sequence[WorkspaceAccess]:
        """The workspaces the member reaches, with their roles there."""
        reachable: list[WorkspaceAccess] = []
        for workspace in await uow.workspaces.list():
            try:
                reachable.append(await self.access(uow, access, workspace))
            except WorkspaceUnavailableError:
                continue
        return reachable
