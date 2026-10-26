from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from footnote.domain.autofix.actions import AppliedChange


class ChangeJournal(Protocol):
    """What an automatic correction changed, kept with the version it made."""

    async def record(self, version_id: UUID, changes: Sequence[AppliedChange]) -> None: ...

    async def list_for_version(self, version_id: UUID) -> Sequence[AppliedChange]: ...
