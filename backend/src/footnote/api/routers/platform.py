from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from footnote.api.dependencies import ContainerDep, PlatformAccessDep
from footnote.api.errors import PROBLEM_RESPONSES
from footnote.api.locale import LocaleDep
from footnote.api.schemas.platform import OrganizationRowOut, PlanAssignIn, PlanOut, SystemOut
from footnote.application.operations.platform import CORPUS_WATCH
from footnote.domain.tenancy.permissions import Permission

router = APIRouter(prefix="/v1/platform", tags=["platform"], responses=PROBLEM_RESPONSES)


@router.get(
    "/organizations/overview",
    response_model=list[OrganizationRowOut],
    response_model_by_alias=True,
)
async def platform_overview(
    container: ContainerDep, access: PlatformAccessDep
) -> list[OrganizationRowOut]:
    """Organizations with their plans and this month's usage (no tenant data)."""
    return [OrganizationRowOut.of(item) for item in await container.console.organizations(access)]


@router.get("/plans", response_model=list[PlanOut], response_model_by_alias=True)
async def platform_plans(container: ContainerDep, access: PlatformAccessDep) -> list[PlanOut]:
    return [PlanOut.of(plan) for plan in container.console.plans(access)]


@router.put("/organizations/{organization_id}/plan", status_code=status.HTTP_204_NO_CONTENT)
async def assign_plan(
    container: ContainerDep, access: PlatformAccessDep, organization_id: UUID, body: PlanAssignIn
) -> None:
    """Move an organization to a plan at once (recorded in its audit log)."""
    await container.console.assign_plan(access, organization_id, body.plan)


@router.get("/system", response_model=SystemOut, response_model_by_alias=True)
async def system_status(
    container: ContainerDep, access: PlatformAccessDep, locale: LocaleDep
) -> SystemOut:
    """Health of dependencies, models, the corpus and its weekly check."""
    return SystemOut.of(await container.console.system(access), locale)


@router.post("/corpus/watch", status_code=status.HTTP_202_ACCEPTED)
async def run_corpus_watch(container: ContainerDep, access: PlatformAccessDep) -> None:
    """Check the official portal for new redactions now."""
    access.require(Permission.PLATFORM_SYSTEM_READ)
    await container.scheduler.run_now(CORPUS_WATCH)
