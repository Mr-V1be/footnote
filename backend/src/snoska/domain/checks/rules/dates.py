from __future__ import annotations

import re

from snoska.domain.checks.outcome import CheckOutcome, Detail, TextLocation
from snoska.domain.checks.rules.base import Offence, RuleParams, offences_outcome
from snoska.domain.documents.structure import Block, DocumentStructure

# Numeric dates in any spelling. The standard spelling is 05.06.2016; the
# others are reported. Section numbers such as 7.0.97 are told apart by the
# day and month ranges and by the leading zeros a clause number never has.
_NUMERIC = re.compile(r"(?<![\d.])(\d{1,2})([./-])(\d{1,2})\2(\d{4}|\d{2})(?![\d.]\d)")
_ISO = re.compile(r"(?<![\d.])(\d{4})-(\d{2})-(\d{2})(?!\d)")
_DAYS = range(1, 32)
_MONTHS = range(1, 13)
_FULL_YEAR = 4


def _numeric_offence(match: re.Match[str]) -> bool:
    day, separator, month, year = match.groups()
    if int(day) not in _DAYS or int(month) not in _MONTHS:
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
        for block in structure.blocks:
            offences.extend(
                self._offence(block, match)
                for match in _NUMERIC.finditer(block.text)
                if _numeric_offence(match)
            )
            offences.extend(
                self._offence(block, match)
                for match in _ISO.finditer(block.text)
                if int(match.group(2)) in _MONTHS and int(match.group(3)) in _DAYS
            )
        return offences_outcome(offences, Detail.message("date_format_widespread"))

    @staticmethod
    def _offence(block: Block, match: re.Match[str]) -> Offence:
        return Offence(
            block,
            Detail.message("date_format", value=match.group(0)),
            location=TextLocation(block.ordinal, match.start(), match.end()),
        )
