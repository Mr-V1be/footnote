from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from footnote.application.audit.trail import AuditTrail
from footnote.domain.audit.event import AuditAction, AuditTarget
from footnote.domain.integrations.api_keys import (
    ApiKey,
    ApiScope,
    InvalidApiKeyError,
    IssuedKey,
    issue_key,
    prefix_of,
)
from footnote.domain.shared.errors import NotFoundError
from footnote.domain.shared.ids import new_id
from footnote.domain.tenancy.access import Actor, ActorKind, OrganizationAccess
from footnote.domain.tenancy.organization import Organization
from footnote.domain.tenancy.permissions import Permission
from footnote.domain.tenancy.roles import RoleDefinition
from footnote.ports.clock import Clock
from footnote.ports.identity import AuthenticationError
from footnote.ports.unit_of_work import UnitOfWorkFactory

# Ranked after every member role: a key is never anyone's "primary" role.
KEY_ROLE_RANK = 100


class ApiKeyNotFoundError(NotFoundError):
    code = "api_key_not_found"


def _target(key: ApiKey) -> AuditTarget:
    return AuditTarget(type="api_key", id=str(key.id), label=f"{key.name} ({key.prefix}…)")


class ApiKeys:
    """Keys integrations use to call the API on the organization's behalf."""

    def __init__(self, uow_factory: UnitOfWorkFactory, audit: AuditTrail, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._audit = audit
        self._clock = clock

    async def list(self, access: OrganizationAccess) -> Sequence[ApiKey]:
        access.require(Permission.INTEGRATIONS_MANAGE)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            return await uow.api_keys.list()

    async def create(
        self, access: OrganizationAccess, *, name: str, scopes: frozenset[ApiScope]
    ) -> IssuedKey:
        access.require(Permission.INTEGRATIONS_MANAGE)
        issued = issue_key(
            id=new_id(),
            organization_id=access.organization_id,
            name=name,
            scopes=scopes,
            created_by=access.user_id,
            created_by_label=access.actor.label,
            now=self._clock.now(),
        )
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            await uow.api_keys.add(issued.key)
            await self._audit.record(
                uow,
                access,
                AuditAction.API_KEY_CREATED,
                _target(issued.key),
                {"scopes": ",".join(sorted(scope.value for scope in scopes))},
            )
            await uow.commit()
        return issued

    async def revoke(self, access: OrganizationAccess, key_id: UUID) -> ApiKey:
        access.require(Permission.INTEGRATIONS_MANAGE)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            key = await uow.api_keys.get(key_id)
            if key is None:
                raise ApiKeyNotFoundError("API key not found")
            key.revoke(self._clock.now())
            await uow.api_keys.save(key)
            await self._audit.record(uow, access, AuditAction.API_KEY_REVOKED, _target(key))
            await uow.commit()
        return key

    async def authenticate(self, token: str, organization: Organization) -> OrganizationAccess:
        """The access a request with this token has in the organization."""
        prefix = prefix_of(token)
        if prefix is None:
            raise AuthenticationError("not an API key")
        async with self._uow_factory.for_tenant(organization.id) as uow:
            key = await uow.api_keys.find_by_prefix(prefix)
            if key is None or not key.matches(token) or not key.active:
                raise AuthenticationError("the API key is invalid or revoked")
            if key.note_use(self._clock.now()):
                await uow.api_keys.save(key)
                await uow.commit()
        role = RoleDefinition(code="api_key", rank=KEY_ROLE_RANK, permissions=key.permissions)
        return OrganizationAccess(
            organization=organization,
            user_id=key.id,
            roles=(role,),
            actor=Actor(ActorKind.API_KEY, key.id, f"{key.name} ({key.prefix}…)"),
        )


__all__ = ["ApiKeyNotFoundError", "ApiKeys", "InvalidApiKeyError"]
