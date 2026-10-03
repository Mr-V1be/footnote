from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, replace
from uuid import UUID

from snoska.application.shared.pagination import Page, clamp_page_size
from snoska.application.tenancy.gate import WorkspaceGate
from snoska.domain.documents.document import Document
from snoska.domain.documents.kinds import DocumentKindRegistry
from snoska.domain.documents.requisites import RequisiteDetector
from snoska.domain.documents.structure import DocumentStructure
from snoska.domain.documents.version import DocumentVersion
from snoska.domain.shared.errors import NotFoundError
from snoska.domain.tenancy.access import OrganizationAccess
from snoska.domain.tenancy.organization import Workspace
from snoska.domain.tenancy.permissions import Permission
from snoska.domain.tenancy.workspace_access import WorkspaceAccess
from snoska.ports.blob_storage import BlobStorage
from snoska.ports.document_repositories import DocumentCursor, DocumentFilter, DocumentListItem
from snoska.ports.unit_of_work import UnitOfWorkFactory

DOWNLOAD_CHUNK_BYTES = 256 * 1024
SEARCH_MAX_LENGTH = 200


class VersionNotFoundError(NotFoundError):
    code = "version_not_found"


@dataclass(frozen=True, slots=True)
class DocumentDetails:
    document: Document
    access: WorkspaceAccess
    versions: Sequence[DocumentVersion]

    @property
    def workspace(self) -> Workspace:
        return self.access.workspace

    @property
    def latest(self) -> DocumentVersion:
        return max(self.versions, key=lambda version: version.number)


@dataclass(frozen=True, slots=True)
class VersionStructure:
    version: DocumentVersion
    structure: DocumentStructure | None


@dataclass(frozen=True, slots=True)
class OriginalFile:
    version: DocumentVersion
    chunks: AsyncIterator[bytes]


class DocumentQueries:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        blobs: BlobStorage,
        kinds: DocumentKindRegistry,
        requisites: RequisiteDetector,
        gate: WorkspaceGate,
    ) -> None:
        self._uow_factory = uow_factory
        self._blobs = blobs
        self._kinds = kinds
        self._requisites = requisites
        self._gate = gate

    async def list(
        self,
        access: OrganizationAccess,
        workspace_slug: str,
        *,
        kind_code: str | None,
        search: str | None,
        after: DocumentCursor | None,
        limit: int | None,
    ) -> Page[DocumentListItem, DocumentCursor]:
        if kind_code is not None:
            self._kinds.get(kind_code)
        size = clamp_page_size(limit)
        term = search.strip()[:SEARCH_MAX_LENGTH] if search else None
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            granted = await self._gate.require_slug(
                uow, access, workspace_slug, Permission.DOCUMENTS_READ
            )
            workspace = granted.workspace
            rows = await uow.documents.list_page(
                DocumentFilter(workspace_id=workspace.id, kind_code=kind_code, search=term or None),
                after,
                size + 1,
            )
        items = rows[:size]
        next_cursor = (
            DocumentCursor(updated_at=items[-1].updated_at, id=items[-1].id)
            if len(rows) > size
            else None
        )
        return Page(items=items, next_cursor=next_cursor)

    async def details(self, access: OrganizationAccess, document_id: UUID) -> DocumentDetails:
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            document, granted = await self._gate.document_access(
                uow, access, document_id, Permission.DOCUMENTS_READ
            )
            versions = await uow.versions.list_for_document(document_id)
        return DocumentDetails(document=document, access=granted, versions=versions)

    async def structure(
        self, access: OrganizationAccess, document_id: UUID, version_number: int
    ) -> VersionStructure:
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            await self._gate.require_document(uow, access, document_id, Permission.DOCUMENTS_READ)
            version = await uow.versions.get_by_number(document_id, version_number)
            if version is None:
                raise VersionNotFoundError("version not found")
            structure = await uow.structures.load(version.id)
        if structure is not None:
            structure = replace(structure, requisites=self._requisites.detect(structure.blocks))
        return VersionStructure(version=version, structure=structure)

    async def original(
        self, access: OrganizationAccess, document_id: UUID, version_number: int
    ) -> OriginalFile:
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            await self._gate.require_document(uow, access, document_id, Permission.DOCUMENTS_READ)
            version = await uow.versions.get_by_number(document_id, version_number)
        if version is None:
            raise VersionNotFoundError("version not found")
        return OriginalFile(
            version=version,
            chunks=self._blobs.stream(version.file.blob_key, chunk_size=DOWNLOAD_CHUNK_BYTES),
        )
