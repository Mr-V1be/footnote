from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from snoska.api.dependencies import ActorProfileDep, ContainerDep, OrganizationAccessDep
from snoska.api.errors import PROBLEM_RESPONSES
from snoska.api.locale import LocaleDep
from snoska.api.schemas.autofix import AutofixOut, AutofixPreviewOut, ChangeOut

router = APIRouter(
    prefix="/v1/organizations/{organization}/documents/{document_id}/versions/{number}",
    tags=["autofix"],
    responses=PROBLEM_RESPONSES,
)


@router.get("/autofix", response_model=AutofixPreviewOut, response_model_by_alias=True)
async def autofix_preview(
    container: ContainerDep, access: OrganizationAccessDep, document_id: UUID, number: int
) -> AutofixPreviewOut:
    """What an automatic correction of the version's formatting would change."""
    return AutofixPreviewOut.of(await container.autofix.preview(access, document_id, number))


@router.post(
    "/autofix",
    response_model=AutofixOut,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def apply_autofix(
    container: ContainerDep,
    access: OrganizationAccessDep,
    author: ActorProfileDep,
    locale: LocaleDep,
    document_id: UUID,
    number: int,
) -> AutofixOut:
    """Correct the formatting into a new version; this one stays as it is."""
    return AutofixOut.of(await container.autofix.apply(access, author, document_id, number, locale))


@router.get("/changes", response_model=list[ChangeOut], response_model_by_alias=True)
async def version_changes(
    container: ContainerDep, access: OrganizationAccessDep, document_id: UUID, number: int
) -> list[ChangeOut]:
    """What the correction that made this version changed (before and after)."""
    return [
        ChangeOut.of(change)
        for change in await container.autofix.changes(access, document_id, number)
    ]
