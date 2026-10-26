from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from footnote.domain.checks.catalog import LawNorm
from footnote.domain.corpus.citation import cite, provision_text
from footnote.domain.corpus.embedding import EmbeddingSpace
from footnote.domain.corpus.units import NormUnit
from footnote.domain.shared.errors import NotFoundError
from footnote.domain.shared.locale import LocalizedText
from footnote.ports.corpus.repositories import CorpusRepository
from footnote.ports.corpus.source import ActCatalog
from footnote.ports.unit_of_work import UnitOfWorkFactory


class ProvisionNotFoundError(NotFoundError):
    code = "provision_not_found"


@dataclass(frozen=True, slots=True)
class Provision:
    """A provision of a law as it is quoted: citation and words of the edition.

    The words are the law's own; the citation reads as each interface
    language cites the provision."""

    edition_id: UUID
    act_code: str
    anchor: str
    citation: LocalizedText
    text: str


class NormLibrary:
    """Provisions of the corpus for checks and their findings."""

    def __init__(self, uow_factory: UnitOfWorkFactory, acts: ActCatalog) -> None:
        self._uow_factory = uow_factory
        self._acts = acts

    def cite(self, act_code: str, anchor: str) -> LocalizedText:
        """How a provision of a tracked act is cited, in every interface language."""
        return cite(anchor, self._acts.get(act_code).act.short_title)

    async def _with_lead_ins(
        self, corpus: CorpusRepository, act_code: str, units: Sequence[NormUnit]
    ) -> list[Provision]:
        parent_ids = {unit.parent_id for unit in units if unit.parent_id is not None}
        parents = {parent.id: parent for parent in await corpus.units_by_ids(parent_ids)}
        provisions: list[Provision] = []
        for unit in units:
            parent = parents.get(unit.parent_id) if unit.parent_id else None
            provisions.append(
                Provision(
                    edition_id=unit.edition_id,
                    act_code=act_code,
                    anchor=unit.anchor,
                    citation=self.cite(act_code, unit.anchor),
                    text=provision_text(unit.kind, unit.text, parent.text if parent else None),
                )
            )
        return provisions

    async def provisions(self, norm: LawNorm) -> list[Provision]:
        """The norm's provisions in the edition in force, in the order of the norm."""
        async with self._uow_factory.for_platform() as uow:
            edition = await uow.corpus.active_edition(norm.act_code)
            if edition is None:
                raise ProvisionNotFoundError(f"no edition of {norm.act_code} is in force")
            units = await uow.corpus.units_by_anchors(edition.id, norm.anchors)
            provisions = await self._with_lead_ins(uow.corpus, norm.act_code, units)
        by_anchor = {provision.anchor: provision for provision in provisions}
        missing = [anchor for anchor in norm.anchors if anchor not in by_anchor]
        if missing:
            raise ProvisionNotFoundError(f"{norm.act_code}: no provisions {missing}")
        return [by_anchor[anchor] for anchor in norm.anchors]

    async def related(
        self,
        act_code: str,
        space: EmbeddingSpace,
        vector: Sequence[float],
        exclude: Collection[str],
        limit: int,
    ) -> list[Provision]:
        """Provisions closest in meaning to a requirement, beyond those it names."""
        if limit <= 0:
            return []
        async with self._uow_factory.for_platform() as uow:
            hits = await uow.corpus.search(
                space, vector, act_code=act_code, limit=limit + len(exclude)
            )
            units = [hit.unit for hit in hits if hit.unit.anchor not in exclude][:limit]
            return await self._with_lead_ins(uow.corpus, act_code, units)

    async def nearest(
        self, space: EmbeddingSpace, vector: Sequence[float], limit: int
    ) -> list[Provision]:
        """Provisions of every act in force closest in meaning to a question."""
        async with self._uow_factory.for_platform() as uow:
            hits = await uow.corpus.search(space, vector, act_code=None, limit=limit)
            by_edition: dict[UUID, list[NormUnit]] = {}
            for hit in hits:
                by_edition.setdefault(hit.unit.edition_id, []).append(hit.unit)
            found: dict[UUID, Provision] = {}
            for edition_id, units in by_edition.items():
                edition = await uow.corpus.get_edition(edition_id)
                if edition is None:
                    continue
                for unit, provision in zip(
                    units,
                    await self._with_lead_ins(uow.corpus, edition.act_code, units),
                    strict=True,
                ):
                    found[unit.id] = provision
        # In the order of closeness.
        return [found[hit.unit.id] for hit in hits if hit.unit.id in found]

    async def quotes(
        self, references: Collection[tuple[UUID, str]]
    ) -> Mapping[tuple[UUID, str], Provision]:
        """Quotes for findings: (edition, anchor) pairs resolved in one pass per edition."""
        by_edition: dict[UUID, set[str]] = {}
        for edition_id, anchor in references:
            by_edition.setdefault(edition_id, set()).add(anchor)
        resolved: dict[tuple[UUID, str], Provision] = {}
        async with self._uow_factory.for_platform() as uow:
            for edition_id, anchors in by_edition.items():
                edition = await uow.corpus.get_edition(edition_id)
                if edition is None:
                    continue
                units = await uow.corpus.units_by_anchors(edition_id, anchors)
                for provision in await self._with_lead_ins(uow.corpus, edition.act_code, units):
                    resolved[(edition_id, provision.anchor)] = provision
        return resolved
