from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from snoska.domain.shared.errors import InvalidStateError


class ParseStatus(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class ParseFailureCode(StrEnum):
    """Stable reasons a version could not be turned into a structure."""

    CORRUPTED_FILE = "corrupted_file"
    ENCRYPTED_FILE = "encrypted_file"
    EMPTY_DOCUMENT = "empty_document"
    TOO_LARGE = "too_large"
    OCR_FAILED = "ocr_failed"
    INTERNAL_ERROR = "internal_error"


class ExtractionMethod(StrEnum):
    DOCX = "docx"
    PDF_TEXT = "pdf_text"
    PDF_OCR = "pdf_ocr"
    PDF_MIXED = "pdf_mixed"


@dataclass(frozen=True, slots=True)
class StoredFile:
    blob_key: str
    filename: str
    format_code: str
    media_type: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ParseSummary:
    method: ExtractionMethod
    page_count: int | None
    block_count: int
    ocr_confidence: float | None
    # Characters of text: how long a document without pages (DOCX) is.
    character_count: int = 0


class VersionOrigin(StrEnum):
    UPLOAD = "upload"
    # Made by the platform from an earlier version: formatting corrected.
    AUTOFIX = "autofix"


@dataclass(slots=True)
class DocumentVersion:
    """One file of a document and the lifecycle of its parsing.

    A version is uploaded by someone, or made by the platform (``origin``),
    in which case ``derived_from`` names the version it was made from.
    """

    id: UUID
    organization_id: UUID
    document_id: UUID
    number: int
    file: StoredFile
    uploaded_by: UUID
    created_at: datetime
    status: ParseStatus
    attempts: int
    parse_started_at: datetime | None
    parsed_at: datetime | None
    failure_code: ParseFailureCode | None
    summary: ParseSummary | None
    origin: VersionOrigin = VersionOrigin.UPLOAD
    derived_from: int | None = None

    @classmethod
    def upload(
        cls,
        *,
        id: UUID,
        organization_id: UUID,
        document_id: UUID,
        number: int,
        file: StoredFile,
        uploaded_by: UUID,
        now: datetime,
        origin: VersionOrigin = VersionOrigin.UPLOAD,
        derived_from: int | None = None,
    ) -> DocumentVersion:
        return cls(
            id=id,
            organization_id=organization_id,
            document_id=document_id,
            number=number,
            file=file,
            uploaded_by=uploaded_by,
            created_at=now,
            status=ParseStatus.QUEUED,
            attempts=0,
            parse_started_at=None,
            parsed_at=None,
            failure_code=None,
            summary=None,
            origin=origin,
            derived_from=derived_from,
        )

    @property
    def is_settled(self) -> bool:
        return self.status in (ParseStatus.PARSED, ParseStatus.FAILED)

    def start_parsing(self, now: datetime) -> None:
        # PARSING is accepted too: a worker that died mid-job leaves the
        # version in PARSING and the redelivered job must be able to resume.
        if self.is_settled:
            raise InvalidStateError(f"version is already {self.status}")
        self.status = ParseStatus.PARSING
        self.attempts += 1
        self.parse_started_at = now

    def complete(self, summary: ParseSummary, now: datetime) -> None:
        if self.status is not ParseStatus.PARSING:
            raise InvalidStateError(f"cannot complete parsing from {self.status}")
        self.status = ParseStatus.PARSED
        self.summary = summary
        self.parsed_at = now
        self.failure_code = None

    def fail(self, code: ParseFailureCode, now: datetime) -> None:
        if self.is_settled:
            raise InvalidStateError(f"version is already {self.status}")
        self.status = ParseStatus.FAILED
        self.failure_code = code
        self.parsed_at = now
