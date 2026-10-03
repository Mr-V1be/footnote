from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePath
from uuid import UUID

from snoska.domain.shared.errors import NotFoundError, ValidationError
from snoska.domain.shared.text import normalize_whitespace

TITLE_MAX_LENGTH = 300


class InvalidTitleError(ValidationError):
    code = "invalid_title"


class DocumentNotFoundError(NotFoundError):
    code = "document_not_found"


def title_from_filename(filename: str) -> str:
    """Derive a human title from an uploaded file name."""
    stem = PurePath(filename).stem.replace("_", " ")
    return normalize_whitespace(stem)[:TITLE_MAX_LENGTH] or filename[:TITLE_MAX_LENGTH]


def validate_title(value: str) -> str:
    title = normalize_whitespace(value)
    if not title or len(title) > TITLE_MAX_LENGTH:
        raise InvalidTitleError(f"title must be 1-{TITLE_MAX_LENGTH} characters")
    return title


@dataclass(slots=True)
class Document:
    """A document registered in a workspace; its content lives in versions.

    ``revision`` is the optimistic concurrency token: every mutation bumps it
    and persistence updates only when the stored revision still matches.
    """

    id: UUID
    organization_id: UUID
    workspace_id: UUID
    title: str
    kind_code: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    latest_version_number: int
    revision: int

    @classmethod
    def register(
        cls,
        *,
        id: UUID,
        organization_id: UUID,
        workspace_id: UUID,
        title: str,
        kind_code: str,
        created_by: UUID,
        now: datetime,
    ) -> Document:
        return cls(
            id=id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            title=validate_title(title),
            kind_code=kind_code,
            created_by=created_by,
            created_at=now,
            updated_at=now,
            latest_version_number=0,
            revision=0,
        )

    def next_version(self, now: datetime) -> int:
        """Reserve the number of a new version and record the change."""
        self.latest_version_number += 1
        self.updated_at = now
        self.revision += 1
        return self.latest_version_number
