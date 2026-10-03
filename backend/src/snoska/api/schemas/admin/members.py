from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from snoska.api.schemas.common import ApiModel
from snoska.domain.tenancy.members import Member
from snoska.domain.tenancy.workspace_access import WorkspaceMember


class MemberWorkspaceRoleOut(ApiModel):
    workspace_id: UUID
    role: str


class MemberOut(ApiModel):
    user_id: UUID
    email: str | None
    first_name: str
    last_name: str
    display_name: str
    role: str | None
    # Invited, has not set a password yet.
    pending: bool

    @classmethod
    def of(cls, member: Member, ranked: Mapping[str, int]) -> MemberOut:
        roles = sorted(member.role_codes, key=lambda code: ranked.get(code, 99))
        return cls(
            user_id=member.user_id,
            email=member.email,
            first_name=member.first_name,
            last_name=member.last_name,
            display_name=member.display_name,
            role=roles[0] if roles else None,
            pending=member.pending,
        )


class InviteIn(ApiModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=40)


class RoleIn(ApiModel):
    role: str = Field(min_length=1, max_length=40)


class WorkspaceIn(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=63, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    restricted: bool = False


class WorkspacePatchIn(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(
        default=None, min_length=1, max_length=63, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    restricted: bool | None = None


class WorkspaceMemberOut(ApiModel):
    user_id: UUID
    role: str
    added_at: datetime

    @classmethod
    def of(cls, member: WorkspaceMember) -> WorkspaceMemberOut:
        return cls(user_id=member.user_id, role=member.role_code, added_at=member.added_at)
