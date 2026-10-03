from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from snoska.domain.shared.errors import NotFoundError
from snoska.domain.tenancy.access import MissingPermissionError, OrganizationAccess
from snoska.domain.tenancy.organization import Workspace
from snoska.domain.tenancy.permissions import Permission
from snoska.domain.tenancy.roles import RoleDefinition


class WorkspaceUnavailableError(NotFoundError):
    """The workspace does not exist for this member: missing or restricted.
    Both look the same, so a restricted workspace does not reveal itself."""

    code = "workspace_not_found"


@dataclass(frozen=True, slots=True)
class WorkspaceMember:
    """A member given a role inside one workspace, apart from their
    organization role: lower (an observer here) or higher (a lawyer here)."""

    workspace_id: UUID
    user_id: UUID
    role_code: str
    added_at: datetime


@dataclass(frozen=True, slots=True)
class WorkspaceAccess:
    """What a member may do inside one workspace."""

    workspace: Workspace
    roles: tuple[RoleDefinition, ...]

    @property
    def permissions(self) -> frozenset[Permission]:
        granted: frozenset[Permission] = frozenset()
        for role in self.roles:
            granted |= role.permissions
        return granted

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions

    def require(self, permission: Permission) -> None:
        if not self.can(permission):
            raise MissingPermissionError(f"permission {permission} is required here")


def workspace_access(
    access: OrganizationAccess, workspace: Workspace, member_role: RoleDefinition | None
) -> WorkspaceAccess:
    """The roles a member holds in a workspace.

    Whoever administers workspaces sees them all with their own role. A role
    given in the workspace replaces the organization role there. Otherwise an
    open workspace takes the organization role and a restricted one is closed.
    """
    if access.can(Permission.WORKSPACES_MANAGE):
        return WorkspaceAccess(workspace=workspace, roles=access.roles)
    if member_role is not None:
        return WorkspaceAccess(workspace=workspace, roles=(member_role,))
    if not workspace.restricted:
        return WorkspaceAccess(workspace=workspace, roles=access.roles)
    raise WorkspaceUnavailableError(f"workspace {workspace.slug!r} not found")
