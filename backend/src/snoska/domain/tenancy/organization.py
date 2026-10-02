from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from snoska.domain.shared.errors import ValidationError

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG_MAX_LENGTH = 63
NAME_MAX_LENGTH = 200


class InvalidSlugError(ValidationError):
    code = "invalid_slug"


def validate_slug(value: str) -> str:
    if len(value) > SLUG_MAX_LENGTH or not _SLUG.fullmatch(value):
        raise InvalidSlugError(f"invalid slug: {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class Organization:
    """A tenant. Its identity and membership are owned by the identity provider;
    the platform keeps the record that tenant data hangs off."""

    id: UUID
    alias: str
    name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Workspace:
    id: UUID
    organization_id: UUID
    slug: str
    name: str
    created_at: datetime

    def __post_init__(self) -> None:
        validate_slug(self.slug)
        if not self.name.strip() or len(self.name) > NAME_MAX_LENGTH:
            raise ValidationError("workspace name must be 1-200 characters")


@dataclass(frozen=True, slots=True)
class UserProfile:
    """Display data of a user as last seen in a verified token."""

    id: UUID
    email: str | None
    display_name: str
