from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from snoska.domain.corpus.units import UnitKind

_ANCHOR_PREFIX: dict[UnitKind, str] = {
    UnitKind.CHAPTER: "gl",
    UnitKind.ARTICLE: "st",
    UnitKind.PART: "ch",
    UnitKind.CLAUSE: "p",
    UnitKind.SUBCLAUSE: "pp",
}

_CITATION_PREFIX: dict[UnitKind, str] = {
    UnitKind.CHAPTER: "гл.",
    UnitKind.ARTICLE: "ст.",
    UnitKind.PART: "ч.",
    UnitKind.CLAUSE: "п.",
    UnitKind.SUBCLAUSE: "подп.",
}


@dataclass(frozen=True, slots=True)
class PathStep:
    kind: UnitKind
    number: str | None


def article_title(number: str | None, heading: str | None) -> str:
    """How an article is named in passages and references: «Статья 6. Условия…»."""
    label = f"Статья {number}" if number else "Статья"
    return f"{label}. {heading}" if heading else label


def anchor_of(path: Sequence[PathStep], ordinal_in_parent: int) -> str:
    """Stable key of a unit. Chapters are skipped below the article level
    because article numbers are unique within a law."""
    steps: list[str] = []
    has_article = any(step.kind is UnitKind.ARTICLE for step in path)
    for step in path:
        if step.kind is UnitKind.CHAPTER and has_article:
            continue
        prefix = _ANCHOR_PREFIX.get(step.kind)
        if prefix is None or step.number is None:
            continue
        steps.append(f"{prefix}-{step.number}")
    last = path[-1]
    if last.number is None or last.kind not in _ANCHOR_PREFIX:
        steps.append(f"t-{ordinal_in_parent}")
    return "/".join(steps)


def citation_of(path: Sequence[PathStep], act_short_title: str) -> str:
    """Russian legal citation, innermost first: «п. 2 ч. 1 ст. 18.1 152-ФЗ»."""
    has_article = any(step.kind is UnitKind.ARTICLE for step in path)
    parts: list[str] = []
    for step in reversed(path):
        if step.kind is UnitKind.CHAPTER and has_article:
            continue
        prefix = _CITATION_PREFIX.get(step.kind)
        if prefix is None or step.number is None:
            continue
        number = f"«{step.number}»" if step.kind is UnitKind.SUBCLAUSE else step.number
        parts.append(f"{prefix} {number}")
    parts.append(act_short_title)
    return " ".join(parts)


# A point of a list reads only together with the lead-in of its part
# («Согласие … должно включать: … 4) цель обработки»).
_LEAD_IN_KINDS = frozenset({UnitKind.CLAUSE, UnitKind.SUBCLAUSE})


def provision_text(unit_kind: UnitKind, text: str, parent_text: str | None) -> str:
    """A provision as it is quoted to a reader or a model."""
    if unit_kind in _LEAD_IN_KINDS and parent_text:
        return f"{parent_text} … {text}"
    return text
