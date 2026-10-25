from __future__ import annotations

from fastapi import APIRouter

from snoska.api.dependencies import ContainerDep, PrincipalDep
from snoska.api.errors import PROBLEM_RESPONSES
from snoska.api.locale import StatedLocaleDep
from snoska.api.schemas.catalog import CatalogOut, DocumentFormatOut, DocumentKindOut
from snoska.api.schemas.tenancy import MembershipOut, MeOut, OrganizationOut

router = APIRouter(prefix="/v1", tags=["session"], responses=PROBLEM_RESPONSES)


@router.get("/me", response_model=MeOut, response_model_by_alias=True)
async def me(container: ContainerDep, principal: PrincipalDep, locale: StatedLocaleDep) -> MeOut:
    """The signed-in person, their organizations and roles. The language the
    request states is remembered as theirs, for the mail sent to them."""
    access = container.tenant_access
    await access.sync_profile(principal, locale)
    memberships = await access.memberships(principal)
    platform = access.platform_access(principal)
    return MeOut(
        id=principal.user_id,
        email=principal.email,
        display_name=principal.display_name,
        memberships=[
            MembershipOut(
                organization=OrganizationOut(
                    id=view.organization.id,
                    alias=view.organization.alias,
                    name=view.organization.name,
                ),
                role=view.roles[0].code,
                roles=[role.code for role in view.roles],
                permissions=sorted(view.permissions),
            )
            for view in memberships
        ],
        platform_roles=[role.code for role in platform.roles],
        platform_permissions=sorted(platform.permissions),
    )


@router.get("/catalog", response_model=CatalogOut, response_model_by_alias=True)
async def catalog(container: ContainerDep) -> CatalogOut:
    """Document kinds and formats the product accepts (public)."""
    data = container.catalog.get()
    return CatalogOut(
        kinds=[
            DocumentKindOut(code=kind.code, is_default=kind.code == data.default_kind.code)
            for kind in data.kinds
        ],
        formats=[
            DocumentFormatOut(
                code=fmt.code, media_type=fmt.media_type, extensions=list(fmt.extensions)
            )
            for fmt in data.formats
        ],
        requisite_kinds=list(data.requisite_kinds),
        max_upload_bytes=data.max_upload_bytes,
    )
