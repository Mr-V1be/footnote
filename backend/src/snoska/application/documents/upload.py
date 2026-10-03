from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

import structlog

from snoska.application.audit.trail import AuditTrail
from snoska.application.integrations.events import OrganizationEvents
from snoska.application.shared.jobs import PARSE_DOCUMENT_VERSION
from snoska.application.tenancy.gate import WorkspaceGate
from snoska.domain.audit.event import AuditAction
from snoska.domain.audit.targets import document_target
from snoska.domain.documents.document import Document, DocumentNotFoundError, title_from_filename
from snoska.domain.documents.formats import FormatRegistry
from snoska.domain.documents.kinds import DocumentKindRegistry
from snoska.domain.documents.version import DocumentVersion, StoredFile
from snoska.domain.integrations.webhooks import WebhookEvent
from snoska.domain.shared.errors import ConflictError
from snoska.domain.shared.ids import new_id
from snoska.domain.tenancy.access import OrganizationAccess
from snoska.domain.tenancy.organization import UserProfile
from snoska.domain.tenancy.permissions import Permission
from snoska.ports.blob_storage import BlobStorage, StoredBlob
from snoska.ports.clock import Clock
from snoska.ports.outbox import OutboxMessage
from snoska.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

log = structlog.get_logger(__name__)


class UnchangedVersionError(ConflictError):
    code = "version_unchanged"


@dataclass(frozen=True, slots=True)
class UploadLimits:
    max_bytes: int


@dataclass(frozen=True, slots=True)
class IncomingFile:
    """An upload as a stream; nothing is buffered in memory as a whole."""

    filename: str
    chunks: AsyncIterator[bytes]


@dataclass(frozen=True, slots=True)
class _StoredUpload:
    blob: StoredBlob
    format_code: str
    media_type: str


@dataclass(frozen=True, slots=True)
class UploadResult:
    document_id: UUID
    version_number: int
    created: bool


async def _prepend(head: bytes, rest: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    if head:
        yield head
    async for chunk in rest:
        yield chunk


class DocumentUploads:
    """Registers documents and their new versions, then schedules parsing."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        blobs: BlobStorage,
        formats: FormatRegistry,
        kinds: DocumentKindRegistry,
        clock: Clock,
        limits: UploadLimits,
        gate: WorkspaceGate,
        audit: AuditTrail,
        events: OrganizationEvents,
    ) -> None:
        self._uow_factory = uow_factory
        self._blobs = blobs
        self._formats = formats
        self._kinds = kinds
        self._clock = clock
        self._limits = limits
        self._gate = gate
        self._audit = audit
        self._events = events

    async def upload_document(
        self,
        access: OrganizationAccess,
        uploader: UserProfile,
        *,
        workspace_slug: str,
        incoming: IncomingFile,
        kind_code: str | None,
        title: str | None,
        upload_key: str | None,
    ) -> UploadResult:
        kind = self._kinds.get(kind_code) if kind_code else self._kinds.default
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            granted = await self._gate.require_slug(
                uow, access, workspace_slug, Permission.DOCUMENTS_UPLOAD
            )
        workspace = granted.workspace
        replay = await self._replay(access, upload_key)
        if replay is not None:
            return replay

        document_id = new_id()
        version_id = new_id()
        stored = await self._store(access.organization_id, document_id, version_id, incoming)
        now = self._clock.now()
        document = Document.register(
            id=document_id,
            organization_id=access.organization_id,
            workspace_id=workspace.id,
            title=title or title_from_filename(incoming.filename),
            kind_code=kind.code,
            created_by=uploader.id,
            now=now,
        )
        version = self._next_version(document, version_id, stored, incoming.filename, uploader)
        try:
            async with self._uow_factory.for_tenant(access.organization_id) as uow:
                await uow.profiles.upsert(uploader, self._clock.now())
                await uow.documents.add(document)
                await uow.versions.add(version, upload_key=upload_key)
                await self._schedule_parsing(uow, version)
                await self._audit.record(
                    uow,
                    access,
                    AuditAction.DOCUMENT_UPLOADED,
                    document_target(document),
                    {"workspace": workspace.slug, "kind": kind.code, "file": incoming.filename},
                )
                await self._events.emit(
                    uow,
                    access.organization_id,
                    WebhookEvent.DOCUMENT_UPLOADED,
                    {
                        "document_id": str(document.id),
                        "title": document.title,
                        "kind": kind.code,
                        "workspace": workspace.slug,
                    },
                )
                await uow.commit()
        except BaseException:
            await self._blobs.delete(stored.blob.key)
            raise
        log.info("document.uploaded", document_id=str(document_id), format=stored.format_code)
        return UploadResult(document_id=document_id, version_number=version.number, created=True)

    async def upload_version(
        self,
        access: OrganizationAccess,
        uploader: UserProfile,
        *,
        document_id: UUID,
        incoming: IncomingFile,
        upload_key: str | None,
    ) -> UploadResult:
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            await self._gate.require_document(uow, access, document_id, Permission.DOCUMENTS_UPLOAD)
        replay = await self._replay(access, upload_key)
        if replay is not None:
            return replay

        version_id = new_id()
        stored = await self._store(access.organization_id, document_id, version_id, incoming)
        try:
            async with self._uow_factory.for_tenant(access.organization_id) as uow:
                document = await uow.documents.get(document_id)
                if document is None:
                    raise DocumentNotFoundError("document not found")
                latest = await uow.versions.get_by_number(
                    document_id, document.latest_version_number
                )
                if latest is not None and latest.file.sha256 == stored.blob.sha256:
                    raise UnchangedVersionError("the file is identical to the latest version")
                version = self._next_version(
                    document, version_id, stored, incoming.filename, uploader
                )
                await uow.profiles.upsert(uploader, self._clock.now())
                await uow.documents.save(document)
                await uow.versions.add(version, upload_key=upload_key)
                await self._schedule_parsing(uow, version)
                await self._audit.record(
                    uow,
                    access,
                    AuditAction.DOCUMENT_VERSION_ADDED,
                    document_target(document),
                    {"version": version.number, "file": incoming.filename},
                )
                await uow.commit()
        except BaseException:
            await self._blobs.delete(stored.blob.key)
            raise
        return UploadResult(document_id=document_id, version_number=version.number, created=True)

    async def _replay(
        self, access: OrganizationAccess, upload_key: str | None
    ) -> UploadResult | None:
        """A retried request with the same key returns the original outcome."""
        if upload_key is None:
            return None
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            reference = await uow.versions.find_by_upload_key(upload_key)
        if reference is None:
            return None
        return UploadResult(
            document_id=reference.document_id,
            version_number=reference.version_number,
            created=False,
        )

    async def _store(
        self,
        organization_id: UUID,
        document_id: UUID,
        version_id: UUID,
        incoming: IncomingFile,
    ) -> _StoredUpload:
        head = b""
        stream = aiter(incoming.chunks)
        needed = self._formats.signature_length
        async for chunk in stream:
            head += chunk
            if len(head) >= needed:
                break
        document_format = self._formats.detect(incoming.filename, head)
        key = f"tenants/{organization_id}/documents/{document_id}/versions/{version_id}"
        blob = await self._blobs.put(key, _prepend(head, stream), max_bytes=self._limits.max_bytes)
        return _StoredUpload(
            blob=blob, format_code=document_format.code, media_type=document_format.media_type
        )

    def _next_version(
        self,
        document: Document,
        version_id: UUID,
        stored: _StoredUpload,
        filename: str,
        uploader: UserProfile,
    ) -> DocumentVersion:
        now = self._clock.now()
        return DocumentVersion.upload(
            id=version_id,
            organization_id=document.organization_id,
            document_id=document.id,
            number=document.next_version(now),
            file=StoredFile(
                blob_key=stored.blob.key,
                filename=filename,
                format_code=stored.format_code,
                media_type=stored.media_type,
                size_bytes=stored.blob.size_bytes,
                sha256=stored.blob.sha256,
            ),
            uploaded_by=uploader.id,
            now=now,
        )

    async def _schedule_parsing(self, uow: UnitOfWork, version: DocumentVersion) -> None:
        await uow.outbox.add(
            OutboxMessage(
                id=new_id(),
                job_name=PARSE_DOCUMENT_VERSION.name,
                payload={
                    "organization_id": str(version.organization_id),
                    "version_id": str(version.id),
                },
                created_at=self._clock.now(),
            )
        )
