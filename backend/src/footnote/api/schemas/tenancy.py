from __future__ import annotations

from uuid import UUID

from footnote.api.schemas.common import ApiModel
from footnote.application.tenancy.workspaces import WorkspaceSummary
from footnote.domain.tenancy.permissions import Permission


class OrganizationOut(ApiModel):
    id: UUID
    alias: str
    name: str


class MembershipOut(ApiModel):
    organization: OrganizationOut
    role: str
    roles: list[str]
    permissions: list[Permission]


class MeOut(ApiModel):
    id: UUID
    email: str | None
    display_name: str
    memberships: list[MembershipOut]
    platform_roles: list[str]
    platform_permissions: list[Permission]


class WorkspaceOut(ApiModel):
    """A workspace the member reaches, with what they may do there."""

    id: UUID
    slug: str
    name: str
    restricted: bool
    documents: int
    role: str
    permissions: list[Permission]

    @classmethod
    def of(cls, summary: WorkspaceSummary) -> WorkspaceOut:
        granted = summary.access
        return cls(
            id=granted.workspace.id,
            slug=granted.workspace.slug,
            name=granted.workspace.name,
            restricted=granted.workspace.restricted,
            documents=summary.documents,
            role=granted.roles[0].code,
            permissions=sorted(granted.permissions),
        )


class OrganizationPageOut(ApiModel):
    items: list[OrganizationOut]
