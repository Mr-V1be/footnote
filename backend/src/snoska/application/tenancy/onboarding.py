"""Opening an organization for a customer and the platform's operators."""

from __future__ import annotations

from dataclasses import dataclass

from snoska.domain.tenancy.roles import ORGANIZATION_ROLES, OWNER_ROLE
from snoska.ports.identity import (
    IdentityProvisioning,
    Invitation,
    MemberAdministration,
    OrganizationProfile,
)


@dataclass(frozen=True, slots=True)
class Person:
    email: str
    first_name: str
    last_name: str


class Onboarding:
    """Operations: an organization with its role groups and its owner, who
    gets the same invitation mail as anyone invited from the product and
    sets a password there. Idempotent, like the provisioning beneath it."""

    def __init__(
        self, provisioning: IdentityProvisioning, administration: MemberAdministration
    ) -> None:
        self._provisioning = provisioning
        self._administration = administration

    async def open_organization(
        self, alias: str, name: str, domain: str, owner: Person
    ) -> OrganizationProfile:
        profile = await self._provisioning.ensure_organization(alias, name, domain)
        await self._provisioning.ensure_role_groups(
            profile.id, tuple(role.code for role in ORGANIZATION_ROLES.all())
        )
        await self._administration.invite(
            profile.id,
            Invitation(
                email=owner.email,
                first_name=owner.first_name,
                last_name=owner.last_name,
                role_code=OWNER_ROLE,
            ),
        )
        return profile

    async def add_operator(self, person: Person, password: str, realm_role: str) -> None:
        """A platform operator: sees every tenant, assigns plans, watches the system."""
        await self._provisioning.ensure_platform_user(
            person.email, person.first_name, person.last_name, password, realm_role
        )
