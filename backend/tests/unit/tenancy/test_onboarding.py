"""An organization is opened with every role group and its owner invited."""

from __future__ import annotations

from uuid import UUID, uuid4

from snoska.application.tenancy.onboarding import Onboarding, Person
from snoska.domain.tenancy.roles import ORGANIZATION_ROLES
from snoska.ports.identity import Invitation, MemberSpec, OrganizationProfile


class RecordingIdentity:
    def __init__(self) -> None:
        self.organizations: dict[str, OrganizationProfile] = {}
        self.domains: dict[str, str] = {}
        self.groups: dict[UUID, tuple[str, ...]] = {}
        self.invited: list[tuple[UUID, Invitation]] = []
        self.operators: list[tuple[str, str]] = []

    async def ensure_organization(self, alias: str, name: str, domain: str) -> OrganizationProfile:
        self.domains[alias] = domain
        return self.organizations.setdefault(alias, OrganizationProfile(uuid4(), alias, name))

    async def ensure_role_groups(self, organization_id: UUID, role_codes: tuple[str, ...]) -> None:
        self.groups[organization_id] = role_codes

    async def ensure_member(self, organization_id: UUID, member: MemberSpec) -> UUID:
        raise AssertionError(f"{member.email} in {organization_id}: invited, not given a password")

    async def ensure_platform_user(
        self, email: str, first_name: str, last_name: str, password: str, realm_role: str
    ) -> UUID:
        self.operators.append((email, realm_role))
        self.names = (first_name, last_name, bool(password))
        return uuid4()

    async def invite(self, organization_id: UUID, invitation: Invitation) -> UUID:
        self.invited.append((organization_id, invitation))
        return uuid4()

    async def set_role(self, organization_id: UUID, user_id: UUID, role_code: str) -> None:
        raise AssertionError(f"no role change expected: {organization_id} {user_id} {role_code}")

    async def remove(self, organization_id: UUID, user_id: UUID) -> None:
        raise AssertionError(f"no removal expected: {organization_id} {user_id}")


OWNER = Person("ivanova@romashka.example", "Мария", "Иванова")


async def test_an_organization_opens_with_its_groups_and_an_invited_owner() -> None:
    identity = RecordingIdentity()
    onboarding = Onboarding(identity, identity)
    profile = await onboarding.open_organization(
        "romashka", "ООО «Ромашка»", "romashka.example", OWNER
    )
    assert set(identity.groups[profile.id]) == {role.code for role in ORGANIZATION_ROLES.all()}
    [(organization, invitation)] = identity.invited
    assert (organization, invitation.email, invitation.role_code) == (
        profile.id,
        OWNER.email,
        "owner",
    )


async def test_an_operator_gets_the_platform_role() -> None:
    identity = RecordingIdentity()
    await Onboarding(identity, identity).add_operator(OWNER, "secret", "platform-admin")
    assert identity.operators == [(OWNER.email, "platform-admin")]
