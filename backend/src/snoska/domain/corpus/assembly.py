from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from snoska.domain.corpus.acts import LegalAct
from snoska.domain.corpus.citation import PathStep, anchor_of, article_title, citation_of
from snoska.domain.corpus.embedding import EMBEDDABLE_KINDS, content_hash, embedding_text
from snoska.domain.corpus.units import NormUnit, ParsedUnit, UnitKind
from snoska.domain.shared.locale import SOURCE_LOCALE


@dataclass(frozen=True, slots=True)
class _ChainLink:
    kind: UnitKind
    number: str | None
    heading: str | None
    text: str


@dataclass(frozen=True, slots=True)
class AssembledEdition:
    units: tuple[NormUnit, ...]
    embedding_texts: Mapping[str, str]


def edition_content_hash(roots: Sequence[ParsedUnit]) -> str:
    """Hash of the normative content, independent of the source's markup."""

    def serialise(unit: ParsedUnit) -> dict[str, Any]:
        return {
            "k": unit.kind.value,
            "n": unit.number,
            "h": unit.heading,
            "t": unit.text,
            "r": unit.repealed,
            "c": [serialise(child) for child in unit.children],
        }

    payload = json.dumps([serialise(root) for root in roots], ensure_ascii=False, sort_keys=True)
    return content_hash(payload)


def _is_embeddable(kind: UnitKind, text: str, repealed: bool) -> bool:
    return kind in EMBEDDABLE_KINDS and bool(text.strip()) and not repealed


def _passage(chain: Sequence[_ChainLink], citation: str) -> str:
    headings: list[str] = []
    lead_ins: list[str] = []
    for link in chain[:-1]:
        if link.kind is UnitKind.ARTICLE:
            headings.append(article_title(link.number, link.heading))
        elif link.kind in EMBEDDABLE_KINDS and link.text:
            lead_ins.append(link.text)
    return embedding_text(citation, headings, lead_ins, chain[-1].text)


def assemble_edition(
    edition_id: UUID,
    act: LegalAct,
    roots: Sequence[ParsedUnit],
    new_id: Callable[[], UUID],
) -> AssembledEdition:
    """Flatten a parsed tree into stored units with anchors and citations."""
    units: list[NormUnit] = []
    texts: dict[str, str] = {}

    def visit(
        unit: ParsedUnit,
        parent_id: UUID | None,
        path: list[PathStep],
        chain: list[_ChainLink],
        index_in_parent: int,
    ) -> None:
        step_path = [*path, PathStep(kind=unit.kind, number=unit.number)]
        step_chain = [*chain, _ChainLink(unit.kind, unit.number, unit.heading, unit.text)]
        citation = citation_of(step_path, act.short_title.resolve(SOURCE_LOCALE))
        sha: str | None = None
        if _is_embeddable(unit.kind, unit.text, unit.repealed):
            passage = _passage(step_chain, citation)
            sha = content_hash(passage)
            texts[sha] = passage
        unit_id = new_id()
        units.append(
            NormUnit(
                id=unit_id,
                edition_id=edition_id,
                parent_id=parent_id,
                ordinal=len(units),
                depth=len(path),
                kind=unit.kind,
                number=unit.number,
                anchor=anchor_of(step_path, index_in_parent),
                citation=citation,
                heading=unit.heading,
                text=unit.text,
                notes=unit.notes,
                repealed=unit.repealed,
                embedding_sha256=sha,
            )
        )
        for index, child in enumerate(unit.children, start=1):
            visit(child, unit_id, step_path, step_chain, index)

    for index, root in enumerate(roots, start=1):
        visit(root, None, [], [], index)
    return AssembledEdition(units=tuple(units), embedding_texts=texts)


def embedding_texts_for(units: Sequence[NormUnit]) -> dict[str, str]:
    """Rebuild retrieval passages of stored units, keyed by their hash.

    Uses the same composition as ``assemble_edition`` so hashes match.
    """
    by_id = {unit.id: unit for unit in units}
    texts: dict[str, str] = {}
    for unit in units:
        if unit.embedding_sha256 is None:
            continue
        chain: list[_ChainLink] = []
        cursor: NormUnit | None = unit
        while cursor is not None:
            chain.append(_ChainLink(cursor.kind, cursor.number, cursor.heading, cursor.text))
            cursor = by_id.get(cursor.parent_id) if cursor.parent_id else None
        chain.reverse()
        texts[unit.embedding_sha256] = _passage(chain, unit.citation)
    return texts
