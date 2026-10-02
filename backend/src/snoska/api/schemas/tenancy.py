from __future__ import annotations

from uuid import UUID

from snoska.api.schemas.common import ApiModel
from snoska.domain.tenancy.permissions import Permission


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
    id: UUID
    slug: str
    name: str


class OrganizationPageOut(ApiModel):
    items: list[OrganizationOut]
