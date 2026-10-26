from __future__ import annotations

from fastapi import APIRouter

from footnote.api.dependencies import PrincipalDep
from footnote.api.errors import PROBLEM_RESPONSES
from footnote.api.schemas.admin.catalog import AdministrationCatalogOut, RoleOut
from footnote.domain.audit.event import AUDIT_CATEGORIES
from footnote.domain.integrations.api_keys import ApiScope
from footnote.domain.integrations.webhooks import SUBSCRIBABLE_EVENTS
from footnote.domain.tenancy.access import ActorKind
from footnote.domain.tenancy.roles import ORGANIZATION_ROLES

router = APIRouter(prefix="/v1", tags=["admin"], responses=PROBLEM_RESPONSES)


@router.get(
    "/administration/catalog",
    response_model=AdministrationCatalogOut,
    response_model_by_alias=True,
)
async def administration_catalog(_: PrincipalDep) -> AdministrationCatalogOut:
    """Roles, API scopes, webhook events and audit categories, in display order."""
    return AdministrationCatalogOut(
        roles=[RoleOut.of(role) for role in ORGANIZATION_ROLES.all()],
        api_scopes=list(ApiScope),
        webhook_events=list(SUBSCRIBABLE_EVENTS),
        audit_categories=list(AUDIT_CATEGORIES),
        actor_kinds=list(ActorKind),
    )
