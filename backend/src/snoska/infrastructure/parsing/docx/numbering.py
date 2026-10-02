from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from lxml.etree import _Element

from snoska.infrastructure.parsing.docx.xml import attr, child, int_attr, w

MAX_LEVELS = 9
_PLACEHOLDER = re.compile(r"%([1-9])")
# Word's Cyrillic sequence omits letters that are not used for enumeration.
_RUSSIAN_LETTERS = "абвгдежзиклмнопрстуфхцчшщэюя"
_LATIN_LETTERS = "abcdefghijklmnopqrstuvwxyz"
_ROMAN = (
    (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
    (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"),
)  # fmt: skip
# Symbol-font bullets live in the private use area; show a plain bullet.
_PRIVATE_USE = re.compile("[\\uf000-\\uf8ff]")
DEFAULT_BULLET = "•"


def _letters(value: int, alphabet: str) -> str:
    size = len(alphabet)
    repeat = (value - 1) // size + 1
    return alphabet[(value - 1) % size] * repeat


def _roman(value: int) -> str:
    out: list[str] = []
    for number, letters in _ROMAN:
        while value >= number:
            out.append(letters)
            value -= number
    return "".join(out)


_FORMATTERS: dict[str, Callable[[int], str]] = {
    "decimal": str,
    "decimalZero": lambda value: f"{value:02d}",
    "lowerLetter": lambda value: _letters(value, _LATIN_LETTERS),
    "upperLetter": lambda value: _letters(value, _LATIN_LETTERS).upper(),
    "russianLower": lambda value: _letters(value, _RUSSIAN_LETTERS),
    "russianUpper": lambda value: _letters(value, _RUSSIAN_LETTERS).upper(),
    "lowerRoman": _roman,
    "upperRoman": lambda value: _roman(value).upper(),
    "none": lambda _value: "",
}


def format_number(value: int, num_fmt: str) -> str:
    """Render a counter in a Word number format; unknown formats fall back to digits."""
    return _FORMATTERS.get(num_fmt, str)(value)


@dataclass(frozen=True, slots=True)
class _Level:
    num_fmt: str
    text: str
    start: int
    legal: bool


@dataclass(slots=True)
class _ListState:
    counters: list[int] = field(default_factory=lambda: [0] * MAX_LEVELS)


class NumberingResolver:
    """Computes list labels exactly as Word renders them («1.2.», «а)», «•»).

    Counters are kept per list instance (numId) and deeper levels restart
    whenever a shallower level advances.
    """

    def __init__(self, numbering_root: _Element | None) -> None:
        self._abstract: dict[str, dict[int, _Level]] = {}
        self._instances: dict[str, str] = {}
        self._overrides: dict[str, dict[int, int]] = {}
        self._state: dict[str, _ListState] = {}
        if numbering_root is None:
            return
        for abstract in numbering_root.findall(w("abstractNum")):
            abstract_id = attr(abstract, "abstractNumId")
            if abstract_id is not None:
                self._abstract[abstract_id] = self._levels(abstract)
        for num in numbering_root.findall(w("num")):
            num_id = attr(num, "numId")
            abstract_id = attr(child(num, "abstractNumId"), "val")
            if num_id is None or abstract_id is None:
                continue
            self._instances[num_id] = abstract_id
            overrides: dict[int, int] = {}
            for override in num.findall(w("lvlOverride")):
                level = int_attr(override, "ilvl")
                start = int_attr(child(override, "startOverride"), "val")
                if level is not None and start is not None:
                    overrides[level] = start
            self._overrides[num_id] = overrides

    @staticmethod
    def _levels(abstract: _Element) -> dict[int, _Level]:
        levels: dict[int, _Level] = {}
        for lvl in abstract.findall(w("lvl")):
            index = int_attr(lvl, "ilvl")
            if index is None or index >= MAX_LEVELS:
                continue
            levels[index] = _Level(
                num_fmt=attr(child(lvl, "numFmt"), "val") or "decimal",
                text=attr(child(lvl, "lvlText"), "val") or "",
                start=int_attr(child(lvl, "start"), "val") or 1,
                legal=child(lvl, "isLgl") is not None,
            )
        return levels

    def is_bullet(self, num_id: str, level: int) -> bool:
        spec = self._level(num_id, level)
        return spec is not None and spec.num_fmt == "bullet"

    def _level(self, num_id: str, level: int) -> _Level | None:
        abstract_id = self._instances.get(num_id)
        if abstract_id is None:
            return None
        return self._abstract.get(abstract_id, {}).get(level)

    def next_label(self, num_id: str, level: int) -> str | None:
        abstract_id = self._instances.get(num_id)
        levels = self._abstract.get(abstract_id or "")
        if not levels or level not in levels:
            return None
        spec = levels[level]
        if spec.num_fmt == "bullet":
            return _PRIVATE_USE.sub(DEFAULT_BULLET, spec.text) or DEFAULT_BULLET
        state = self._state.setdefault(num_id, _ListState())
        overrides = self._overrides.get(num_id, {})
        for index in range(MAX_LEVELS):
            if state.counters[index] == 0 and index < level and index in levels:
                state.counters[index] = overrides.get(index, levels[index].start)
        if state.counters[level] == 0:
            state.counters[level] = overrides.get(level, spec.start)
        else:
            state.counters[level] += 1
        for deeper in range(level + 1, MAX_LEVELS):
            state.counters[deeper] = 0

        def substitute(match: re.Match[str]) -> str:
            index = int(match.group(1)) - 1
            source = levels.get(index)
            if source is None:
                return ""
            fmt = "decimal" if spec.legal else source.num_fmt
            return format_number(state.counters[index], fmt)

        label = _PLACEHOLDER.sub(substitute, spec.text).strip()
        return label or None
