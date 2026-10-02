from __future__ import annotations

from fastapi import APIRouter

from snoska.api.dependencies import ContainerDep, OrganizationAccessDep, PlatformAccessDep
from snoska.api.schemas.tenancy import OrganizationOut, OrganizationPageOut, WorkspaceOut

router = APIRouter(prefix="/v1", tags=["tenancy"])

PLATFORM_PAGE_SIZE = 100


@router.get(
    "/organizations/{organization}/workspaces",
    response_model=list[WorkspaceOut],
    response_model_by_alias=True,
)
async def list_workspaces(
    container: ContainerDep, access: OrganizationAccessDep
) -> list[WorkspaceOut]:
    workspaces = await container.workspaces.list(access)
    return [WorkspaceOut(id=ws.id, slug=ws.slug, name=ws.name) for ws in workspaces]


@router.get(
    "/platform/organizations", response_model=OrganizationPageOut, response_model_by_alias=True
)
async def platform_organizations(
    container: ContainerDep, access: PlatformAccessDep, offset: int = 0
) -> OrganizationPageOut:
    organizations = await container.platform.organizations(
        access, limit=PLATFORM_PAGE_SIZE, offset=max(offset, 0)
    )
    return OrganizationPageOut(
        items=[OrganizationOut(id=o.id, alias=o.alias, name=o.name) for o in organizations]
    )
