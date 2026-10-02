from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from snoska.domain.corpus.acts import Edition, LegalAct
from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.domain.corpus.units import NormUnit


@dataclass(frozen=True, slots=True)
class NormSearchHit:
    unit: NormUnit
    article_heading: str | None
    distance: float


@dataclass(frozen=True, slots=True)
class ActOverview:
    act: LegalAct
    active_edition: Edition | None
    unit_count: int


class CorpusRepository(Protocol):
    async def upsert_act(self, act: LegalAct) -> None: ...

    async def list_acts(self) -> Sequence[ActOverview]: ...

    async def find_edition(self, act_code: str, content_sha256: str) -> Edition | None: ...

    async def add_edition(self, edition: Edition, units: Sequence[NormUnit]) -> None: ...

    async def lock_edition(self, edition_id: UUID) -> Edition | None: ...

    async def active_edition(self, act_code: str) -> Edition | None: ...

    async def save_edition(self, edition: Edition) -> None: ...

    async def list_units(self, edition_id: UUID) -> Sequence[NormUnit]: ...

    async def get_unit_by_anchor(self, edition_id: UUID, anchor: str) -> NormUnit | None: ...

    async def missing_embeddings(
        self, space: EmbeddingSpace, hashes: Collection[str]
    ) -> set[str]: ...

    async def add_embeddings(
        self, space: EmbeddingSpace, vectors: Mapping[str, Sequence[float]], now: datetime
    ) -> None: ...

    async def search(
        self, space: EmbeddingSpace, vector: Sequence[float], *, act_code: str | None, limit: int
    ) -> Sequence[NormSearchHit]:
        """Nearest units of the active editions by cosine distance."""
        ...
