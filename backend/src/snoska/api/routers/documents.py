from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, File, Form, Header, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from snoska.api.cursors import decode_cursor, encode_cursor
from snoska.api.dependencies import ContainerDep, OrganizationAccessDep, PrincipalDep
from snoska.api.errors import PROBLEM_RESPONSES
from snoska.api.schemas.documents import (
    DocumentListItemOut,
    DocumentOut,
    DocumentPageOut,
    StructureOut,
    UploadOut,
)
from snoska.application.documents.upload import IncomingFile

router = APIRouter(
    prefix="/v1/organizations/{organization}", tags=["documents"], responses=PROBLEM_RESPONSES
)

UPLOAD_CHUNK_BYTES = 256 * 1024
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)]


async def _chunks(upload: UploadFile) -> AsyncIterator[bytes]:
    while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
        yield chunk


@router.get(
    "/workspaces/{workspace}/documents",
    response_model=DocumentPageOut,
    response_model_by_alias=True,
)
async def list_documents(
    container: ContainerDep,
    access: OrganizationAccessDep,
    workspace: str,
    kind: str | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: str | None = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> DocumentPageOut:
    page = await container.documents.list(
        access,
        workspace,
        kind_code=kind,
        search=q,
        after=decode_cursor(cursor) if cursor else None,
        limit=limit,
    )
    return DocumentPageOut(
        items=[DocumentListItemOut.of(item) for item in page.items],
        next_cursor=encode_cursor(page.next_cursor) if page.next_cursor else None,
    )


@router.post(
    "/workspaces/{workspace}/documents",
    response_model=UploadOut,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    container: ContainerDep,
    access: OrganizationAccessDep,
    principal: PrincipalDep,
    workspace: str,
    file: Annotated[UploadFile, File()],
    idempotency_key: IdempotencyKey = None,
    kind: Annotated[str | None, Form()] = None,
    title: Annotated[str | None, Form(max_length=300)] = None,
) -> UploadOut:
    result = await container.uploads.upload_document(
        access,
        principal.profile,
        workspace_slug=workspace,
        incoming=IncomingFile(filename=file.filename or "document", chunks=_chunks(file)),
        kind_code=kind,
        title=title,
        upload_key=idempotency_key,
    )
    return UploadOut(
        document_id=result.document_id, version_number=result.version_number, created=result.created
    )


@router.get("/documents/{document_id}", response_model=DocumentOut, response_model_by_alias=True)
async def get_document(
    container: ContainerDep, access: OrganizationAccessDep, document_id: UUID
) -> DocumentOut:
    return DocumentOut.of(await container.documents.details(access, document_id))


@router.post(
    "/documents/{document_id}/versions",
    response_model=UploadOut,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def upload_version(
    container: ContainerDep,
    access: OrganizationAccessDep,
    principal: PrincipalDep,
    document_id: UUID,
    file: Annotated[UploadFile, File()],
    idempotency_key: IdempotencyKey = None,
) -> UploadOut:
    result = await container.uploads.upload_version(
        access,
        principal.profile,
        document_id=document_id,
        incoming=IncomingFile(filename=file.filename or "document", chunks=_chunks(file)),
        upload_key=idempotency_key,
    )
    return UploadOut(
        document_id=result.document_id, version_number=result.version_number, created=result.created
    )


@router.get(
    "/documents/{document_id}/versions/{number}/structure",
    response_model=StructureOut,
    response_model_by_alias=True,
)
async def get_structure(
    container: ContainerDep, access: OrganizationAccessDep, document_id: UUID, number: int
) -> StructureOut:
    result = await container.documents.structure(access, document_id, number)
    return StructureOut.of(result.version, result.structure)


@router.get("/documents/{document_id}/versions/{number}/file")
async def download_original(
    container: ContainerDep, access: OrganizationAccessDep, document_id: UUID, number: int
) -> StreamingResponse:
    original = await container.documents.original(access, document_id, number)
    file = original.version.file
    disposition = f"attachment; filename*=UTF-8''{quote(file.filename)}"
    return StreamingResponse(
        original.chunks,
        media_type=file.media_type,
        headers={"Content-Disposition": disposition, "Content-Length": str(file.size_bytes)},
    )
