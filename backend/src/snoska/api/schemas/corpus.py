from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from snoska.api.schemas.common import ApiModel
from snoska.domain.corpus.units import NormUnit
from snoska.ports.corpus_repositories import ActOverview, NormSearchHit


class EditionOut(ApiModel):
    id: UUID
    source: str
    source_revision: str
    amended_by: str | None
    retrieved_at: datetime
    activated_at: datetime | None


class ActOut(ApiModel):
    code: str
    kind: str
    short_title: str
    title: str
    adopted_on: date
    edition: EditionOut | None
    unit_count: int

    @classmethod
    def of(cls, overview: ActOverview) -> ActOut:
        edition = overview.active_edition
        return cls(
            code=overview.act.code,
            kind=overview.act.kind.value,
            short_title=overview.act.short_title,
            title=overview.act.title,
            adopted_on=overview.act.adopted_on,
            edition=(
                EditionOut(
                    id=edition.id,
                    source=edition.source_code,
                    source_revision=edition.source_revision,
                    amended_by=edition.amended_by,
                    retrieved_at=edition.retrieved_at,
                    activated_at=edition.activated_at,
                )
                if edition
                else None
            ),
            unit_count=overview.unit_count,
        )


class NormUnitOut(ApiModel):
    id: UUID
    parent_id: UUID | None
    depth: int
    kind: str
    number: str | None
    anchor: str
    citation: str
    heading: str | None
    text: str
    notes: list[str]
    repealed: bool

    @classmethod
    def of(cls, unit: NormUnit) -> NormUnitOut:
        return cls(
            id=unit.id,
            parent_id=unit.parent_id,
            depth=unit.depth,
            kind=unit.kind.value,
            number=unit.number,
            anchor=unit.anchor,
            citation=unit.citation,
            heading=unit.heading,
            text=unit.text,
            notes=list(unit.notes),
            repealed=unit.repealed,
        )


class EditionContentOut(ApiModel):
    act: ActOut
    units: list[NormUnitOut]


class SearchHitOut(ApiModel):
    unit: NormUnitOut
    article_heading: str | None
    similarity: float

    @classmethod
    def of(cls, hit: NormSearchHit) -> SearchHitOut:
        return cls(
            unit=NormUnitOut.of(hit.unit),
            article_heading=hit.article_heading,
            similarity=round(1.0 - hit.distance, 4),
        )


class SearchResultOut(ApiModel):
    hits: list[SearchHitOut]
