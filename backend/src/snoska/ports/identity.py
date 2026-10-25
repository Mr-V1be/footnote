from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from snoska.domain.shared.errors import DomainError
from snoska.domain.shared.locale import Locale
from snoska.domain.tenancy.access import Principal
from snoska.domain.tenancy.members import Member


class AuthenticationError(DomainError):
    code = "unauthenticated"


class IdentityProviderError(Exception):
    """The identity provider is unreachable or answered unexpectedly."""


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> Principal:
        """Validate signature, issuer, audience and expiry; raise AuthenticationError."""
        ...


@dataclass(frozen=True, slots=True)
class OrganizationProfile:
    id: UUID
    alias: str
    name: str


class OrganizationDirectory(Protocol):
    """Read side of the identity provider's organization registry."""

    async def get_organization(self, organization_id: UUID) -> OrganizationProfile | None: ...

    async def list_members(self, organization_id: UUID) -> Sequence[Member]: ...


@dataclass(frozen=True, slots=True)
class Invitation:
    email: str
    first_name: str
    last_name: str
    role_code: str
    # The language the invitation is written in: the inviter's, the best
    # guess there is about a person who has not signed in yet.
    locale: Locale


class MemberAdministration(Protocol):
    """Changes to an organization's members, made in the identity provider.

    Roles reach a member's token on their next sign-in or token refresh.
    """

    async def invite(self, organization_id: UUID, invitation: Invitation) -> UUID:
        """Create (or reuse) the user, add them with the role, and email them
        a link to set a password. Returns the user's id."""
        ...

    async def set_role(self, organization_id: UUID, user_id: UUID, role_code: str) -> None: ...

    async def remove(self, organization_id: UUID, user_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class MemberSpec:
    email: str
    first_name: str
    last_name: str
    password: str
    role_code: str


class IdentityProvisioning(Protocol):
    """Write side: create organizations, their role groups and members.

    Every operation is idempotent so provisioning can be re-run safely.
    """

    async def ensure_organization(
        self, alias: str, name: str, domain: str
    ) -> OrganizationProfile: ...

    async def ensure_role_groups(
        self, organization_id: UUID, role_codes: tuple[str, ...]
    ) -> None: ...

    async def ensure_member(self, organization_id: UUID, member: MemberSpec) -> UUID: ...

    async def ensure_platform_user(
        self, email: str, first_name: str, last_name: str, password: str, realm_role: str
    ) -> UUID: ...
