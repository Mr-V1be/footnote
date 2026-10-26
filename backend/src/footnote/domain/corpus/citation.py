from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from footnote.domain.corpus.units import UnitKind
from footnote.domain.shared.locale import SOURCE_LOCALE, Locale, LocalizedText

_ANCHOR_PREFIX: dict[UnitKind, str] = {
    UnitKind.CHAPTER: "gl",
    UnitKind.ARTICLE: "st",
    UnitKind.PART: "ch",
    UnitKind.CLAUSE: "p",
    UnitKind.SUBCLAUSE: "pp",
}
_KIND_OF_PREFIX = {prefix: kind for kind, prefix in _ANCHOR_PREFIX.items()}

# A cited unit: its level and its number as the act writes it ("18.1", "а").
CitedStep = tuple[UnitKind, str]


@dataclass(frozen=True, slots=True)
class PathStep:
    kind: UnitKind
    number: str | None


@dataclass(frozen=True, slots=True)
class CitationStyle:
    """How a language cites a provision: the label of each level, the order
    of the levels and what separates them from each other and from the act."""

    labels: Mapping[UnitKind, str]
    outermost_first: bool
    separator: str
    act_separator: str
    # A subclause is numbered by a letter, set apart: «а» or (а).
    subclause: str

    def render(self, steps: Sequence[CitedStep], act: str) -> str:
        ordered = steps if self.outermost_first else tuple(reversed(steps))
        units = self.separator.join(
            f"{self.labels[kind]} "
            f"{self.subclause.format(number) if kind is UnitKind.SUBCLAUSE else number}"
            for kind, number in ordered
        )
        return f"{units}{self.act_separator}{act}" if units else act


CITATION_STYLES: Mapping[Locale, CitationStyle] = {
    # Russian legal usage, innermost first: «п. 2 ч. 1 ст. 18.1 152-ФЗ».
    Locale.RU: CitationStyle(
        labels={
            UnitKind.CHAPTER: "гл.",
            UnitKind.ARTICLE: "ст.",
            UnitKind.PART: "ч.",
            UnitKind.CLAUSE: "п.",
            UnitKind.SUBCLAUSE: "подп.",
        },
        outermost_first=False,
        separator=" ",
        act_separator=" ",
        subclause="«{}»",
    ),
    # As English renderings of Russian law read, outermost first:
    # "Art. 18.1, Part 1, Cl. 2, 152-FZ".
    Locale.EN: CitationStyle(
        labels={
            UnitKind.CHAPTER: "Ch.",
            UnitKind.ARTICLE: "Art.",
            UnitKind.PART: "Part",
            UnitKind.CLAUSE: "Cl.",
            UnitKind.SUBCLAUSE: "Subcl.",
        },
        outermost_first=True,
        separator=", ",
        act_separator=", ",
        subclause="({})",
    ),
}


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


def _path_steps(path: Sequence[PathStep]) -> tuple[CitedStep, ...]:
    has_article = any(step.kind is UnitKind.ARTICLE for step in path)
    return tuple(
        (step.kind, step.number)
        for step in path
        if step.number is not None
        and step.kind in _ANCHOR_PREFIX
        and not (step.kind is UnitKind.CHAPTER and has_article)
    )


def anchor_steps(anchor: str) -> tuple[CitedStep, ...]:
    """The numbered units an anchor names, outermost first. An anchor holds
    exactly the units a citation names (see ``anchor_of``): unnumbered
    units (``t-3``) are not cited."""
    steps: list[CitedStep] = []
    for part in anchor.split("/"):
        prefix, _, number = part.partition("-")
        kind = _KIND_OF_PREFIX.get(prefix)
        if kind is not None and number:
            steps.append((kind, number))
    return tuple(steps)


def citation_of(path: Sequence[PathStep], act_short_title: str) -> str:
    """The citation a unit is stored and shown to the model with, in the
    language of the law: «п. 2 ч. 1 ст. 18.1 152-ФЗ»."""
    return CITATION_STYLES[SOURCE_LOCALE].render(_path_steps(path), act_short_title)


def cite(anchor: str, act_short_title: LocalizedText) -> LocalizedText:
    """A provision of an act as each interface language cites it."""
    steps = anchor_steps(anchor)
    return LocalizedText(
        {
            locale: style.render(steps, act_short_title.resolve(locale))
            for locale, style in CITATION_STYLES.items()
        }
    )


def cite_clause(clause: str, standard: LocalizedText) -> LocalizedText:
    """A clause of a standard as each interface language cites it."""
    return LocalizedText(
        {
            locale: style.render(((UnitKind.CLAUSE, clause),), standard.resolve(locale))
            for locale, style in CITATION_STYLES.items()
        }
    )


# A point of a list reads only together with the lead-in of its part
# («Согласие … должно включать: … 4) цель обработки»).
_LEAD_IN_KINDS = frozenset({UnitKind.CLAUSE, UnitKind.SUBCLAUSE})


def provision_text(unit_kind: UnitKind, text: str, parent_text: str | None) -> str:
    """A provision as it is quoted to a reader or a model."""
    if unit_kind in _LEAD_IN_KINDS and parent_text:
        return f"{parent_text} … {text}"
    return text
