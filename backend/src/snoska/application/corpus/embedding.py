from __future__ import annotations

from itertools import batched
from uuid import UUID

import structlog

from snoska.domain.corpus.acts import EditionStatus
from snoska.domain.corpus.assembly import embedding_texts_for
from snoska.ports.ai import Embedder
from snoska.ports.clock import Clock
from snoska.ports.jobs import JobPayload
from snoska.ports.unit_of_work import UnitOfWorkFactory

log = structlog.get_logger(__name__)

EMBEDDING_BATCH_SIZE = 16


class EmbedCorpusEdition:
    """Background job: embed every passage of an edition, then activate it.

    Vectors are keyed by the hash of the passage, so text unchanged between
    editions is embedded once. Each batch commits on its own, so a retried
    job resumes where the previous attempt stopped.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, embedder: Embedder, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._embedder = embedder
        self._clock = clock

    async def __call__(self, payload: JobPayload) -> None:
        edition_id = UUID(payload["edition_id"])
        space = self._embedder.space
        async with self._uow_factory.for_platform() as uow:
            edition = await uow.corpus.lock_edition(edition_id)
            if edition is None or edition.status is not EditionStatus.INGESTED:
                return
            units = await uow.corpus.list_units(edition_id)
            texts = embedding_texts_for(units)
            missing = await uow.corpus.missing_embeddings(space, texts.keys())

        for batch in batched(sorted(missing), EMBEDDING_BATCH_SIZE, strict=False):
            vectors = await self._embedder.embed([texts[sha] for sha in batch])
            for vector in vectors:
                space.validate(vector)
            async with self._uow_factory.for_platform() as uow:
                await uow.corpus.add_embeddings(
                    space, dict(zip(batch, vectors, strict=True)), self._clock.now()
                )
                await uow.commit()

        async with self._uow_factory.for_platform() as uow:
            edition = await uow.corpus.lock_edition(edition_id)
            if edition is None or edition.status is not EditionStatus.INGESTED:
                return
            previous = await uow.corpus.active_edition(edition.act_code)
            if previous is not None:
                previous.supersede()
                await uow.corpus.save_edition(previous)
            edition.activate(self._clock.now())
            await uow.corpus.save_edition(edition)
            await uow.commit()
        log.info("corpus.edition_activated", edition_id=str(edition_id), embedded=len(missing))
