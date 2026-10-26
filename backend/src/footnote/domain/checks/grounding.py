from __future__ import annotations

import re
import unicodedata

# A quote must be found in the passage it claims to come from. Matching
# forgives what a reader would not notice (case, spacing, the kind of quote
# marks and dashes, «ё») and an ellipsis standing for omitted words, bare or
# in the brackets an editor puts around it: "…", "...", "[...]", "(…)".
_ELLIPSIS = re.compile(r"\s*[\[(<]?\s*(?:\u2026|\.{3})\s*[\])>]?\s*")
_EQUIVALENT = str.maketrans(
    {
        "«": '"',
        "»": '"',
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u2013": "-",
        "\u2014": "-",
        "\u2010": "-",
        "\u2011": "-",
        "ё": "е",
        "Ё": "Е",
    }
)
MIN_QUOTE_CHARS = 8
_CELL_SEPARATOR = "|"
# Punctuation a quote may end or start with although the passage goes on.
_EDGE_PUNCTUATION = ".,;:!?"


def _normalized(text: str) -> tuple[str, list[int]]:
    """Comparable form of ``text`` and, for each of its characters, the index
    of the original character it came from."""
    folded: list[str] = []
    origin: list[int] = []
    previous_space = True
    for index, original in enumerate(text):
        comparable = unicodedata.normalize("NFC", original).translate(_EQUIVALENT).casefold()
        # A cell separator in a quoted table row stands where the text has a tab.
        if comparable.isspace() or comparable == _CELL_SEPARATOR:
            if previous_space:
                continue
            comparable = " "
            previous_space = True
        else:
            previous_space = False
        for piece in comparable:
            folded.append(piece)
            origin.append(index)
    while folded and folded[-1] == " ":
        folded.pop()
        origin.pop()
    return "".join(folded), origin


def locate_parts(text: str, quote: str) -> tuple[tuple[int, int], ...] | None:
    """The spans of ``text`` each part of the quote reproduces, in order, or
    None if the quote is not the text's.

    Parts are separated by an ellipsis and must appear in order. Quotes
    shorter than a few characters prove nothing and are rejected.
    """
    parts = [
        trimmed
        for part in _ELLIPSIS.split(quote.strip())
        if (trimmed := part.strip().strip(_EDGE_PUNCTUATION).strip())
    ]
    if not parts or sum(len(part.strip()) for part in parts) < MIN_QUOTE_CHARS:
        return None
    haystack, origin = _normalized(text)
    cursor = 0
    spans: list[tuple[int, int]] = []
    for part in parts:
        needle, _ = _normalized(part)
        found = haystack.find(needle, cursor) if needle else -1
        if found < 0:
            return None
        cursor = found + len(needle)
        spans.append((origin[found], origin[cursor - 1] + 1))
    return tuple(spans)


def locate_quote(text: str, quote: str) -> tuple[int, int] | None:
    """The span of ``text`` the quote reproduces, from its first part to its
    last, or None if it does not."""
    spans = locate_parts(text, quote)
    if spans is None:
        return None
    return spans[0][0], spans[-1][1]
