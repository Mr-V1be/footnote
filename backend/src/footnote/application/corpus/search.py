from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from footnote.domain.shared.errors import InvalidStateError, ValidationError
from footnote.ports.ai import Embedder
from footnote.ports.corpus.repositories import NormSearchHit
from footnote.ports.unit_of_work import UnitOfWorkFactory

QUERY_MAX_LENGTH = 2_000
MAX_RESULTS = 50


class EmptyQueryError(ValidationError):
    code = "empty_query"


class CorpusNotIndexedError(InvalidStateError):
    """No edition in force is indexed for the configured embedding model yet."""

    code = "corpus_not_indexed"


@dataclass(frozen=True, slots=True)
class NormSearchQuery:
    text: str
    act_code: str | None = None
    limit: int = 10


class NormSearch:
    """Semantic retrieval over the active editions of the corpus."""

    def __init__(self, uow_factory: UnitOfWorkFactory, embedder: Embedder) -> None:
        self._uow_factory = uow_factory
        self._embedder = embedder

    async def search(self, query: NormSearchQuery) -> Sequence[NormSearchHit]:
        text = query.text.strip()[:QUERY_MAX_LENGTH]
        if not text:
            raise EmptyQueryError("query is empty")
        space = self._embedder.space
        async with self._uow_factory.for_platform() as uow:
            indexed = await uow.corpus.indexed_active_editions(space, query.act_code)
        if not indexed:
            raise CorpusNotIndexedError(f"no edition in force is indexed in space {space.code!r}")
        [vector] = await self._embedder.embed([text])
        space.validate(vector)
        async with self._uow_factory.for_platform() as uow:
            return await uow.corpus.search(
                self._embedder.space,
                vector,
                act_code=query.act_code,
                limit=max(1, min(query.limit, MAX_RESULTS)),
            )
