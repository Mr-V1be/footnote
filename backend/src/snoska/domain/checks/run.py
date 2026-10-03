from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from snoska.domain.shared.errors import InvalidStateError


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunFailureCode(StrEnum):
    """Stable reasons a whole run could not finish (single checks fail on their own)."""

    VERSION_NOT_PARSED = "version_not_parsed"
    INTERNAL_ERROR = "internal_error"
    # The plan's monthly allowance was used up when the run was due.
    QUOTA_EXCEEDED = "quota_exceeded"


@dataclass(slots=True)
class CheckRun:
    """Checking one document version against the catalogue at one revision.

    Progress is ``done`` of ``total`` checks. A run interrupted by a worker
    crash is redelivered and resumes: checks already recorded are skipped.
    """

    id: UUID
    organization_id: UUID
    document_id: UUID
    version_id: UUID
    catalog_revision: str
    requested_by: UUID | None
    created_at: datetime
    status: RunStatus
    total: int
    done: int
    attempts: int
    started_at: datetime | None
    finished_at: datetime | None
    failure_code: RunFailureCode | None
    revision: int

    @classmethod
    def queue(
        cls,
        *,
        id: UUID,
        organization_id: UUID,
        document_id: UUID,
        version_id: UUID,
        catalog_revision: str,
        requested_by: UUID | None,
        now: datetime,
    ) -> CheckRun:
        return cls(
            id=id,
            organization_id=organization_id,
            document_id=document_id,
            version_id=version_id,
            catalog_revision=catalog_revision,
            requested_by=requested_by,
            created_at=now,
            status=RunStatus.QUEUED,
            total=0,
            done=0,
            attempts=0,
            started_at=None,
            finished_at=None,
            failure_code=None,
            revision=0,
        )

    @property
    def is_settled(self) -> bool:
        return self.status in (RunStatus.COMPLETED, RunStatus.FAILED)

    def start(self, total: int, done: int, now: datetime) -> None:
        """Begin or resume: ``done`` counts checks already recorded."""
        if self.is_settled:
            raise InvalidStateError(f"run is already {self.status}")
        if total < 0 or not 0 <= done <= total:
            raise ValueError(f"progress {done}/{total} is out of range")
        self.status = RunStatus.RUNNING
        self.total = total
        self.done = done
        self.attempts += 1
        self.started_at = self.started_at or now

    def advance(self) -> None:
        if self.status is not RunStatus.RUNNING:
            raise InvalidStateError(f"cannot record progress of a {self.status} run")
        if self.done >= self.total:
            raise InvalidStateError("every check is already recorded")
        self.done += 1

    def complete(self, now: datetime) -> None:
        if self.status is not RunStatus.RUNNING or self.done != self.total:
            raise InvalidStateError(
                f"cannot complete a {self.status} run at {self.done}/{self.total}"
            )
        self.status = RunStatus.COMPLETED
        self.finished_at = now

    def fail(self, code: RunFailureCode, now: datetime) -> None:
        if self.is_settled:
            raise InvalidStateError(f"run is already {self.status}")
        self.status = RunStatus.FAILED
        self.failure_code = code
        self.finished_at = now
