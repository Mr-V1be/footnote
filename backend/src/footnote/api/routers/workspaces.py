from __future__ import annotations

from fastapi import APIRouter

from footnote.api.dependencies import ContainerDep, OrganizationAccessDep, PlatformAccessDep
from footnote.api.errors import PROBLEM_RESPONSES
from footnote.api.schemas.tenancy import OrganizationOut, OrganizationPageOut, WorkspaceOut

router = APIRouter(prefix="/v1", tags=["tenancy"], responses=PROBLEM_RESPONSES)

PLATFORM_PAGE_SIZE = 100


@router.get(
    "/organizations/{organization}/workspaces",
    response_model=list[WorkspaceOut],
    response_model_by_alias=True,
)
async def list_workspaces(
    container: ContainerDep, access: OrganizationAccessDep
) -> list[WorkspaceOut]:
    """Workspaces the member reaches, with their role and permissions there."""
    return [WorkspaceOut.of(summary) for summary in await container.workspaces.list(access)]


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
