from __future__ import annotations

from dataclasses import dataclass

from footnote.domain.shared.errors import NotFoundError
from footnote.domain.shared.ids import new_id
from footnote.domain.shared.locale import Locale
from footnote.domain.tenancy.access import (
    AccessPolicy,
    MembershipClaim,
    MissingPermissionError,
    NotAMemberError,
    OrganizationAccess,
    PlatformAccess,
    Principal,
)
from footnote.domain.tenancy.organization import Organization, Workspace
from footnote.domain.tenancy.permissions import Permission
from footnote.domain.tenancy.roles import RoleDefinition
from footnote.ports.clock import Clock
from footnote.ports.identity import AuthenticationError, OrganizationDirectory
from footnote.ports.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class DefaultWorkspace:
    """The workspace every new organization starts with."""

    slug: str
    name: str


@dataclass(frozen=True, slots=True)
class MembershipView:
    organization: Organization
    roles: tuple[RoleDefinition, ...]

    @property
    def permissions(self) -> frozenset[Permission]:
        granted: frozenset[Permission] = frozenset()
        for role in self.roles:
            granted |= role.permissions
        return granted


class OrganizationUnavailableError(NotFoundError):
    code = "organization_unavailable"


class TenantAccessService:
    """Resolves what a verified principal may do and in which tenant.

    Organizations are owned by the identity provider. The first time a member
    of a new organization arrives, the tenant record and its default
    workspace are provisioned in one transaction.
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        directory: OrganizationDirectory,
        policy: AccessPolicy,
        clock: Clock,
        default_workspace: DefaultWorkspace,
    ) -> None:
        self._uow_factory = uow_factory
        self._directory = directory
        self._policy = policy
        self._clock = clock
        self._default_workspace = default_workspace

    async def organization_access(self, principal: Principal, alias: str) -> OrganizationAccess:
        membership = principal.membership_by_alias(alias)
        if membership is None:
            raise NotAMemberError(f"not a member of organization {alias!r}")
        organization = await self._ensure_tenant(membership)
        return self._policy.organization_access(principal, organization)

    async def organization_by_alias(self, alias: str) -> Organization:
        """A provisioned tenant by its alias (for requests made with an API key)."""
        async with self._uow_factory.for_platform() as uow:
            organization = await uow.organizations.get_by_alias(alias)
        if organization is None:
            raise AuthenticationError("unknown organization")
        return organization

    def platform_access(self, principal: Principal) -> PlatformAccess:
        return self._policy.platform_access(principal)

    def holds_anywhere(self, principal: Principal, permission: Permission) -> bool:
        if permission in self._policy.platform_access(principal).permissions:
            return True
        return any(
            permission in role.permissions
            for membership in principal.memberships
            for role in self._policy.roles_of(membership)
        )

    def require_anywhere(self, principal: Principal, permission: Permission) -> None:
        """For platform-wide resources (the corpus): any membership may grant it."""
        if not self.holds_anywhere(principal, permission):
            raise MissingPermissionError(f"permission {permission} is required")

    async def memberships(self, principal: Principal) -> list[MembershipView]:
        views: list[MembershipView] = []
        for membership in principal.memberships:
            roles = self._policy.roles_of(membership)
            if not roles:
                continue
            organization = await self._ensure_tenant(membership)
            views.append(MembershipView(organization=organization, roles=roles))
        return sorted(views, key=lambda view: view.organization.name.casefold())

    async def sync_profile(self, principal: Principal, locale: Locale | None = None) -> None:
        """Keep the person's display data as their token gives it, and the
        interface language they use when the request states one."""
        async with self._uow_factory.for_platform() as uow:
            await uow.profiles.upsert(principal.profile, self._clock.now())
            if locale is not None:
                await uow.profiles.remember_locale(principal.user_id, locale)
            await uow.commit()

    async def _ensure_tenant(self, membership: MembershipClaim) -> Organization:
        async with self._uow_factory.for_platform() as uow:
            existing = await uow.organizations.get(membership.organization_id)
        if existing is not None:
            return existing
        profile = await self._directory.get_organization(membership.organization_id)
        if profile is None:
            raise OrganizationUnavailableError(
                "organization is not registered with the identity provider"
            )
        now = self._clock.now()
        organization = Organization(
            id=profile.id, alias=profile.alias, name=profile.name, created_at=now
        )
        async with self._uow_factory.for_tenant(organization.id) as uow:
            await uow.organizations.add_if_absent(organization)
            await uow.workspaces.add_if_absent(
                Workspace(
                    id=new_id(),
                    organization_id=organization.id,
                    slug=self._default_workspace.slug,
                    name=self._default_workspace.name,
                    created_at=now,
                )
            )
            await uow.commit()
        async with self._uow_factory.for_platform() as uow:
            stored = await uow.organizations.get(organization.id)
        if stored is None:
            raise OrganizationUnavailableError("organization could not be provisioned")
        return stored
