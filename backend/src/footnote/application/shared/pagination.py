from __future__ import annotations

from collections.abc import Callable, Sequence
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


def next_page[ItemT, CursorT](
    rows: Sequence[ItemT], size: int, cursor_of: Callable[[ItemT], CursorT]
) -> Page[ItemT, CursorT]:
    """A page from ``size + 1`` rows: the extra row only says there is more."""
    items = rows[:size]
    more = len(rows) > size and len(items) > 0
    return Page(items=items, next_cursor=cursor_of(items[-1]) if more else None)
