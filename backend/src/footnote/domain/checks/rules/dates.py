from __future__ import annotations

import re

from footnote.domain.checks.outcome import CheckOutcome, Detail, TextLocation
from footnote.domain.checks.rules.base import Offence, RuleParams, offences_outcome
from footnote.domain.documents.structure import Block, DocumentStructure

# Numeric dates in any spelling. The standard spelling is 05.06.2016; the
# others are reported. Section numbers such as 7.0.97 are told apart by the
# day and month ranges and by the leading zeros a clause number never has.
_NUMERIC = re.compile(r"(?<![\d.])(\d{1,2})([./-])(\d{1,2})\2(\d{4}|\d{2})(?![\d.]\d)")
_ISO = re.compile(r"(?<![\d.])(\d{4})-(\d{2})-(\d{2})(?!\d)")
# A date in words, the other standard spelling: 5 июня 2016 г.
_WORDS = re.compile(
    r"(?<!\d)«?\d{1,2}»?\s(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября"
    r"|октября|ноября|декабря)\s\d{4}"
)
_DAYS = range(1, 32)
_MONTHS = range(1, 13)
_FULL_YEAR = 4


def _is_date(match: re.Match[str]) -> bool:
    day, _, month, _ = match.groups()
    return int(day) in _DAYS and int(month) in _MONTHS


def _numeric_offence(match: re.Match[str]) -> bool:
    day, separator, month, year = match.groups()
    if not _is_date(match):
        return False
    if separator != ".":
        return True
    if len(year) == _FULL_YEAR:
        return len(day) == 1 or len(month) == 1
    # A two-digit year only reads as a date when day and month are zero-padded.
    return len(day) == len(month) == 2


class DateFormatRule:
    """Dates are written as 05.06.2016 or in words: 5 июня 2016 г."""

    id = "date_format"

    def validate(self, params: RuleParams) -> None:
        return None

    def evaluate(self, structure: DocumentStructure, params: RuleParams) -> CheckOutcome:
        offences: list[Offence] = []
        dates = 0
        for block in structure.blocks:
            numeric = [match for match in _NUMERIC.finditer(block.text) if _is_date(match)]
            iso = [
                match
                for match in _ISO.finditer(block.text)
                if int(match.group(2)) in _MONTHS and int(match.group(3)) in _DAYS
            ]
            dates += len(numeric) + len(iso) + len(_WORDS.findall(block.text))
            offences.extend(
                self._offence(block, match) for match in numeric if _numeric_offence(match)
            )
            offences.extend(self._offence(block, match) for match in iso)
        return offences_outcome(offences, dates, Detail.message("date_format_widespread"), params)

    @staticmethod
    def _offence(block: Block, match: re.Match[str]) -> Offence:
        return Offence(
            block,
            Detail.message("date_format", value=match.group(0)),
            location=TextLocation(block.ordinal, match.start(), match.end()),
        )
