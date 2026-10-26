from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from footnote.domain.tenancy.permissions import Permission


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    """A role as granted by the identity provider and what it allows.

    ``rank`` orders roles from the most to the least privileged; it is used
    only to present a primary role when a member holds several.
    """

    code: str
    rank: int
    permissions: frozenset[Permission]


class RoleCatalog:
    """Registry of known roles. Unknown role codes are ignored, never trusted."""

    def __init__(self, roles: Iterable[RoleDefinition]) -> None:
        self._roles = {role.code: role for role in roles}

    def get(self, code: str) -> RoleDefinition | None:
        return self._roles.get(code)

    def resolve(self, codes: Iterable[str]) -> tuple[RoleDefinition, ...]:
        found = (self._roles[code] for code in set(codes) if code in self._roles)
        return tuple(sorted(found, key=lambda role: role.rank))

    def all(self) -> tuple[RoleDefinition, ...]:
        return tuple(sorted(self._roles.values(), key=lambda role: role.rank))


_READER = frozenset({Permission.DOCUMENTS_READ, Permission.CORPUS_READ})
_EXECUTOR = _READER | {
    Permission.DOCUMENTS_UPLOAD,
    Permission.CHECKS_RUN,
    Permission.FINDINGS_RESOLVE,
    Permission.NORMS_ASK,
}
_LAWYER = _EXECUTOR | {Permission.FINDINGS_DECIDE, Permission.AUDIT_READ, Permission.BILLING_READ}
_OWNER = _LAWYER | {
    Permission.MEMBERS_MANAGE,
    Permission.WORKSPACES_MANAGE,
    Permission.INTEGRATIONS_MANAGE,
    Permission.BILLING_MANAGE,
}

# The role that administers the organization and reaches every workspace.
OWNER_ROLE = "owner"

ORGANIZATION_ROLES = RoleCatalog(
    [
        RoleDefinition(code=OWNER_ROLE, rank=0, permissions=_OWNER),
        RoleDefinition(code="lawyer", rank=1, permissions=_LAWYER),
        RoleDefinition(code="executor", rank=2, permissions=_EXECUTOR),
        RoleDefinition(code="observer", rank=3, permissions=_READER),
    ]
)

PLATFORM_ROLES = RoleCatalog(
    [
        RoleDefinition(
            code="platform-admin",
            rank=0,
            permissions=frozenset(
                {
                    Permission.PLATFORM_TENANTS_READ,
                    Permission.PLATFORM_PLANS_MANAGE,
                    Permission.PLATFORM_SYSTEM_READ,
                    Permission.CORPUS_READ,
                }
            ),
        ),
    ]
)
