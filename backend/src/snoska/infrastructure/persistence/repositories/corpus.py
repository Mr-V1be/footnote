from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, cast, func, insert, literal_column, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from snoska.domain.corpus.acts import ActKind, Edition, EditionStatus, LegalAct
from snoska.domain.corpus.citation import article_title
from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.domain.corpus.units import NormUnit, UnitKind
from snoska.infrastructure.persistence.tables.corpus import (
    corpus_editions,
    edition_indexes,
    embedding_spaces,
    legal_acts,
    norm_embeddings,
    norm_units,
)
from snoska.infrastructure.persistence.vector_index import comparable_type, space_predicate
from snoska.ports.corpus_repositories import ActOverview, NormSearchHit

_INSERT_BATCH = 500


def _act(row: RowMapping) -> LegalAct:
    return LegalAct(
        code=row["code"],
        kind=ActKind(row["kind"]),
        short_title=row["short_title"],
        title=row["title"],
        adopted_on=row["adopted_on"],
    )


def _edition(row: RowMapping) -> Edition:
    return Edition(
        id=row["id"],
        act_code=row["act_code"],
        source_code=row["source_code"],
        source_revision=row["source_revision"],
        amended_by=row["amended_by"],
        content_sha256=row["content_sha256"],
        retrieved_at=row["retrieved_at"],
        status=EditionStatus(row["status"]),
        activated_at=row["activated_at"],
    )


def _unit(row: RowMapping) -> NormUnit:
    return NormUnit(
        id=row["id"],
        edition_id=row["edition_id"],
        parent_id=row["parent_id"],
        ordinal=row["ordinal"],
        depth=row["depth"],
        kind=UnitKind(row["kind"]),
        number=row["number"],
        anchor=row["anchor"],
        citation=row["citation"],
        heading=row["heading"],
        text=row["text"],
        notes=tuple(row["notes"]),
        repealed=row["repealed"],
        embedding_sha256=row["embedding_sha256"],
    )


def _unit_row(unit: NormUnit) -> dict[str, Any]:
    return {
        "id": unit.id,
        "edition_id": unit.edition_id,
        "parent_id": unit.parent_id,
        "ordinal": unit.ordinal,
        "depth": unit.depth,
        "kind": unit.kind.value,
        "number": unit.number,
        "anchor": unit.anchor,
        "citation": unit.citation,
        "heading": unit.heading,
        "text": unit.text,
        "notes": list(unit.notes),
        "repealed": unit.repealed,
        "embedding_sha256": unit.embedding_sha256,
    }


class SqlCorpusRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def upsert_act(self, act: LegalAct) -> None:
        statement = pg_insert(legal_acts).values(
            code=act.code,
            kind=act.kind.value,
            short_title=act.short_title,
            title=act.title,
            adopted_on=act.adopted_on,
        )
        await self._connection.execute(
            statement.on_conflict_do_update(
                index_elements=[legal_acts.c.code],
                set_={
                    "kind": statement.excluded.kind,
                    "short_title": statement.excluded.short_title,
                    "title": statement.excluded.title,
                    "adopted_on": statement.excluded.adopted_on,
                },
            )
        )

    async def list_acts(self) -> Sequence[ActOverview]:
        acts = await self._connection.execute(select(legal_acts).order_by(legal_acts.c.code))
        active = await self._connection.execute(
            select(corpus_editions).where(corpus_editions.c.status == EditionStatus.ACTIVE.value)
        )
        editions = {edition.act_code: edition for edition in map(_edition, active.mappings())}
        counts: dict[UUID, int] = {}
        if editions:
            grouped = await self._connection.execute(
                select(norm_units.c.edition_id, func.count())
                .where(norm_units.c.edition_id.in_([e.id for e in editions.values()]))
                .group_by(norm_units.c.edition_id)
            )
            counts = {row[0]: row[1] for row in grouped}
        overviews: list[ActOverview] = []
        for row in acts.mappings():
            act = _act(row)
            edition = editions.get(act.code)
            overviews.append(
                ActOverview(
                    act=act,
                    active_edition=edition,
                    unit_count=counts.get(edition.id, 0) if edition else 0,
                )
            )
        return overviews

    async def find_edition(self, act_code: str, content_sha256: str) -> Edition | None:
        result = await self._connection.execute(
            select(corpus_editions).where(
                corpus_editions.c.act_code == act_code,
                corpus_editions.c.content_sha256 == content_sha256,
            )
        )
        row = result.mappings().first()
        return _edition(row) if row else None

    async def add_edition(self, edition: Edition, units: Sequence[NormUnit]) -> None:
        await self._connection.execute(
            insert(corpus_editions).values(
                id=edition.id,
                act_code=edition.act_code,
                source_code=edition.source_code,
                source_revision=edition.source_revision,
                amended_by=edition.amended_by,
                content_sha256=edition.content_sha256,
                retrieved_at=edition.retrieved_at,
                status=edition.status.value,
                activated_at=edition.activated_at,
            )
        )
        rows = [_unit_row(unit) for unit in units]
        for start in range(0, len(rows), _INSERT_BATCH):
            await self._connection.execute(insert(norm_units), rows[start : start + _INSERT_BATCH])

    async def lock_edition(self, edition_id: UUID) -> Edition | None:
        result = await self._connection.execute(
            select(corpus_editions).where(corpus_editions.c.id == edition_id).with_for_update()
        )
        row = result.mappings().first()
        return _edition(row) if row else None

    async def active_edition(self, act_code: str) -> Edition | None:
        result = await self._connection.execute(
            select(corpus_editions).where(
                corpus_editions.c.act_code == act_code,
                corpus_editions.c.status == EditionStatus.ACTIVE.value,
            )
        )
        row = result.mappings().first()
        return _edition(row) if row else None

    async def save_edition(self, edition: Edition) -> None:
        await self._connection.execute(
            update(corpus_editions)
            .where(corpus_editions.c.id == edition.id)
            .values(status=edition.status.value, activated_at=edition.activated_at)
        )

    async def list_units(self, edition_id: UUID) -> Sequence[NormUnit]:
        result = await self._connection.execute(
            select(norm_units)
            .where(norm_units.c.edition_id == edition_id)
            .order_by(norm_units.c.ordinal)
        )
        return [_unit(row) for row in result.mappings()]

    async def get_unit_by_anchor(self, edition_id: UUID, anchor: str) -> NormUnit | None:
        result = await self._connection.execute(
            select(norm_units).where(
                norm_units.c.edition_id == edition_id, norm_units.c.anchor == anchor
            )
        )
        row = result.mappings().first()
        return _unit(row) if row else None

    async def units_by_anchors(
        self, edition_id: UUID, anchors: Collection[str]
    ) -> Sequence[NormUnit]:
        if not anchors:
            return []
        result = await self._connection.execute(
            select(norm_units)
            .where(norm_units.c.edition_id == edition_id, norm_units.c.anchor.in_(list(anchors)))
            .order_by(norm_units.c.ordinal)
        )
        return [_unit(row) for row in result.mappings()]

    async def units_by_ids(self, unit_ids: Collection[UUID]) -> Sequence[NormUnit]:
        if not unit_ids:
            return []
        result = await self._connection.execute(
            select(norm_units).where(norm_units.c.id.in_(list(unit_ids)))
        )
        return [_unit(row) for row in result.mappings()]

    async def get_edition(self, edition_id: UUID) -> Edition | None:
        result = await self._connection.execute(
            select(corpus_editions).where(corpus_editions.c.id == edition_id)
        )
        row = result.mappings().first()
        return _edition(row) if row else None

    async def missing_embeddings(self, space: EmbeddingSpace, hashes: Collection[str]) -> set[str]:
        if not hashes:
            return set()
        result = await self._connection.execute(
            select(norm_embeddings.c.content_sha256).where(
                norm_embeddings.c.space_code == space.code,
                norm_embeddings.c.content_sha256.in_(list(hashes)),
            )
        )
        present = {row[0] for row in result}
        return set(hashes) - present

    async def add_embeddings(
        self, space: EmbeddingSpace, vectors: Mapping[str, Sequence[float]], now: datetime
    ) -> None:
        if not vectors:
            return
        statement = pg_insert(norm_embeddings).values(
            [
                {
                    "space_code": space.code,
                    "content_sha256": sha,
                    "embedding": list(vector),
                    "created_at": now,
                }
                for sha, vector in vectors.items()
            ]
        )
        await self._connection.execute(statement.on_conflict_do_nothing())

    async def space_registered(self, space: EmbeddingSpace) -> bool:
        registered = await self._connection.scalar(
            select(embedding_spaces.c.dimensions).where(embedding_spaces.c.code == space.code)
        )
        return registered is not None and int(registered) == space.dimensions

    async def is_indexed(self, edition_id: UUID, space: EmbeddingSpace) -> bool:
        found = await self._connection.scalar(
            select(func.count())
            .select_from(edition_indexes)
            .where(
                edition_indexes.c.edition_id == edition_id,
                edition_indexes.c.space_code == space.code,
            )
        )
        return bool(found)

    async def mark_indexed(self, edition_id: UUID, space: EmbeddingSpace, now: datetime) -> None:
        await self._connection.execute(
            pg_insert(edition_indexes)
            .values(edition_id=edition_id, space_code=space.code, ready_at=now)
            .on_conflict_do_nothing()
        )

    async def indexed_active_editions(self, space: EmbeddingSpace, act_code: str | None) -> int:
        statement = (
            select(func.count())
            .select_from(corpus_editions)
            .join(
                edition_indexes,
                (edition_indexes.c.edition_id == corpus_editions.c.id)
                & (edition_indexes.c.space_code == space.code),
            )
            .where(corpus_editions.c.status == EditionStatus.ACTIVE.value)
        )
        if act_code is not None:
            statement = statement.where(corpus_editions.c.act_code == act_code)
        return int(await self._connection.scalar(statement) or 0)

    async def active_editions(self) -> Sequence[Edition]:
        result = await self._connection.execute(
            select(corpus_editions).where(corpus_editions.c.status == EditionStatus.ACTIVE.value)
        )
        return [_edition(row) for row in result.mappings()]

    async def search(
        self, space: EmbeddingSpace, vector: Sequence[float], *, act_code: str | None, limit: int
    ) -> Sequence[NormSearchHit]:
        embedding = cast(norm_embeddings.c.embedding, comparable_type(space))
        distance = embedding.cosine_distance(list(vector)).label("distance")
        editions = corpus_editions
        statement = (
            select(norm_units, distance)
            .select_from(norm_embeddings)
            .join(norm_units, norm_units.c.embedding_sha256 == norm_embeddings.c.content_sha256)
            .join(editions, editions.c.id == norm_units.c.edition_id)
            .join(
                edition_indexes,
                (edition_indexes.c.edition_id == editions.c.id)
                & (edition_indexes.c.space_code == space.code),
            )
            .where(
                text(space_predicate(space, "norm_embeddings")),
                editions.c.status == EditionStatus.ACTIVE.value,
            )
            .order_by(literal_column("distance"))
            .limit(limit)
        )
        if act_code is not None:
            statement = statement.where(editions.c.act_code == act_code)
        result = await self._connection.execute(statement)
        rows = list(result.mappings())
        headings = await self._article_headings([row["id"] for row in rows])
        return [
            NormSearchHit(
                unit=_unit(row),
                article_heading=headings.get(row["id"]),
                distance=float(row["distance"]),
            )
            for row in rows
        ]

    async def _article_headings(self, unit_ids: Sequence[UUID]) -> dict[UUID, str]:
        """Heading of the enclosing article for each unit, in one round trip."""
        if not unit_ids:
            return {}
        result = await self._connection.execute(
            text(
                """
                WITH RECURSIVE chain AS (
                    SELECT u.id AS origin, u.id, u.parent_id, u.kind, u.number, u.heading
                    FROM norm_units u WHERE u.id = ANY(:ids)
                    UNION ALL
                    SELECT c.origin, p.id, p.parent_id, p.kind, p.number, p.heading
                    FROM norm_units p JOIN chain c ON p.id = c.parent_id
                )
                SELECT origin, number, heading FROM chain WHERE kind = 'article'
                """
            ),
            {"ids": list(unit_ids)},
        )
        return {row.origin: article_title(row.number, row.heading) for row in result}
