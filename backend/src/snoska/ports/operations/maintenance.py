from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class TenantPurge(Protocol):
    """Removes every row of one tenant, append-only tables included. Only
    for resetting a demo stand: it runs with the schema owner's rights."""

    async def purge(self, organization_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class Backlog:
    """Background work not done yet, across every tenant."""

    # Jobs written to the outbox and not yet handed to the queue.
    jobs: int
    # Versions queued for reading or being read.
    versions: int
    # Check runs queued or running.
    checks: int

    @property
    def idle(self) -> bool:
        return not (self.jobs or self.versions or self.checks)


class BacklogProbe(Protocol):
    """Counts the background work in progress (for scripts that must wait
    for it, like the refresh of the demo stand)."""

    async def backlog(self) -> Backlog: ...
