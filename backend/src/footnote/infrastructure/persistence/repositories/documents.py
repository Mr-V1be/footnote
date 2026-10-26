from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, and_, insert, select, tuple_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from footnote.domain.documents.document import Document
from footnote.domain.documents.version import (
    DocumentVersion,
    ExtractionMethod,
    ParseFailureCode,
    ParseStatus,
    ParseSummary,
    StoredFile,
    VersionOrigin,
)
from footnote.domain.shared.errors import ConflictError
from footnote.infrastructure.persistence.errors import violated_constraint
from footnote.infrastructure.persistence.tables.checks import check_results, check_runs
from footnote.infrastructure.persistence.tables.documents import document_versions, documents
from footnote.infrastructure.persistence.tables.tenancy import user_profiles
from footnote.ports.document_repositories import (
    DocumentCursor,
    DocumentFilter,
    DocumentListItem,
    UploadReference,
)
from footnote.ports.unit_of_work import ConcurrentModificationError

# Error codes of checks that wait for the model: its daily allowance was
# spent, or it did not answer for a while.
MODEL_WAITING = ("model_daily_limit", "model_unavailable")

_LIKE_ESCAPE = "\\"
_UPLOAD_KEY_CONSTRAINT = "uq_document_versions_organization_id_upload_key"


class UploadInProgressError(ConflictError):
    code = "upload_in_progress"


def _like_pattern(term: str) -> str:
    escaped = term.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2).replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _document(row: RowMapping) -> Document:
    return Document(
        id=row["id"],
        organization_id=row["organization_id"],
        workspace_id=row["workspace_id"],
        title=row["title"],
        kind_code=row["kind_code"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        latest_version_number=row["latest_version_number"],
        revision=row["revision"],
    )


def _summary(row: RowMapping) -> ParseSummary | None:
    if row["method"] is None:
        return None
    return ParseSummary(
        method=ExtractionMethod(row["method"]),
        page_count=row["page_count"],
        block_count=row["block_count"],
        character_count=row["character_count"] or 0,
        ocr_confidence=row["ocr_confidence"],
    )


def _version(row: RowMapping) -> DocumentVersion:
    failure = row["failure_code"]
    return DocumentVersion(
        id=row["id"],
        organization_id=row["organization_id"],
        document_id=row["document_id"],
        number=row["number"],
        file=StoredFile(
            blob_key=row["blob_key"],
            filename=row["filename"],
            format_code=row["format_code"],
            media_type=row["media_type"],
            size_bytes=row["size_bytes"],
            sha256=row["sha256"],
        ),
        uploaded_by=row["uploaded_by"],
        created_at=row["created_at"],
        status=ParseStatus(row["status"]),
        attempts=row["attempts"],
        parse_started_at=row["parse_started_at"],
        parsed_at=row["parsed_at"],
        failure_code=ParseFailureCode(failure) if failure else None,
        summary=_summary(row),
        origin=VersionOrigin(row["origin"]),
        derived_from=row["derived_from"],
    )


def _version_state(version: DocumentVersion) -> dict[str, Any]:
    summary = version.summary
    return {
        "status": version.status.value,
        "attempts": version.attempts,
        "parse_started_at": version.parse_started_at,
        "parsed_at": version.parsed_at,
        "failure_code": version.failure_code.value if version.failure_code else None,
        "method": summary.method.value if summary else None,
        "page_count": summary.page_count if summary else None,
        "block_count": summary.block_count if summary else None,
        "character_count": summary.character_count if summary else None,
        "ocr_confidence": summary.ocr_confidence if summary else None,
    }


class SqlDocumentRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, document: Document) -> None:
        await self._connection.execute(
            insert(documents).values(
                id=document.id,
                organization_id=document.organization_id,
                workspace_id=document.workspace_id,
                title=document.title,
                kind_code=document.kind_code,
                created_by=document.created_by,
                created_at=document.created_at,
                updated_at=document.updated_at,
                latest_version_number=document.latest_version_number,
                revision=document.revision,
            )
        )

    async def get(self, document_id: UUID) -> Document | None:
        result = await self._connection.execute(
            select(documents).where(documents.c.id == document_id)
        )
        row = result.mappings().first()
        return _document(row) if row else None

    async def save(self, document: Document) -> None:
        result = await self._connection.execute(
            update(documents)
            .where(documents.c.id == document.id, documents.c.revision == document.revision - 1)
            .values(
                title=document.title,
                kind_code=document.kind_code,
                updated_at=document.updated_at,
                latest_version_number=document.latest_version_number,
                revision=document.revision,
            )
        )
        if result.rowcount != 1:
            raise ConcurrentModificationError("the document was changed concurrently")

    async def list_page(
        self, filters: DocumentFilter, after: DocumentCursor | None, limit: int
    ) -> Sequence[DocumentListItem]:
        latest = document_versions.alias("latest")
        conditions = [documents.c.workspace_id == filters.workspace_id]
        if filters.kind_code is not None:
            conditions.append(documents.c.kind_code == filters.kind_code)
        if filters.search:
            conditions.append(
                documents.c.title.ilike(_like_pattern(filters.search), escape=_LIKE_ESCAPE)
            )
        if after is not None:
            conditions.append(
                tuple_(documents.c.updated_at, documents.c.id) < tuple_(after.updated_at, after.id)
            )
        statement = (
            select(
                documents,
                latest.c.id.label("latest_version_id"),
                latest.c.status,
                latest.c.failure_code,
                latest.c.format_code,
                latest.c.size_bytes,
                latest.c.page_count,
                user_profiles.c.display_name,
            )
            .join(
                latest,
                and_(
                    latest.c.document_id == documents.c.id,
                    latest.c.number == documents.c.latest_version_number,
                ),
            )
            .outerjoin(user_profiles, user_profiles.c.id == documents.c.created_by)
            .where(*conditions)
            .order_by(documents.c.updated_at.desc(), documents.c.id.desc())
            .limit(limit)
        )
        result = await self._connection.execute(statement)
        return [
            DocumentListItem(
                id=row["id"],
                workspace_id=row["workspace_id"],
                title=row["title"],
                kind_code=row["kind_code"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                latest_version_number=row["latest_version_number"],
                latest_version_id=row["latest_version_id"],
                latest_status=ParseStatus(row["status"]),
                latest_failure_code=(
                    ParseFailureCode(row["failure_code"]) if row["failure_code"] else None
                ),
                latest_format_code=row["format_code"],
                latest_size_bytes=row["size_bytes"],
                latest_page_count=row["page_count"],
                created_by_name=row["display_name"],
            )
            for row in result.mappings()
        ]


class SqlDocumentVersionRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, version: DocumentVersion, *, upload_key: str | None) -> None:
        values = {
            "id": version.id,
            "organization_id": version.organization_id,
            "document_id": version.document_id,
            "number": version.number,
            "blob_key": version.file.blob_key,
            "filename": version.file.filename,
            "format_code": version.file.format_code,
            "media_type": version.file.media_type,
            "size_bytes": version.file.size_bytes,
            "sha256": version.file.sha256,
            "uploaded_by": version.uploaded_by,
            "upload_key": upload_key,
            "origin": version.origin.value,
            "derived_from": version.derived_from,
            "created_at": version.created_at,
            **_version_state(version),
        }
        try:
            await self._connection.execute(insert(document_versions).values(**values))
        except IntegrityError as exc:
            if violated_constraint(exc) == _UPLOAD_KEY_CONSTRAINT:
                raise UploadInProgressError(
                    "an upload with this key is already registered"
                ) from exc
            raise

    async def get(self, version_id: UUID) -> DocumentVersion | None:
        result = await self._connection.execute(
            select(document_versions).where(document_versions.c.id == version_id)
        )
        row = result.mappings().first()
        return _version(row) if row else None

    async def lock(self, version_id: UUID) -> DocumentVersion | None:
        result = await self._connection.execute(
            select(document_versions).where(document_versions.c.id == version_id).with_for_update()
        )
        row = result.mappings().first()
        return _version(row) if row else None

    async def get_by_number(self, document_id: UUID, number: int) -> DocumentVersion | None:
        result = await self._connection.execute(
            select(document_versions).where(
                document_versions.c.document_id == document_id,
                document_versions.c.number == number,
            )
        )
        row = result.mappings().first()
        return _version(row) if row else None

    async def list_for_document(self, document_id: UUID) -> Sequence[DocumentVersion]:
        result = await self._connection.execute(
            select(document_versions)
            .where(document_versions.c.document_id == document_id)
            .order_by(document_versions.c.number.desc())
        )
        return [_version(row) for row in result.mappings()]

    async def latest_parsed(self) -> Sequence[DocumentVersion]:
        result = await self._connection.execute(
            select(document_versions)
            .join(
                documents,
                and_(
                    documents.c.id == document_versions.c.document_id,
                    documents.c.latest_version_number == document_versions.c.number,
                ),
            )
            .where(document_versions.c.status == ParseStatus.PARSED.value)
            .order_by(document_versions.c.created_at)
        )
        return [_version(row) for row in result.mappings()]

    async def latest_waiting_for_model(self) -> Sequence[DocumentVersion]:
        """Latest versions whose latest check has results that waited for the
        model's daily allowance."""
        last_run = (
            select(check_runs.c.id)
            .where(check_runs.c.version_id == document_versions.c.id)
            .order_by(check_runs.c.created_at.desc())
            .limit(1)
            .correlate(document_versions)
            .scalar_subquery()
        )
        waiting = (
            select(check_results.c.run_id)
            .where(
                check_results.c.run_id == last_run,
                check_results.c.error_code.in_(MODEL_WAITING),
            )
            .exists()
        )
        result = await self._connection.execute(
            select(document_versions)
            .join(
                documents,
                and_(
                    documents.c.id == document_versions.c.document_id,
                    documents.c.latest_version_number == document_versions.c.number,
                ),
            )
            .where(waiting)
            .order_by(document_versions.c.created_at)
        )
        return [_version(row) for row in result.mappings()]

    async def find_by_upload_key(self, upload_key: str) -> UploadReference | None:
        result = await self._connection.execute(
            select(document_versions.c.document_id, document_versions.c.number).where(
                document_versions.c.upload_key == upload_key
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return UploadReference(document_id=row["document_id"], version_number=row["number"])

    async def save(self, version: DocumentVersion) -> None:
        await self._connection.execute(
            update(document_versions)
            .where(document_versions.c.id == version.id)
            .values(**_version_state(version))
        )
