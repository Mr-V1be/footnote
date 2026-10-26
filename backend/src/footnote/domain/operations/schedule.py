from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PeriodicTask:
    """Background work the platform does on its own, every ``interval``."""

    name: str
    job_name: str
    interval: timedelta


@dataclass(slots=True)
class TaskState:
    name: str
    next_run_at: datetime
    last_run_at: datetime | None = None

    def due(self, now: datetime) -> bool:
        return self.next_run_at <= now

    def ran(self, now: datetime, interval: timedelta) -> None:
        self.last_run_at = now
        # Missed runs are not replayed: the next one is one interval away.
        self.next_run_at = now + interval


class WatchOutcome(StrEnum):
    UNCHANGED = "unchanged"
    NEW_EDITION = "new_edition"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class EditionCheck:
    """One look at the official source for a newer redaction of an act."""

    id: UUID
    act_code: str
    checked_at: datetime
    outcome: WatchOutcome
    revision: str | None
    edition_id: UUID | None
    error: str | None = None
