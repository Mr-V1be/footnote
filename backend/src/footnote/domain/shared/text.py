from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"[\s\u00a0\u2007\u202f]+")


def normalize_whitespace(value: str) -> str:
    """Collapse every run of whitespace, including non-breaking spaces."""
    return _WHITESPACE.sub(" ", value).strip()


def normalize_text(value: str) -> str:
    """Canonical form used for hashing and comparison of document text."""
    return normalize_whitespace(unicodedata.normalize("NFC", value))
