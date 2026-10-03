from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from snoska.domain.shared.errors import AccessDeniedError
from snoska.domain.tenancy.organization import Organization, UserProfile
from snoska.domain.tenancy.permissions import Permission
from snoska.domain.tenancy.roles import RoleCatalog, RoleDefinition


class NotAMemberError(AccessDeniedError):
    code = "not_a_member"


class MissingPermissionError(AccessDeniedError):
    code = "missing_permission"


class ActorKind(StrEnum):
    USER = "user"
    API_KEY = "api_key"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class Actor:
    """Who acts: a member, an integration's API key or the platform itself.
    ``label`` is the name shown in the audit log as it was at the time."""

    kind: ActorKind
    id: UUID | None
    label: str


SYSTEM_ACTOR = Actor(kind=ActorKind.SYSTEM, id=None, label="system")


@dataclass(frozen=True, slots=True)
class MembershipClaim:
    """Organization membership asserted by a verified identity token."""

    organization_id: UUID
    organization_alias: str
    role_codes: frozenset[str]


@dataclass(frozen=True, slots=True)
class Principal:
    """An authenticated subject. Built only from a verified token."""

    user_id: UUID
    email: str | None
    display_name: str
    memberships: tuple[MembershipClaim, ...]
    platform_role_codes: frozenset[str]

    def membership_in(self, organization_id: UUID) -> MembershipClaim | None:
        return next(
            (m for m in self.memberships if m.organization_id == organization_id),
            None,
        )

    def membership_by_alias(self, alias: str) -> MembershipClaim | None:
        return next((m for m in self.memberships if m.organization_alias == alias), None)

    @property
    def profile(self) -> UserProfile:
        return UserProfile(id=self.user_id, email=self.email, display_name=self.display_name)


def _permissions_of(roles: tuple[RoleDefinition, ...]) -> frozenset[Permission]:
    granted: frozenset[Permission] = frozenset()
    for role in roles:
        granted |= role.permissions
    return granted


@dataclass(frozen=True, slots=True)
class OrganizationAccess:
    """What a principal may do inside one organization.

    ``user_id`` is the member, or for an API key the key itself; ``actor``
    names either for the audit log.
    """

    organization: Organization
    user_id: UUID
    roles: tuple[RoleDefinition, ...]
    actor: Actor

    @property
    def organization_id(self) -> UUID:
        return self.organization.id

    @property
    def primary_role(self) -> RoleDefinition:
        return self.roles[0]

    @property
    def permissions(self) -> frozenset[Permission]:
        return _permissions_of(self.roles)

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions

    def require(self, permission: Permission) -> None:
        if not self.can(permission):
            raise MissingPermissionError(f"permission {permission} is required")


@dataclass(frozen=True, slots=True)
class PlatformAccess:
    user_id: UUID
    roles: tuple[RoleDefinition, ...]
    display_name: str = ""

    @property
    def actor(self) -> Actor:
        return Actor(ActorKind.USER, self.user_id, self.display_name or "platform")

    @property
    def permissions(self) -> frozenset[Permission]:
        return _permissions_of(self.roles)

    def require(self, permission: Permission) -> None:
        if permission not in self.permissions:
            raise MissingPermissionError(f"permission {permission} is required")


class AccessPolicy:
    """Turns token claims into access grants using the role registries."""

    def __init__(self, organization_roles: RoleCatalog, platform_roles: RoleCatalog) -> None:
        self._organization_roles = organization_roles
        self._platform_roles = platform_roles

    def organization_access(
        self, principal: Principal, organization: Organization
    ) -> OrganizationAccess:
        membership = principal.membership_in(organization.id)
        if membership is None:
            raise NotAMemberError("principal is not a member of the organization")
        roles = self._organization_roles.resolve(membership.role_codes)
        if not roles:
            raise NotAMemberError("principal holds no recognised role in the organization")
        return OrganizationAccess(
            organization=organization,
            user_id=principal.user_id,
            roles=roles,
            actor=Actor(ActorKind.USER, principal.user_id, principal.display_name),
        )

    def roles_of(self, membership: MembershipClaim) -> tuple[RoleDefinition, ...]:
        return self._organization_roles.resolve(membership.role_codes)

    def platform_access(self, principal: Principal) -> PlatformAccess:
        return PlatformAccess(
            user_id=principal.user_id,
            roles=self._platform_roles.resolve(principal.platform_role_codes),
            display_name=principal.display_name,
        )
