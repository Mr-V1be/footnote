from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from snoska.api.dependencies import ContainerDep, OrganizationAccessDep
from snoska.api.errors import PROBLEM_RESPONSES
from snoska.api.locale import LocaleDep
from snoska.api.schemas.admin.members import InviteIn, MemberOut, RoleIn
from snoska.domain.tenancy.roles import ORGANIZATION_ROLES
from snoska.ports.identity import Invitation

router = APIRouter(
    prefix="/v1/organizations/{organization}", tags=["admin"], responses=PROBLEM_RESPONSES
)

RANKS = {role.code: role.rank for role in ORGANIZATION_ROLES.all()}


@router.get("/members", response_model=list[MemberOut], response_model_by_alias=True)
async def list_members(container: ContainerDep, access: OrganizationAccessDep) -> list[MemberOut]:
    """Members of the organization with their roles (owners only)."""
    return [MemberOut.of(member, RANKS) for member in await container.members.list(access)]


@router.post(
    "/members",
    response_model=MemberOut,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    container: ContainerDep, access: OrganizationAccessDep, locale: LocaleDep, body: InviteIn
) -> MemberOut:
    """Add a member with a role; a new person gets an email to set a password,
    in the language of the request."""
    member = await container.members.invite(
        access,
        Invitation(
            email=str(body.email),
            first_name=body.first_name.strip(),
            last_name=body.last_name.strip(),
            role_code=body.role,
            locale=locale,
        ),
    )
    return MemberOut.of(member, RANKS)


@router.patch("/members/{user_id}", response_model=MemberOut, response_model_by_alias=True)
async def change_member_role(
    container: ContainerDep, access: OrganizationAccessDep, user_id: UUID, body: RoleIn
) -> MemberOut:
    return MemberOut.of(await container.members.change_role(access, user_id, body.role), RANKS)


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    container: ContainerDep, access: OrganizationAccessDep, user_id: UUID
) -> None:
    await container.members.remove(access, user_id)
