from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from footnote.domain.documents.structure import Block, BlockKind, Requisite, RequisiteKind

# Requisites cluster at the top (header) and the bottom (signature area) of
# a document. Restricting detectors to these zones keeps body text that merely
# mentions a date or a number from being taken for a requisite.
HEADER_ZONE_BLOCKS = 14
TAIL_ZONE_BLOCKS = 14


class Zone(StrEnum):
    HEADER = "header"
    TAIL = "tail"
    ANYWHERE = "anywhere"


# A date or a number that belongs to a cited act ("Федерального закона от
# 27.07.2006 № 152-ФЗ") is the act's requisite, not the document's.
_ACT_BEFORE_DATE = re.compile(
    r"(?:закон[а-я]*|кодекс[а-я]*|указ[а-я]*|постановлени[а-я]*)"
    r"(?:\s+Российской\s+Федерации)?\s+от\s*$",
    re.IGNORECASE,
)
_ACT_NUMBER = re.compile(r"\d+-Ф?К?З$")


@dataclass(frozen=True, slots=True)
class PatternDetector:
    """Finds one requisite kind by a pattern within a document zone.

    ``not_after`` rejects a match that the text before it marks as something
    else; ``not_value`` rejects a match by its own value.
    """

    kind: RequisiteKind
    zone: Zone
    pattern: re.Pattern[str]
    first_only: bool = True
    group: int | str = 0
    not_after: re.Pattern[str] | None = None
    not_value: re.Pattern[str] | None = None

    def find(self, block: Block) -> Iterable[tuple[int, int, str]]:
        for match in self.pattern.finditer(block.text):
            start, end = match.span(self.group)
            value = match.group(self.group)
            if self.not_after is not None and self.not_after.search(block.text[:start]):
                continue
            if self.not_value is not None and self.not_value.search(value):
                continue
            yield start, end, value
            if self.first_only:
                return


_MONTHS = "января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря"
_DOC_TYPES = (
    "ПРИКАЗ|РАСПОРЯЖЕНИЕ|ПОСТАНОВЛЕНИЕ|ПОЛОЖЕНИЕ|ПОЛИТИКА|СОГЛАСИЕ|ДОГОВОР|"
    "ИНСТРУКЦИЯ|ПРАВИЛА|РЕГЛАМЕНТ|ПОРЯДОК|АКТ|ПРОТОКОЛ|УВЕДОМЛЕНИЕ|ОБЯЗАТЕЛЬСТВО|"
    "СОГЛАШЕНИЕ|ДОВЕРЕННОСТЬ|СЛУЖЕБНАЯ ЗАПИСКА|ДОКЛАДНАЯ ЗАПИСКА"
)
_LEGAL_FORM = (
    r"(?:Общество с ограниченной ответственностью|Акционерное общество|"
    r"Публичное акционерное общество|Непубличное акционерное общество|"
    r"Индивидуальный предприниматель|ООО|ПАО|НАО|АО|ЗАО|ИП|ФГУП|МУП|ГБУ|АНО)"
)
_INITIALS_SURNAME = r"[А-ЯЁ]\.\s?[А-ЯЁ]\.\s?[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?"
_SURNAME_INITIALS = r"[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?\s[А-ЯЁ]\.\s?[А-ЯЁ]\."

DEFAULT_DETECTORS: tuple[PatternDetector, ...] = (
    PatternDetector(
        kind=RequisiteKind.ORGANIZATION_NAME,
        zone=Zone.HEADER,
        pattern=re.compile(rf"{_LEGAL_FORM}\s*[«\"][^»\"]{{2,120}}[»\"]"),
    ),
    PatternDetector(
        kind=RequisiteKind.DOCUMENT_TYPE,
        zone=Zone.HEADER,
        pattern=re.compile(rf"^\s*({_DOC_TYPES})(?=\s|$|\s*№)", re.MULTILINE),
        group=1,
    ),
    PatternDetector(
        kind=RequisiteKind.DATE,
        zone=Zone.HEADER,
        # Any spelling of a date counts as the requisite; whether the spelling
        # follows the standard is a check of its own.
        pattern=re.compile(
            rf"(?<![\d.])(?:\d{{1,2}}\.\d{{1,2}}\.\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}}"
            rf"|«?\d{{1,2}}»?\s(?:{_MONTHS})\s\d{{4}})(?:\s?г\.)?(?![\d.]\d)"
        ),
        not_after=_ACT_BEFORE_DATE,
    ),
    PatternDetector(
        kind=RequisiteKind.REGISTRATION_NUMBER,
        zone=Zone.HEADER,
        pattern=re.compile(r"№\s?([0-9A-Za-zА-Яа-яЁё][0-9A-Za-zА-Яа-яЁё/\-.]{0,30})"),
        not_value=_ACT_NUMBER,
    ),
    PatternDetector(
        kind=RequisiteKind.PLACE,
        zone=Zone.HEADER,
        pattern=re.compile(r"(?:^|\s)((?:г\.|город)\s?[А-ЯЁ][а-яё]+(?:[\s-][А-ЯЁ][а-яё]+)*)"),
        group=1,
    ),
    PatternDetector(
        kind=RequisiteKind.ACCESS_RESTRICTION,
        zone=Zone.HEADER,
        pattern=re.compile(
            r"^\s*(Конфиденциально|Для служебного пользования|Коммерческая тайна)\s*$",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    PatternDetector(
        kind=RequisiteKind.APPROVAL_STAMP,
        zone=Zone.HEADER,
        pattern=re.compile(r"^\s*(УТВЕРЖДАЮ|УТВЕРЖДЕН[АОЫ]?)\b", re.MULTILINE),
        group=1,
    ),
    PatternDetector(
        kind=RequisiteKind.TITLE,
        zone=Zone.HEADER,
        pattern=re.compile(r"^\s*(Об?\s[а-яё].{3,})$", re.MULTILINE),
        group=1,
    ),
    PatternDetector(
        kind=RequisiteKind.ATTACHMENT_NOTE,
        zone=Zone.ANYWHERE,
        pattern=re.compile(r"^\s*(Приложени[ея]\s?:)", re.MULTILINE),
        group=1,
    ),
    PatternDetector(
        kind=RequisiteKind.SIGNATURE,
        zone=Zone.TAIL,
        pattern=re.compile(rf"({_INITIALS_SURNAME}|{_SURNAME_INITIALS})\s*$", re.MULTILINE),
        group=1,
        first_only=False,
    ),
    PatternDetector(
        kind=RequisiteKind.EXECUTOR_NOTE,
        zone=Zone.TAIL,
        pattern=re.compile(r"(?:^|\s)(Исп\.|Исполнитель:).{0,80}?(\+7|8)[\s(]*\d{3}"),
    ),
)


def _is_numbered_section(block: Block) -> bool:
    return block.label is not None and block.kind in (BlockKind.HEADING, BlockKind.LIST_ITEM)


def _header_zone(blocks: Sequence[Block]) -> Sequence[Block]:
    """Blocks before the numbered body starts, at most HEADER_ZONE_BLOCKS."""
    end = next((i for i, block in enumerate(blocks) if _is_numbered_section(block)), len(blocks))
    return blocks[: min(end, HEADER_ZONE_BLOCKS)]


def _tail_zone(blocks: Sequence[Block]) -> Sequence[Block]:
    """Blocks after the last numbered section, at most TAIL_ZONE_BLOCKS."""
    last = max((i for i, block in enumerate(blocks) if _is_numbered_section(block)), default=-1)
    tail = blocks[last + 1 :] if last >= 0 else blocks
    return tail[-TAIL_ZONE_BLOCKS:]


class RequisiteDetector:
    """Runs the registered detectors over the zones of a document."""

    def __init__(self, detectors: Sequence[PatternDetector] = DEFAULT_DETECTORS) -> None:
        self._detectors = tuple(detectors)

    def detect(self, blocks: Sequence[Block]) -> tuple[Requisite, ...]:
        # Table blocks take part too: header requisites are often laid out in
        # a borderless table (place on the left, date on the right).
        zones = {
            Zone.HEADER: _header_zone(blocks),
            Zone.TAIL: _tail_zone(blocks),
            Zone.ANYWHERE: blocks,
        }
        found: list[Requisite] = []
        for detector in self._detectors:
            for block in zones[detector.zone]:
                hits = list(detector.find(block))
                found.extend(
                    Requisite(
                        kind=detector.kind,
                        block_ordinal=block.ordinal,
                        start=start,
                        end=end,
                        value=value.strip(),
                    )
                    for start, end, value in hits
                )
                if hits and detector.first_only:
                    break
        return tuple(sorted(found, key=lambda r: (r.block_ordinal, r.start)))
