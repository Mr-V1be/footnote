from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RunChanged:
    """A run's progress or state changed; the run itself is the source of truth."""

    organization_id: UUID
    run_id: UUID


class RunChanges(Protocol):
    async def next(self, within_seconds: float) -> RunChanged | None:
        """The next change, or None if nothing changed within the given time."""
        ...


class RunChangeFeed(Protocol):
    def subscribe(self) -> AbstractAsyncContextManager[RunChanges]:
        """Changes of every run from now on, until the context exits."""
        ...
