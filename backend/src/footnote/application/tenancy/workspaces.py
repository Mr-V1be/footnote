from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from uuid import UUID

from footnote.application.audit.trail import AuditTrail
from footnote.application.tenancy.gate import WorkspaceGate
from footnote.domain.audit.event import AuditAction, AuditTarget
from footnote.domain.shared.errors import ConflictError
from footnote.domain.shared.ids import new_id
from footnote.domain.tenancy.access import OrganizationAccess
from footnote.domain.tenancy.members import require_role
from footnote.domain.tenancy.organization import Workspace, validate_slug
from footnote.domain.tenancy.permissions import Permission
from footnote.domain.tenancy.roles import RoleCatalog
from footnote.domain.tenancy.workspace_access import (
    WorkspaceAccess,
    WorkspaceMember,
    WorkspaceUnavailableError,
)
from footnote.ports.clock import Clock
from footnote.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

# Kept for callers that name the error after the use case.
WorkspaceNotFoundError = WorkspaceUnavailableError


class WorkspaceNotEmptyError(ConflictError):
    """A workspace with documents is not deleted: they would go with it."""

    code = "workspace_not_empty"


class LastWorkspaceError(ConflictError):
    code = "last_workspace"


@dataclass(frozen=True, slots=True)
class WorkspaceSummary:
    access: WorkspaceAccess
    documents: int


@dataclass(frozen=True, slots=True)
class WorkspaceChange:
    name: str | None = None
    slug: str | None = None
    restricted: bool | None = None


def _target(workspace: Workspace) -> AuditTarget:
    return AuditTarget(type="workspace", id=str(workspace.id), label=workspace.name)


class Workspaces:
    """The workspaces of an organization: what a member reaches, and their
    administration (create, rename, restrict, delete, roles inside)."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        gate: WorkspaceGate,
        roles: RoleCatalog,
        audit: AuditTrail,
        clock: Clock,
    ) -> None:
        self._uow_factory = uow_factory
        self._gate = gate
        self._roles = roles
        self._audit = audit
        self._clock = clock

    async def list(self, access: OrganizationAccess) -> Sequence[WorkspaceSummary]:
        access.require(Permission.DOCUMENTS_READ)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            reachable = await self._gate.visible(uow, access)
            counts = await uow.workspaces.document_counts()
        return [
            WorkspaceSummary(access=item, documents=counts.get(item.workspace.id, 0))
            for item in reachable
        ]

    async def get(self, access: OrganizationAccess, slug: str) -> WorkspaceAccess:
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            return await self._gate.require_slug(uow, access, slug, Permission.DOCUMENTS_READ)

    async def create(
        self, access: OrganizationAccess, *, name: str, slug: str, restricted: bool
    ) -> Workspace:
        access.require(Permission.WORKSPACES_MANAGE)
        workspace = Workspace(
            id=new_id(),
            organization_id=access.organization_id,
            slug=validate_slug(slug),
            name=name.strip(),
            created_at=self._clock.now(),
            restricted=restricted,
        )
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            await uow.workspaces.add(workspace)
            await self._audit.record(
                uow,
                access,
                AuditAction.WORKSPACE_CREATED,
                _target(workspace),
                {"slug": workspace.slug, "restricted": restricted},
            )
            await uow.commit()
        return workspace

    async def update(
        self, access: OrganizationAccess, workspace_id: UUID, change: WorkspaceChange
    ) -> Workspace:
        access.require(Permission.WORKSPACES_MANAGE)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            current = await self._existing(uow, workspace_id)
            updated = replace(
                current,
                name=change.name.strip() if change.name is not None else current.name,
                slug=validate_slug(change.slug) if change.slug is not None else current.slug,
                restricted=change.restricted
                if change.restricted is not None
                else current.restricted,
            )
            await uow.workspaces.save(updated)
            details: dict[str, str | bool] = {}
            if updated.name != current.name:
                details["name"] = updated.name
            if updated.slug != current.slug:
                details["slug"] = updated.slug
            if updated.restricted != current.restricted:
                details["restricted"] = updated.restricted
            await self._audit.record(
                uow, access, AuditAction.WORKSPACE_UPDATED, _target(updated), details
            )
            await uow.commit()
        return updated

    async def delete(self, access: OrganizationAccess, workspace_id: UUID) -> None:
        access.require(Permission.WORKSPACES_MANAGE)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            workspace = await self._existing(uow, workspace_id)
            if (await uow.workspaces.document_counts()).get(workspace_id, 0) > 0:
                raise WorkspaceNotEmptyError("move or delete the documents first")
            if len(await uow.workspaces.list()) <= 1:
                raise LastWorkspaceError("an organization keeps at least one workspace")
            await uow.workspaces.delete(workspace_id)
            await self._audit.record(uow, access, AuditAction.WORKSPACE_DELETED, _target(workspace))
            await uow.commit()

    async def members(
        self, access: OrganizationAccess, workspace_id: UUID
    ) -> Sequence[WorkspaceMember]:
        access.require(Permission.WORKSPACES_MANAGE)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            await self._existing(uow, workspace_id)
            return await uow.workspace_members.list_for_workspace(workspace_id)

    async def roles_by_workspace(
        self, access: OrganizationAccess, user_id: UUID
    ) -> Mapping[UUID, str]:
        access.require(Permission.MEMBERS_MANAGE)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            entries = await uow.workspace_members.list_for_user(user_id)
        return {entry.workspace_id: entry.role_code for entry in entries}

    async def set_member(
        self,
        access: OrganizationAccess,
        workspace_id: UUID,
        *,
        user_id: UUID,
        label: str,
        role_code: str,
    ) -> WorkspaceMember:
        access.require(Permission.WORKSPACES_MANAGE)
        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role_code=require_role(self._roles, role_code),
            added_at=self._clock.now(),
        )
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            workspace = await self._existing(uow, workspace_id)
            await uow.workspace_members.put(member)
            await self._audit.record(
                uow,
                access,
                AuditAction.WORKSPACE_MEMBER_SET,
                _target(workspace),
                {"member": label, "role": role_code},
            )
            await uow.commit()
        return member

    async def remove_member(
        self, access: OrganizationAccess, workspace_id: UUID, *, user_id: UUID, label: str
    ) -> None:
        access.require(Permission.WORKSPACES_MANAGE)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            workspace = await self._existing(uow, workspace_id)
            await uow.workspace_members.remove(workspace_id, user_id)
            await self._audit.record(
                uow,
                access,
                AuditAction.WORKSPACE_MEMBER_REMOVED,
                _target(workspace),
                {"member": label},
            )
            await uow.commit()

    @staticmethod
    async def _existing(uow: UnitOfWork, workspace_id: UUID) -> Workspace:
        workspace = await uow.workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceUnavailableError("workspace not found")
        return workspace
