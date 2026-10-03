from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TimeCursor:
    """A position in a list ordered newest first by a moment, then by id:
    the next page holds what comes strictly after it."""

    at: datetime
    id: UUID
