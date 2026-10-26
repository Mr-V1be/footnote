from __future__ import annotations

from itertools import batched
from uuid import UUID

import structlog

from footnote.domain.corpus.assembly import embedding_texts_for
from footnote.domain.corpus.embedding import EmbeddingSpace
from footnote.domain.shared.errors import InvalidStateError
from footnote.ports.ai import Embedder
from footnote.ports.clock import Clock
from footnote.ports.jobs import JobPayload
from footnote.ports.unit_of_work import UnitOfWorkFactory

log = structlog.get_logger(__name__)

EMBEDDING_BATCH_SIZE = 16


class SpaceNotRegisteredError(InvalidStateError):
    code = "embedding_space_not_registered"


class IndexCorpusEdition:
    """Embed every passage of an edition in the configured space, then mark the
    edition searchable there.

    Vectors are keyed by the hash of the passage, so text unchanged between
    editions is embedded once. Each batch commits on its own, so a retried
    job resumes where the previous attempt stopped. With no embedding model
    configured there is nothing to do: the edition is served, not searchable.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, embedder: Embedder, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._embedder = embedder
        self._clock = clock

    @property
    def space(self) -> EmbeddingSpace:
        return self._embedder.space

    async def __call__(self, payload: JobPayload) -> None:
        if self.space.dimensions <= 0:
            log.info("corpus.index_skipped", reason="no embedding model configured")
            return
        try:
            await self.index(UUID(payload["edition_id"]))
        except SpaceNotRegisteredError:
            log.error("corpus.index_space_missing", space=self.space.code)

    async def index(self, edition_id: UUID) -> int:
        """Embed what is missing and mark the edition indexed; returns how many
        passages were embedded."""
        space = self.space
        async with self._uow_factory.for_platform() as uow:
            if not await uow.corpus.space_registered(space):
                raise SpaceNotRegisteredError(
                    f"space {space.code!r} is not registered: run `footnote corpus reindex`"
                )
            if await uow.corpus.is_indexed(edition_id, space):
                return 0
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
            await uow.corpus.mark_indexed(edition_id, space, self._clock.now())
            await uow.commit()
        log.info("corpus.edition_indexed", edition_id=str(edition_id), space=space.code)
        return len(missing)

    async def reindex_active(self) -> dict[UUID, int]:
        """Index every edition in force; the command run after a model change."""
        async with self._uow_factory.for_platform() as uow:
            editions = await uow.corpus.active_editions()
        return {edition.id: await self.index(edition.id) for edition in editions}
