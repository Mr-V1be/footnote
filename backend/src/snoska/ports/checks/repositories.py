from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from snoska.domain.checks.catalog import Severity
from snoska.domain.checks.finding import Finding
from snoska.domain.checks.result import CheckResult
from snoska.domain.checks.run import CheckRun, RunStatus


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Read projection of a run for lists: progress, open findings by severity
    and the checks that produced no verdict (so "no findings" is not overstated)."""

    run_id: UUID
    document_id: UUID
    version_id: UUID
    status: RunStatus
    total: int
    done: int
    open_by_severity: Mapping[Severity, int] = field(default_factory=dict)
    open_reviews: int = 0
    not_performed: int = 0


class CheckRunRepository(Protocol):
    async def add(self, run: CheckRun) -> None: ...

    async def get(self, run_id: UUID) -> CheckRun | None: ...

    async def lock(self, run_id: UUID) -> CheckRun | None:
        """Load and lock the row until the end of the transaction."""
        ...

    async def save(self, run: CheckRun) -> None:
        """Persist changes if the stored revision is still the loaded one.

        Raises ConcurrentModificationError otherwise.
        """
        ...

    async def pending_for_version(self, version_id: UUID) -> CheckRun | None:
        """A queued or running run of the version, if there is one."""
        ...

    async def latest_for_version(self, version_id: UUID) -> CheckRun | None: ...

    async def latest_summaries(self, version_ids: Collection[UUID]) -> Mapping[UUID, RunSummary]:
        """The latest run of each version, keyed by version id."""
        ...


class CheckResultRepository(Protocol):
    async def add(self, result: CheckResult) -> None: ...

    async def list_for_run(self, run_id: UUID) -> Sequence[CheckResult]: ...


class FindingRepository(Protocol):
    async def add_many(self, findings: Sequence[Finding]) -> None: ...

    async def get(self, finding_id: UUID) -> Finding | None: ...

    async def save(self, finding: Finding) -> None:
        """Persist a review if the stored revision is still the loaded one.

        Raises ConcurrentModificationError otherwise.
        """
        ...

    async def list_for_run(self, run_id: UUID) -> Sequence[Finding]: ...

    async def reviewed_before(self, document_id: UUID, run_id: UUID) -> Mapping[str, Finding]:
        """Reviewed findings of the document's earlier runs, newest per fingerprint."""
        ...

    async def count_for_run(self, run_id: UUID) -> int: ...
