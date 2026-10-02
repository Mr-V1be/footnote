from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from snoska.domain.checks.catalog import LawNorm
from snoska.domain.corpus.citation import provision_text
from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.domain.corpus.units import NormUnit
from snoska.domain.shared.errors import NotFoundError
from snoska.ports.corpus_repositories import CorpusRepository
from snoska.ports.unit_of_work import UnitOfWorkFactory


class ProvisionNotFoundError(NotFoundError):
    code = "provision_not_found"


@dataclass(frozen=True, slots=True)
class Provision:
    """A provision of a law as it is quoted: citation and words of the edition."""

    edition_id: UUID
    act_code: str
    anchor: str
    citation: str
    text: str


async def _with_lead_ins(
    corpus: CorpusRepository, act_code: str, units: Sequence[NormUnit]
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
                citation=unit.citation,
                text=provision_text(unit.kind, unit.text, parent.text if parent else None),
            )
        )
    return provisions


class NormLibrary:
    """Provisions of the corpus for checks and their findings."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def provisions(self, norm: LawNorm) -> list[Provision]:
        """The norm's provisions in the edition in force, in the order of the norm."""
        async with self._uow_factory.for_platform() as uow:
            edition = await uow.corpus.active_edition(norm.act_code)
            if edition is None:
                raise ProvisionNotFoundError(f"no edition of {norm.act_code} is in force")
            units = await uow.corpus.units_by_anchors(edition.id, norm.anchors)
            provisions = await _with_lead_ins(uow.corpus, norm.act_code, units)
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
            return await _with_lead_ins(uow.corpus, act_code, units)

    async def citations(self, act_code: str, anchors: Collection[str]) -> Mapping[str, str]:
        """How provisions are cited in the edition in force, by anchor."""
        async with self._uow_factory.for_platform() as uow:
            edition = await uow.corpus.active_edition(act_code)
            if edition is None:
                return {}
            units = await uow.corpus.units_by_anchors(edition.id, anchors)
        return {unit.anchor: unit.citation for unit in units}

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
                for provision in await _with_lead_ins(uow.corpus, edition.act_code, units):
                    resolved[(edition_id, provision.anchor)] = provision
        return resolved
