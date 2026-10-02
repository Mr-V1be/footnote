from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from uuid import UUID

from snoska.application.documents.upload import DocumentNotFoundError
from snoska.application.shared.pagination import Page, clamp_page_size
from snoska.application.tenancy.workspaces import WorkspaceNotFoundError
from snoska.domain.documents.document import Document
from snoska.domain.documents.kinds import DocumentKindRegistry
from snoska.domain.documents.structure import DocumentStructure
from snoska.domain.documents.version import DocumentVersion
from snoska.domain.shared.errors import NotFoundError
from snoska.domain.tenancy.access import OrganizationAccess
from snoska.domain.tenancy.organization import Workspace
from snoska.domain.tenancy.permissions import Permission
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
    workspace: Workspace
    versions: Sequence[DocumentVersion]

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
        self, uow_factory: UnitOfWorkFactory, blobs: BlobStorage, kinds: DocumentKindRegistry
    ) -> None:
        self._uow_factory = uow_factory
        self._blobs = blobs
        self._kinds = kinds

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
        access.require(Permission.DOCUMENTS_READ)
        if kind_code is not None:
            self._kinds.get(kind_code)
        size = clamp_page_size(limit)
        term = search.strip()[:SEARCH_MAX_LENGTH] if search else None
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            workspace = await uow.workspaces.get_by_slug(workspace_slug)
            if workspace is None:
                raise WorkspaceNotFoundError(f"workspace {workspace_slug!r} not found")
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
        access.require(Permission.DOCUMENTS_READ)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            document = await uow.documents.get(document_id)
            if document is None:
                raise DocumentNotFoundError("document not found")
            versions = await uow.versions.list_for_document(document_id)
            workspace = await uow.workspaces.get(document.workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("workspace of the document not found")
        return DocumentDetails(document=document, workspace=workspace, versions=versions)

    async def structure(
        self, access: OrganizationAccess, document_id: UUID, version_number: int
    ) -> VersionStructure:
        access.require(Permission.DOCUMENTS_READ)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            version = await uow.versions.get_by_number(document_id, version_number)
            if version is None:
                raise VersionNotFoundError("version not found")
            structure = await uow.structures.load(version.id)
        return VersionStructure(version=version, structure=structure)

    async def original(
        self, access: OrganizationAccess, document_id: UUID, version_number: int
    ) -> OriginalFile:
        access.require(Permission.DOCUMENTS_READ)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            version = await uow.versions.get_by_number(document_id, version_number)
        if version is None:
            raise VersionNotFoundError("version not found")
        return OriginalFile(
            version=version,
            chunks=self._blobs.stream(version.file.blob_key, chunk_size=DOWNLOAD_CHUNK_BYTES),
        )
