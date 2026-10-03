from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from snoska.domain.shared.errors import InvalidStateError, ValidationError
from snoska.domain.tenancy.permissions import Permission

# Tokens read "snk_" + a public prefix that finds the key + the secret part.
TOKEN_MARKER = "snk_"  # noqa: S105 - a format marker, not a secret
PREFIX_LENGTH = 10
SECRET_BYTES = 30
NAME_MAX_LENGTH = 80
# A key's "last used" moment is refreshed at most this often.
USAGE_RESOLUTION = timedelta(minutes=1)


class ApiScope(StrEnum):
    """What an integration may do with the organization's data."""

    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_WRITE = "documents:write"
    CHECKS_RUN = "checks:run"
    AUDIT_READ = "audit:read"


SCOPE_PERMISSIONS: Mapping[ApiScope, frozenset[Permission]] = {
    ApiScope.DOCUMENTS_READ: frozenset({Permission.DOCUMENTS_READ}),
    ApiScope.DOCUMENTS_WRITE: frozenset({Permission.DOCUMENTS_READ, Permission.DOCUMENTS_UPLOAD}),
    ApiScope.CHECKS_RUN: frozenset({Permission.DOCUMENTS_READ, Permission.CHECKS_RUN}),
    ApiScope.AUDIT_READ: frozenset({Permission.AUDIT_READ}),
}


class InvalidApiKeyError(ValidationError):
    code = "invalid_api_key"


class ApiKeyRevokedError(InvalidStateError):
    code = "api_key_revoked"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def prefix_of(token: str) -> str | None:
    """The public part of a token, or None when it is not one of ours."""
    if not token.startswith(TOKEN_MARKER):
        return None
    body = token[len(TOKEN_MARKER) :]
    return body[:PREFIX_LENGTH] if len(body) > PREFIX_LENGTH else None


@dataclass(slots=True)
class ApiKey:
    """An organization's key for an integration.

    Only a hash of the token is kept; the token itself is shown once, when
    the key is created. A revoked key stays listed, for the audit trail.
    """

    id: UUID
    organization_id: UUID
    name: str
    prefix: str
    token_hash: str
    scopes: frozenset[ApiScope]
    created_by: UUID
    created_by_label: str
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    revision: int = field(default=0)

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name or len(self.name) > NAME_MAX_LENGTH:
            raise ValidationError(f"a key's name is 1-{NAME_MAX_LENGTH} characters")
        if not self.scopes:
            raise ValidationError("a key grants at least one scope")

    @property
    def active(self) -> bool:
        return self.revoked_at is None

    @property
    def permissions(self) -> frozenset[Permission]:
        granted: frozenset[Permission] = frozenset()
        for scope in self.scopes:
            granted |= SCOPE_PERMISSIONS[scope]
        return granted

    def matches(self, token: str) -> bool:
        return hmac.compare_digest(self.token_hash, hash_token(token))

    def revoke(self, now: datetime) -> None:
        if self.revoked_at is not None:
            raise ApiKeyRevokedError("the key is already revoked")
        self.revoked_at = now

    def note_use(self, now: datetime) -> bool:
        """Record a use; True when the moment changed enough to be saved."""
        if self.last_used_at is not None and now - self.last_used_at < USAGE_RESOLUTION:
            return False
        self.last_used_at = now
        return True


@dataclass(frozen=True, slots=True)
class IssuedKey:
    key: ApiKey
    # The only time the token exists outside the caller's hands.
    token: str


def issue_key(
    *,
    id: UUID,
    organization_id: UUID,
    name: str,
    scopes: frozenset[ApiScope],
    created_by: UUID,
    created_by_label: str,
    now: datetime,
) -> IssuedKey:
    while True:
        body = secrets.token_urlsafe(SECRET_BYTES).replace("-", "x").replace("_", "y")
        if len(body) > PREFIX_LENGTH:
            break
    token = f"{TOKEN_MARKER}{body}"
    key = ApiKey(
        id=id,
        organization_id=organization_id,
        name=name,
        prefix=body[:PREFIX_LENGTH],
        token_hash=hash_token(token),
        scopes=scopes,
        created_by=created_by,
        created_by_label=created_by_label,
        created_at=now,
    )
    return IssuedKey(key=key, token=token)
