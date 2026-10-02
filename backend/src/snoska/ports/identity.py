from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from snoska.domain.shared.errors import DomainError
from snoska.domain.tenancy.access import Principal


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
