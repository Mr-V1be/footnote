from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 30


@dataclass(frozen=True, slots=True)
class Page[ItemT, CursorT]:
    items: Sequence[ItemT]
    next_cursor: CursorT | None


def clamp_page_size(requested: int | None) -> int:
    if requested is None:
        return DEFAULT_PAGE_SIZE
    return max(1, min(requested, MAX_PAGE_SIZE))
