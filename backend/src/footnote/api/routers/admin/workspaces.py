from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from footnote.api.dependencies import ContainerDep, OrganizationAccessDep
from footnote.api.errors import PROBLEM_RESPONSES
from footnote.api.schemas.admin.members import (
    RoleIn,
    WorkspaceIn,
    WorkspaceMemberOut,
    WorkspacePatchIn,
)
from footnote.api.schemas.tenancy import WorkspaceOut
from footnote.application.tenancy.workspaces import WorkspaceChange, WorkspaceSummary

router = APIRouter(
    prefix="/v1/organizations/{organization}/workspaces",
    tags=["admin"],
    responses=PROBLEM_RESPONSES,
)


@router.post(
    "",
    response_model=WorkspaceOut,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    container: ContainerDep, access: OrganizationAccessDep, body: WorkspaceIn
) -> WorkspaceOut:
    workspace = await container.workspaces.create(
        access, name=body.name, slug=body.slug, restricted=body.restricted
    )
    granted = await container.workspaces.get(access, workspace.slug)
    return WorkspaceOut.of(WorkspaceSummary(access=granted, documents=0))


@router.patch("/{workspace_id}", response_model=WorkspaceOut, response_model_by_alias=True)
async def update_workspace(
    container: ContainerDep,
    access: OrganizationAccessDep,
    workspace_id: UUID,
    body: WorkspacePatchIn,
) -> WorkspaceOut:
    updated = await container.workspaces.update(
        access,
        workspace_id,
        WorkspaceChange(name=body.name, slug=body.slug, restricted=body.restricted),
    )
    summaries = await container.workspaces.list(access)
    summary = next(item for item in summaries if item.access.workspace.id == updated.id)
    return WorkspaceOut.of(summary)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    container: ContainerDep, access: OrganizationAccessDep, workspace_id: UUID
) -> None:
    await container.workspaces.delete(access, workspace_id)


@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMemberOut],
    response_model_by_alias=True,
)
async def workspace_members(
    container: ContainerDep, access: OrganizationAccessDep, workspace_id: UUID
) -> list[WorkspaceMemberOut]:
    """Members given a role of their own in the workspace."""
    return [
        WorkspaceMemberOut.of(member)
        for member in await container.workspaces.members(access, workspace_id)
    ]


@router.put(
    "/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberOut,
    response_model_by_alias=True,
)
async def set_workspace_member(
    container: ContainerDep,
    access: OrganizationAccessDep,
    workspace_id: UUID,
    user_id: UUID,
    body: RoleIn,
) -> WorkspaceMemberOut:
    members = {member.user_id: member for member in await container.members.list(access)}
    label = members[user_id].display_name if user_id in members else str(user_id)
    member = await container.workspaces.set_member(
        access, workspace_id, user_id=user_id, label=label, role_code=body.role
    )
    return WorkspaceMemberOut.of(member)


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_workspace_member(
    container: ContainerDep, access: OrganizationAccessDep, workspace_id: UUID, user_id: UUID
) -> None:
    members = {member.user_id: member for member in await container.members.list(access)}
    label = members[user_id].display_name if user_id in members else str(user_id)
    await container.workspaces.remove_member(access, workspace_id, user_id=user_id, label=label)
