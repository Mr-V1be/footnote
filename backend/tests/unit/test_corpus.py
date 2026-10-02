from __future__ import annotations

import gzip
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from snoska.domain.corpus.acts import ActKind, LegalAct
from snoska.domain.corpus.assembly import (
    assemble_edition,
    edition_content_hash,
    embedding_texts_for,
)
from snoska.domain.corpus.citation import PathStep, anchor_of, citation_of
from snoska.domain.corpus.units import UnitKind
from snoska.infrastructure.corpus_sources.law_html import ParsedLaw, parse_law_html
from snoska.infrastructure.corpus_sources.pravo_ips import PORTAL_ENCODING

SNAPSHOT = Path(__file__).parents[2] / "data" / "corpus" / "snapshots" / "152-fz.pravo-ips.html.gz"
ACT = LegalAct("152-fz", ActKind.FEDERAL_LAW, "152-ФЗ", "О персональных данных", date(2006, 7, 27))


@pytest.fixture(scope="module")
def law() -> ParsedLaw:
    return parse_law_html(gzip.decompress(SNAPSHOT.read_bytes()).decode(PORTAL_ENCODING))


def test_citation_reads_innermost_first() -> None:
    path = [
        PathStep(UnitKind.CHAPTER, "4"),
        PathStep(UnitKind.ARTICLE, "18.1"),
        PathStep(UnitKind.PART, "1"),
        PathStep(UnitKind.CLAUSE, "2"),
    ]
    assert citation_of(path, "152-ФЗ") == "п. 2 ч. 1 ст. 18.1 152-ФЗ"
    assert anchor_of(path, 2) == "st-18.1/ch-1/p-2"


def test_unnumbered_text_gets_positional_anchor() -> None:
    path = [PathStep(UnitKind.ARTICLE, "2"), PathStep(UnitKind.PARAGRAPH, None)]
    assert anchor_of(path, 1) == "st-2/t-1"


def test_snapshot_parses_to_the_full_structure(law: ParsedLaw) -> None:
    assert law.amended_by is not None
    assert law.amended_by.endswith("-ФЗ")
    chapters = [u for u in law.units if u.kind is UnitKind.CHAPTER]
    articles = [a for c in chapters for a in c.children if a.kind is UnitKind.ARTICLE]
    assert len(chapters) == 6
    numbers = {a.number for a in articles}
    assert {"3", "6", "9", "18.1", "22.1"} <= numbers
    article_9 = next(a for a in articles if a.number == "9")
    part_4 = next(p for p in article_9.children if p.number == "4")
    assert [c.number for c in part_4.children][:3] == ["1", "2", "3"]


def test_amendment_notes_are_kept_apart_from_text(law: ParsedLaw) -> None:
    article_1 = law.units[0].children[0]
    part_1 = article_1.children[0]
    assert "(В редакции" not in part_1.text
    assert any("В редакции" in note for note in part_1.notes)


def test_repealed_provisions_are_marked_without_text(law: ParsedLaw) -> None:
    article_1 = law.units[0].children[0]
    part_2 = next(p for p in article_1.children if p.number == "2")
    clause_3 = next(c for c in part_2.children if c.number == "3")
    assert clause_3.repealed
    assert clause_3.text == ""


def test_embedding_passages_are_reproducible_from_stored_units(law: ParsedLaw) -> None:
    ids = iter(UUID(int=i) for i in range(1, 10_000))
    assembled = assemble_edition(uuid4(), ACT, law.units, lambda: next(ids))
    assert dict(assembled.embedding_texts) == embedding_texts_for(assembled.units)
    anchors = {unit.anchor for unit in assembled.units}
    assert "st-18.1/ch-1/p-2" in anchors
    passage = next(
        text
        for sha, text in assembled.embedding_texts.items()
        if any(
            u.anchor == "st-18.1/ch-1/p-2" and u.embedding_sha256 == sha for u in assembled.units
        )
    )
    assert passage.startswith("п. 2 ч. 1 ст. 18.1 152-ФЗ")
    assert "Статья 18.1." in passage


def test_content_hash_ignores_nothing_normative(law: ParsedLaw) -> None:
    assert edition_content_hash(law.units) == edition_content_hash(law.units)
    trimmed = law.units[:-1]
    assert edition_content_hash(trimmed) != edition_content_hash(law.units)
