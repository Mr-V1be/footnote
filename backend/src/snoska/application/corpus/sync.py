from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

import structlog

from snoska.application.shared.jobs import INDEX_CORPUS_EDITION
from snoska.domain.corpus.acts import Edition, EditionStatus
from snoska.domain.corpus.assembly import assemble_edition, edition_content_hash
from snoska.domain.shared.errors import NotFoundError
from snoska.domain.shared.ids import new_id
from snoska.ports.clock import Clock
from snoska.ports.corpus_source import ActCatalog, CorpusSource
from snoska.ports.outbox import OutboxMessage
from snoska.ports.unit_of_work import UnitOfWorkFactory

log = structlog.get_logger(__name__)


class UnknownCorpusSourceError(NotFoundError):
    code = "unknown_corpus_source"


class SyncOutcome(StrEnum):
    UNCHANGED = "unchanged"
    INGESTED = "ingested"


@dataclass(frozen=True, slots=True)
class SyncResult:
    act_code: str
    outcome: SyncOutcome
    edition_id: UUID
    source_revision: str
    unit_count: int


class CorpusSync:
    """Fetches the current redaction of an act and stores it as a new edition.

    Editions are immutable: an unchanged source is a no-op (matched by a hash
    of the normative content), a changed one becomes the edition in force
    right away and is indexed for search in the background.
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        catalog: ActCatalog,
        sources: Mapping[str, CorpusSource],
        clock: Clock,
    ) -> None:
        self._uow_factory = uow_factory
        self._catalog = catalog
        self._sources = sources
        self._clock = clock

    async def sync(self, act_code: str, source_code: str) -> SyncResult:
        tracked = self._catalog.get(act_code)
        source = self._sources.get(source_code)
        if source is None:
            raise UnknownCorpusSourceError(f"unknown corpus source {source_code!r}")
        fetched = await source.fetch_current(tracked.act)
        content_sha = edition_content_hash(fetched.units)

        async with self._uow_factory.for_platform() as uow:
            await uow.corpus.upsert_act(tracked.act)
            existing = await uow.corpus.find_edition(act_code, content_sha)
            if existing is not None:
                await uow.commit()
                return SyncResult(
                    act_code=act_code,
                    outcome=SyncOutcome.UNCHANGED,
                    edition_id=existing.id,
                    source_revision=existing.source_revision,
                    unit_count=len(await uow.corpus.list_units(existing.id)),
                )
            edition = Edition(
                id=new_id(),
                act_code=act_code,
                source_code=fetched.source_code,
                source_revision=fetched.source_revision,
                amended_by=fetched.amended_by,
                content_sha256=content_sha,
                retrieved_at=fetched.retrieved_at,
                status=EditionStatus.INGESTED,
                activated_at=None,
            )
            assembled = assemble_edition(edition.id, tracked.act, fetched.units, new_id)
            await uow.corpus.add_edition(edition, assembled.units)
            previous = await uow.corpus.active_edition(act_code)
            if previous is not None:
                previous.supersede()
                await uow.corpus.save_edition(previous)
            edition.activate(self._clock.now())
            await uow.corpus.save_edition(edition)
            await uow.outbox.add(
                OutboxMessage(
                    id=new_id(),
                    job_name=INDEX_CORPUS_EDITION.name,
                    payload={"edition_id": str(edition.id)},
                    created_at=self._clock.now(),
                )
            )
            await uow.commit()
        log.info(
            "corpus.edition_ingested",
            act=act_code,
            revision=fetched.source_revision,
            units=len(assembled.units),
        )
        return SyncResult(
            act_code=act_code,
            outcome=SyncOutcome.INGESTED,
            edition_id=edition.id,
            source_revision=fetched.source_revision,
            unit_count=len(assembled.units),
        )
