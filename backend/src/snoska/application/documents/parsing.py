from __future__ import annotations

from typing import Protocol
from uuid import UUID

import structlog

from snoska.application.shared.jobs import PARSE_DOCUMENT_VERSION
from snoska.domain.documents.structure import DocumentStructure
from snoska.domain.documents.version import DocumentVersion, ParseFailureCode, ParseSummary
from snoska.ports.blob_storage import BlobStorage
from snoska.ports.clock import Clock
from snoska.ports.document_parsing import DocumentParseError, DocumentParserRegistry
from snoska.ports.jobs import JobPayload
from snoska.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

log = structlog.get_logger(__name__)

# On the last delivery the queue will make, an unexpected failure is recorded
# as final so the version never stays in PARSING forever.
MAX_PARSE_ATTEMPTS = PARSE_DOCUMENT_VERSION.max_retries + 1


class ParsedVersionFollowUp(Protocol):
    """What happens next to a parsed version, in the transaction that parsed it."""

    async def on_parsed(self, uow: UnitOfWork, version: DocumentVersion) -> None: ...


class ParseDocumentVersion:
    """Background job: turn an uploaded file into a document structure.

    Idempotent: a redelivered job for a settled version is a no-op, and a
    version left in PARSING by a crashed worker is picked up again.
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        blobs: BlobStorage,
        parsers: DocumentParserRegistry,
        clock: Clock,
        follow_up: ParsedVersionFollowUp | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._blobs = blobs
        self._parsers = parsers
        self._clock = clock
        self._follow_up = follow_up

    async def __call__(self, payload: JobPayload) -> None:
        organization_id = UUID(payload["organization_id"])
        version_id = UUID(payload["version_id"])
        version = await self._begin(organization_id, version_id)
        if version is None:
            return
        bound = log.bind(version_id=str(version_id), organization_id=str(organization_id))
        try:
            content = await self._blobs.read(version.file.blob_key)
            parser = self._parsers.for_format(version.file.format_code)
            parsed = await parser.parse(content)
        except DocumentParseError as exc:
            bound.info("document.parse_rejected", code=exc.code, reason=str(exc))
            await self._fail(organization_id, version_id, exc.code)
            return
        except Exception:
            if version.attempts >= MAX_PARSE_ATTEMPTS:
                bound.exception("document.parse_failed_finally")
                await self._fail(organization_id, version_id, ParseFailureCode.INTERNAL_ERROR)
                return
            raise

        if not parsed.blocks:
            await self._fail(organization_id, version_id, ParseFailureCode.EMPTY_DOCUMENT)
            return
        structure = DocumentStructure(blocks=parsed.blocks, layout=parsed.layout)
        summary = ParseSummary(
            method=parsed.method,
            page_count=parsed.page_count,
            block_count=len(parsed.blocks),
            ocr_confidence=parsed.ocr_confidence,
            character_count=sum(len(block.text) for block in parsed.blocks),
        )
        async with self._uow_factory.for_tenant(organization_id) as uow:
            locked = await uow.versions.lock(version_id)
            if locked is None or locked.is_settled:
                return
            await uow.structures.replace(version_id, structure)
            locked.complete(summary, self._clock.now())
            await uow.versions.save(locked)
            if self._follow_up is not None:
                await self._follow_up.on_parsed(uow, locked)
            await uow.commit()
        bound.info("document.parsed", blocks=summary.block_count, method=summary.method)

    async def _begin(self, organization_id: UUID, version_id: UUID) -> DocumentVersion | None:
        async with self._uow_factory.for_tenant(organization_id) as uow:
            version = await uow.versions.lock(version_id)
            if version is None or version.is_settled:
                return None
            version.start_parsing(self._clock.now())
            await uow.versions.save(version)
            await uow.commit()
            return version

    async def _fail(self, organization_id: UUID, version_id: UUID, code: ParseFailureCode) -> None:
        async with self._uow_factory.for_tenant(organization_id) as uow:
            version = await uow.versions.lock(version_id)
            if version is None or version.is_settled:
                return
            version.fail(code, self._clock.now())
            await uow.versions.save(version)
            await uow.commit()
