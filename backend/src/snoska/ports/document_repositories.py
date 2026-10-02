from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from snoska.domain.documents.document import Document
from snoska.domain.documents.structure import DocumentStructure
from snoska.domain.documents.version import DocumentVersion, ParseFailureCode, ParseStatus


@dataclass(frozen=True, slots=True)
class DocumentListItem:
    """Read projection for document lists: one row, no N+1."""

    id: UUID
    workspace_id: UUID
    title: str
    kind_code: str
    created_at: datetime
    updated_at: datetime
    latest_version_number: int
    latest_version_id: UUID
    latest_status: ParseStatus
    latest_failure_code: ParseFailureCode | None
    latest_format_code: str
    latest_size_bytes: int
    latest_page_count: int | None
    created_by_name: str | None


@dataclass(frozen=True, slots=True)
class DocumentCursor:
    """Keyset position: lists are ordered by (updated_at desc, id desc)."""

    updated_at: datetime
    id: UUID


@dataclass(frozen=True, slots=True)
class DocumentFilter:
    workspace_id: UUID
    kind_code: str | None = None
    search: str | None = None


@dataclass(frozen=True, slots=True)
class UploadReference:
    document_id: UUID
    version_number: int


class DocumentRepository(Protocol):
    async def add(self, document: Document) -> None: ...

    async def get(self, document_id: UUID) -> Document | None: ...

    async def save(self, document: Document) -> None:
        """Persist changes if nobody else changed the document meanwhile.

        Raises ConcurrentModificationError when the stored revision moved on.
        """
        ...

    async def list_page(
        self, filters: DocumentFilter, after: DocumentCursor | None, limit: int
    ) -> Sequence[DocumentListItem]: ...


class DocumentVersionRepository(Protocol):
    async def add(self, version: DocumentVersion, *, upload_key: str | None) -> None: ...

    async def get(self, version_id: UUID) -> DocumentVersion | None: ...

    async def lock(self, version_id: UUID) -> DocumentVersion | None:
        """Load and lock the row until the end of the transaction."""
        ...

    async def get_by_number(self, document_id: UUID, number: int) -> DocumentVersion | None: ...

    async def list_for_document(self, document_id: UUID) -> Sequence[DocumentVersion]: ...

    async def find_by_upload_key(self, upload_key: str) -> UploadReference | None: ...

    async def save(self, version: DocumentVersion) -> None: ...


class DocumentStructureRepository(Protocol):
    async def replace(self, version_id: UUID, structure: DocumentStructure) -> None: ...

    async def load(self, version_id: UUID) -> DocumentStructure | None: ...
