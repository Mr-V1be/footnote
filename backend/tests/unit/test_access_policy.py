from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from snoska.domain.tenancy.access import (
    AccessPolicy,
    MembershipClaim,
    MissingPermissionError,
    NotAMemberError,
    Principal,
)
from snoska.domain.tenancy.organization import Organization
from snoska.domain.tenancy.permissions import Permission
from snoska.domain.tenancy.roles import ORGANIZATION_ROLES, PLATFORM_ROLES

POLICY = AccessPolicy(ORGANIZATION_ROLES, PLATFORM_ROLES)
ORG = Organization(id=uuid4(), alias="acme", name="Acme", created_at=datetime.now(UTC))


def principal(
    *roles: str, organization: Organization = ORG, platform: tuple[str, ...] = ()
) -> Principal:
    return Principal(
        user_id=uuid4(),
        email="user@acme.example",
        display_name="User",
        memberships=(
            MembershipClaim(
                organization_id=organization.id,
                organization_alias=organization.alias,
                role_codes=frozenset(roles),
            ),
        ),
        platform_role_codes=frozenset(platform),
    )


@pytest.mark.parametrize(
    ("role", "can_upload"),
    [("owner", True), ("lawyer", True), ("executor", True), ("observer", False)],
)
def test_roles_grant_expected_permissions(role: str, can_upload: bool) -> None:
    access = POLICY.organization_access(principal(role), ORG)
    assert access.can(Permission.DOCUMENTS_READ)
    assert access.can(Permission.DOCUMENTS_UPLOAD) is can_upload


def test_observer_upload_is_refused_with_stable_code() -> None:
    access = POLICY.organization_access(principal("observer"), ORG)
    with pytest.raises(MissingPermissionError) as error:
        access.require(Permission.DOCUMENTS_UPLOAD)
    assert error.value.code == "missing_permission"


def test_member_of_another_organization_is_not_granted_access() -> None:
    other = Organization(id=uuid4(), alias="other", name="Other", created_at=datetime.now(UTC))
    with pytest.raises(NotAMemberError):
        POLICY.organization_access(principal("owner", organization=other), ORG)


def test_unknown_roles_are_ignored_not_trusted() -> None:
    with pytest.raises(NotAMemberError):
        POLICY.organization_access(principal("superuser"), ORG)


def test_highest_ranked_role_is_primary_and_permissions_merge() -> None:
    access = POLICY.organization_access(principal("observer", "lawyer"), ORG)
    assert access.primary_role.code == "lawyer"
    assert access.can(Permission.DOCUMENTS_UPLOAD)


def test_platform_role_grants_platform_permissions_only() -> None:
    access = POLICY.platform_access(principal("observer", platform=("platform-admin",)))
    assert Permission.PLATFORM_TENANTS_READ in access.permissions
    plain = POLICY.platform_access(principal("owner"))
    with pytest.raises(MissingPermissionError):
        plain.require(Permission.PLATFORM_TENANTS_READ)
