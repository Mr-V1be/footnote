from __future__ import annotations

import re
from dataclasses import dataclass

from footnote.domain.shared.text import normalize_whitespace

# Numbering typed by hand at the start of a paragraph: «1.», «1.2.», «2)»,
# «а)», «IV.», bullets. Captured separately so text and label stay apart.
_MANUAL_LABEL = re.compile(
    r"^(?P<label>"
    r"\d{1,3}(?:\.\d{1,3}){0,4}\.?(?=\s)"
    r"|\d{1,3}\)"
    r"|[а-яё]\)"
    r"|[a-z]\)"
    r"|[IVXLC]{1,6}\.(?=\s)"
    r"|[•·▪‒–—-](?=\s)"
    r")\s+(?P<rest>\S.*)$",
    re.DOTALL,
)
_BULLETS = frozenset("•·▪‒–—-")
_NON_HEADING_ENDINGS = (";", ",", ":")
# Approval and agreement stamps are typed in capitals but are requisites,
# not section headings.
_STAMP_WORDS = frozenset(
    {"УТВЕРЖДАЮ", "УТВЕРЖДЕН", "УТВЕРЖДЕНО", "УТВЕРЖДЕНА", "УТВЕРЖДЕНЫ", "СОГЛАСОВАНО"}
)
HEADING_MAX_CHARS = 160


# Symbol and Wingdings bullets are extracted from PDFs as private-use code points.
_PRIVATE_USE_BULLET = re.compile("[\\uf020-\\uf0ff]")
BULLET = "•"


def normalize_symbols(text: str) -> str:
    return _PRIVATE_USE_BULLET.sub(BULLET, text)


@dataclass(frozen=True, slots=True)
class ManualLabel:
    label: str
    text: str
    depth: int
    is_bullet: bool


def split_manual_label(text: str) -> ManualLabel | None:
    match = _MANUAL_LABEL.match(text)
    if match is None:
        return None
    label = match.group("label")
    rest = normalize_whitespace(match.group("rest"))
    if not rest:
        return None
    is_bullet = label in _BULLETS
    if is_bullet:
        depth = 0
    elif label[0].isdigit() and not label.endswith(")"):
        depth = label.rstrip(".").count(".")
    else:
        depth = 1
    return ManualLabel(label=label, text=rest, depth=depth, is_bullet=is_bullet)


def looks_like_heading(text: str, *, emphasized: bool, numbered_top: bool) -> bool:
    """Heuristic for headings that carry no heading style.

    A heading is short, single-line, does not read like a sentence (no
    trailing comma, colon or semicolon) and stands out: written in upper case,
    or bold as a whole and either numbered at the top level or unpunctuated.
    """
    stripped = text.strip()
    if not stripped or len(stripped) > HEADING_MAX_CHARS or "\n" in stripped:
        return False
    if stripped.endswith(_NON_HEADING_ENDINGS) or stripped.split(" ")[0] in _STAMP_WORDS:
        return False
    letters = [ch for ch in stripped if ch.isalpha()]
    if len(letters) > 3 and all(ch.isupper() for ch in letters):
        return True
    return emphasized and (numbered_top or not stripped.endswith("."))
