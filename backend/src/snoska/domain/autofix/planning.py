from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence

from snoska.domain.autofix.actions import (
    FixAction,
    FixPlan,
    ReplaceText,
    SetFirstLineIndent,
    SetFontSize,
    SetLineSpacing,
    SetMargins,
    Skipped,
    SkipReason,
)
from snoska.domain.checks.catalog import CheckCatalog, CheckDefinition, CheckMethod
from snoska.domain.checks.finding import Finding, ReviewStatus
from snoska.domain.documents.structure import DocumentStructure

_NUMERIC_DATE = re.compile(r"^(\d{1,2})([./-])(\d{1,2})\2(\d{2}|\d{4})$")
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_SURNAME_FIRST = re.compile(r"^([А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?)\s+([А-ЯЁ]\.\s?(?:[А-ЯЁ]\.)?)$")
_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
_TWO_DIGIT_CENTURY = 2000
# Decisions that leave a finding to be corrected.
_OUTSTANDING = (ReviewStatus.OPEN, ReviewStatus.ACCEPTED)


def standard_date(value: str) -> str | None:
    """A date in the standard spelling 05.06.2026, or None if not a date."""
    iso = _ISO_DATE.match(value)
    if iso:
        year, month, day = iso.groups()
        return f"{day}.{month}.{year}"
    numeric = _NUMERIC_DATE.match(value)
    if numeric is None:
        return None
    day, _, month, year = numeric.groups()
    full_year = int(year) + _TWO_DIGIT_CENTURY if len(year) == 2 else int(year)
    return f"{int(day):02d}.{int(month):02d}.{full_year}"


def initials_first(name: str) -> str | None:
    match = _SURNAME_FIRST.match(name.strip())
    if match is None:
        return None
    surname, initials = match.groups()
    return f"{initials.replace(' ', '')} {surname}"


def arabic_label(label: str) -> str | None:
    """A Roman section number as an Arabic one: "IV." becomes "4."."""
    letters = label.rstrip(".").strip()
    if not letters or any(letter not in _ROMAN for letter in letters):
        return None
    total = 0
    for current, following in zip(letters, [*letters[1:], ""], strict=True):
        value = _ROMAN[current]
        total += -value if following and _ROMAN[following] > value else value
    return f"{total}." if label.endswith(".") else str(total)


def _blocks(findings: Sequence[Finding]) -> tuple[int, ...]:
    ordinals = {
        place.block_ordinal
        for finding in findings
        for place in (finding.places or ((finding.location,) if finding.location else ()))
    }
    return tuple(sorted(ordinals))


Planner = Callable[[CheckDefinition, Sequence[Finding], DocumentStructure], list[FixAction]]


def _number(check: CheckDefinition, name: str) -> float:
    value = check.params[name]
    if not isinstance(value, int | float):
        raise TypeError(f"{check.code}: {name} is not a number")
    return float(value)


def _margins(
    check: CheckDefinition, _: Sequence[Finding], __: DocumentStructure
) -> list[FixAction]:
    return [
        SetMargins(
            check.code,
            *(_number(check, f"min_{side}_mm") for side in ("left", "right", "top", "bottom")),
        )
    ]


def _font(
    check: CheckDefinition, found: Sequence[Finding], _: DocumentStructure
) -> list[FixAction]:
    return [
        SetFontSize(check.code, _blocks(found), _number(check, "min_pt"), _number(check, "max_pt"))
    ]


def _spacing(
    check: CheckDefinition, found: Sequence[Finding], _: DocumentStructure
) -> list[FixAction]:
    return [
        SetLineSpacing(check.code, _blocks(found), _number(check, "min"), _number(check, "max"))
    ]


def _indent(
    check: CheckDefinition, found: Sequence[Finding], _: DocumentStructure
) -> list[FixAction]:
    return [SetFirstLineIndent(check.code, _blocks(found), _number(check, "indent_mm"))]


def _quoted(structure: DocumentStructure, finding: Finding) -> str | None:
    location = finding.location
    if location is None:
        return None
    block = next((b for b in structure.blocks if b.ordinal == location.block_ordinal), None)
    return block.text[location.start : location.end] if block else None


def _replacements(
    check: CheckDefinition,
    found: Sequence[Finding],
    structure: DocumentStructure,
    rewrite: Callable[[str], str | None],
) -> list[FixAction]:
    actions: list[FixAction] = []
    for finding in found:
        before = _quoted(structure, finding)
        after = rewrite(before) if before else None
        if before and after and finding.location is not None:
            actions.append(ReplaceText(check.code, finding.location.block_ordinal, before, after))
    return actions


def _dates(
    check: CheckDefinition, found: Sequence[Finding], structure: DocumentStructure
) -> list[FixAction]:
    return _replacements(check, found, structure, standard_date)


def _signatures(
    check: CheckDefinition, found: Sequence[Finding], structure: DocumentStructure
) -> list[FixAction]:
    return _replacements(check, found, structure, initials_first)


def _numbering(
    check: CheckDefinition, found: Sequence[Finding], structure: DocumentStructure
) -> list[FixAction]:
    """Roman numbers become Arabic ones; too deep a nesting is left to a person."""
    labels = {block.ordinal: block.label for block in structure.blocks if block.label}
    blocks = [
        place.block_ordinal
        for finding in found
        for place in (finding.places or ((finding.location,) if finding.location else ()))
    ]
    actions: list[FixAction] = []
    for ordinal in sorted(set(blocks)):
        label = labels.get(ordinal)
        arabic = arabic_label(label) if label else None
        if label and arabic:
            actions.append(ReplaceText(check.code, ordinal, label, arabic))
    return actions


# Corrections by the rule a check runs. A check whose rule is missing here
# is never corrected automatically.
PLANNERS: Mapping[str, Planner] = {
    "page_margins": _margins,
    "body_font_size": _font,
    "line_spacing": _spacing,
    "paragraph_indent": _indent,
    "date_format": _dates,
    "signature_initials_first": _signatures,
    "numbering_arabic": _numbering,
}


def correctable(check: CheckDefinition) -> bool:
    return check.method is CheckMethod.DETERMINISTIC and (check.rule or "") in PLANNERS


def plan_fixes(
    catalog: CheckCatalog,
    findings: Sequence[Finding],
    structure: DocumentStructure,
    *,
    editable: bool,
) -> FixPlan:
    """What an automatic correction of formatting would do with these findings."""
    by_check: dict[str, list[Finding]] = {}
    skipped: list[Skipped] = []
    for finding in findings:
        if finding.review not in _OUTSTANDING:
            continue
        check = catalog.get(finding.check_code)
        if check.method is CheckMethod.MODEL:
            skipped.append(Skipped(check.code, str(finding.id), SkipReason.LEGAL))
        elif not editable:
            skipped.append(Skipped(check.code, str(finding.id), SkipReason.NOT_EDITABLE))
        elif not correctable(check):
            skipped.append(Skipped(check.code, str(finding.id), SkipReason.NEEDS_PERSON))
        else:
            by_check.setdefault(check.code, []).append(finding)
    actions: list[FixAction] = []
    for code, found in by_check.items():
        check = catalog.get(code)
        planned = PLANNERS[check.rule or ""](check, found, structure)
        if not planned:
            skipped.extend(Skipped(code, str(finding.id), SkipReason.UNSAFE) for finding in found)
        actions.extend(planned)
    return FixPlan(actions=tuple(actions), skipped=tuple(skipped))
