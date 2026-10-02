from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from snoska.domain.shared.errors import ValidationError
from snoska.ports.ai import Embedder
from snoska.ports.corpus_repositories import NormSearchHit
from snoska.ports.unit_of_work import UnitOfWorkFactory

QUERY_MAX_LENGTH = 2_000
MAX_RESULTS = 50


class EmptyQueryError(ValidationError):
    code = "empty_query"


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
        [vector] = await self._embedder.embed([text])
        self._embedder.space.validate(vector)
        async with self._uow_factory.for_platform() as uow:
            return await uow.corpus.search(
                self._embedder.space,
                vector,
                act_code=query.act_code,
                limit=max(1, min(query.limit, MAX_RESULTS)),
            )
