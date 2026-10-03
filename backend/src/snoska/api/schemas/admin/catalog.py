from __future__ import annotations

from snoska.api.schemas.common import ApiModel
from snoska.domain.integrations.api_keys import ApiScope
from snoska.domain.integrations.webhooks import WebhookEvent
from snoska.domain.tenancy.access import ActorKind
from snoska.domain.tenancy.permissions import Permission
from snoska.domain.tenancy.roles import RoleDefinition


class RoleOut(ApiModel):
    code: str
    rank: int
    permissions: list[Permission]

    @classmethod
    def of(cls, role: RoleDefinition) -> RoleOut:
        return cls(code=role.code, rank=role.rank, permissions=sorted(role.permissions))


class AdministrationCatalogOut(ApiModel):
    """Registries the administration screens choose from."""

    roles: list[RoleOut]
    api_scopes: list[ApiScope]
    webhook_events: list[WebhookEvent]
    audit_categories: list[str]
    actor_kinds: list[ActorKind]
