from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from footnote.domain.operations.schedule import EditionCheck, TaskState


class TaskStateRepository(Protocol):
    """Platform-wide; claimed rows are locked against other workers."""

    async def ensure(self, state: TaskState) -> None:
        """Register a task the first time; keep an existing schedule."""
        ...

    async def claim_due(self, now: datetime, names: Sequence[str]) -> Sequence[TaskState]: ...

    async def save(self, state: TaskState) -> None: ...

    async def get(self, name: str) -> TaskState | None: ...


class EditionCheckLog(Protocol):
    """Platform-wide history of looks at the corpus sources."""

    async def add(self, check: EditionCheck) -> None: ...

    async def latest(self, *, limit: int) -> Sequence[EditionCheck]: ...
