from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from snoska.domain.documents.document import Document, InvalidTitleError, title_from_filename
from snoska.domain.documents.formats import SUPPORTED_FORMATS, UnsupportedFormatError
from snoska.domain.documents.version import (
    DocumentVersion,
    ExtractionMethod,
    ParseFailureCode,
    ParseStatus,
    ParseSummary,
    StoredFile,
)
from snoska.domain.shared.errors import InvalidStateError

NOW = datetime(2026, 10, 2, tzinfo=UTC)


def version() -> DocumentVersion:
    return DocumentVersion.upload(
        id=uuid4(),
        organization_id=uuid4(),
        document_id=uuid4(),
        number=1,
        file=StoredFile("key", "a.docx", "docx", "application/x", 10, "0" * 64),
        uploaded_by=uuid4(),
        now=NOW,
    )


SUMMARY = ParseSummary(ExtractionMethod.DOCX, None, 3, 1, None)


def test_parsing_lifecycle_and_redelivery() -> None:
    v = version()
    v.start_parsing(NOW)
    v.start_parsing(NOW)  # a redelivered job resumes a crashed attempt
    assert v.attempts == 2
    v.complete(SUMMARY, NOW)
    assert v.status is ParseStatus.PARSED
    with pytest.raises(InvalidStateError):
        v.start_parsing(NOW)


def test_failure_is_final() -> None:
    v = version()
    v.start_parsing(NOW)
    v.fail(ParseFailureCode.CORRUPTED_FILE, NOW)
    with pytest.raises(InvalidStateError):
        v.complete(SUMMARY, NOW)


def test_versions_are_numbered_and_bump_revision() -> None:
    doc = Document.register(
        id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        title="  Политика   обработки ",
        kind_code="pd_policy",
        created_by=uuid4(),
        now=NOW,
    )
    assert doc.title == "Политика обработки"
    assert (doc.next_version(NOW), doc.next_version(NOW)) == (1, 2)
    assert doc.revision == 2


def test_blank_title_is_rejected() -> None:
    with pytest.raises(InvalidTitleError):
        Document.register(
            id=uuid4(),
            organization_id=uuid4(),
            workspace_id=uuid4(),
            title="   ",
            kind_code="other",
            created_by=uuid4(),
            now=NOW,
        )


def test_title_from_filename() -> None:
    assert title_from_filename("Политика_ПДн_2026.docx") == "Политика ПДн 2026"


@pytest.mark.parametrize(
    ("filename", "head", "expected"),
    [("a.DOCX", b"PK\x03\x04rest", "docx"), ("scan.pdf", b"%PDF-1.7", "pdf")],
)
def test_format_requires_extension_and_signature(filename: str, head: bytes, expected: str) -> None:
    assert SUPPORTED_FORMATS.detect(filename, head).code == expected


@pytest.mark.parametrize(
    ("filename", "head"),
    [("a.pdf", b"PK\x03\x04"), ("a.exe", b"%PDF-1.7"), ("a.docx", b"MZ\x90")],
)
def test_mismatched_files_are_rejected(filename: str, head: bytes) -> None:
    with pytest.raises(UnsupportedFormatError):
        SUPPORTED_FORMATS.detect(filename, head)
