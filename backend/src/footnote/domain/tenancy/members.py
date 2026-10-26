from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from footnote.domain.shared.errors import ConflictError, NotFoundError, ValidationError
from footnote.domain.tenancy.roles import OWNER_ROLE, RoleCatalog


class UnknownRoleError(ValidationError):
    code = "unknown_role"


class LastOwnerError(ConflictError):
    """An organization always keeps at least one owner."""

    code = "last_owner"


class DemoAccountProtectedError(ConflictError):
    """On the demo stand the accounts of one-click sign-in keep their roles,
    so that every visitor finds them as described."""

    code = "demo_account_protected"


class MemberNotFoundError(NotFoundError):
    code = "member_not_found"


@dataclass(frozen=True, slots=True)
class Member:
    """A member as the identity provider knows them."""

    user_id: UUID
    email: str | None
    first_name: str
    last_name: str
    role_codes: frozenset[str]
    # Invited and not yet signed in (no password set).
    pending: bool = False

    @property
    def display_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or (self.email or str(self.user_id))


def require_role(roles: RoleCatalog, code: str) -> str:
    if roles.get(code) is None:
        raise UnknownRoleError(f"unknown role {code!r}")
    return code


def ensure_owner_remains(members: Sequence[Member], user_id: UUID, *, new_role: str | None) -> None:
    """Refuse to demote or remove the last owner (``new_role`` None = removal)."""
    owners = [member for member in members if OWNER_ROLE in member.role_codes]
    if new_role == OWNER_ROLE or all(member.user_id != user_id for member in owners):
        return
    if len(owners) <= 1:
        raise LastOwnerError("the organization would be left without an owner")


def ensure_not_protected(member: Member, protected_emails: frozenset[str]) -> None:
    if member.email and member.email.casefold() in protected_emails:
        raise DemoAccountProtectedError(f"{member.email} is a demo sign-in account")
