from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from footnote.domain.checks.catalog import CheckMethod
from footnote.domain.checks.outcome import CitedProvision, ResultStatus, TextLocation


@dataclass(frozen=True, slots=True)
class CheckResult:
    """The record of one check within a run, findings or not.

    Keeping passed and failed checks alike lets the interface say what was
    checked, not only what was found, and lets a crashed run resume.
    ``model`` names the language model for model checks.
    """

    run_id: UUID
    organization_id: UUID
    check_code: str
    method: CheckMethod
    status: ResultStatus
    evidence: tuple[TextLocation, ...]
    cited: CitedProvision | None
    error_code: str | None
    attempts: int
    duration_ms: int
    model: str | None
    finished_at: datetime
