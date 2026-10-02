from __future__ import annotations

from uuid import UUID

from snoska.api.schemas.common import ApiModel


class OrganizationOut(ApiModel):
    id: UUID
    alias: str
    name: str


class MembershipOut(ApiModel):
    organization: OrganizationOut
    role: str
    roles: list[str]
    permissions: list[str]


class MeOut(ApiModel):
    id: UUID
    email: str | None
    display_name: str
    memberships: list[MembershipOut]
    platform_roles: list[str]
    platform_permissions: list[str]


class WorkspaceOut(ApiModel):
    id: UUID
    slug: str
    name: str


class OrganizationPageOut(ApiModel):
    items: list[OrganizationOut]
