from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from footnote.domain.billing.plans import Plan, UsageMetric
from footnote.domain.shared.errors import DomainError

# A DOCX has no pages until it is printed; it is counted as printed at 14 pt.
CHARACTERS_PER_PAGE = 1800


class QuotaExceededError(DomainError):
    """The plan's monthly limit would be passed. Reported as 402."""

    code = "quota_exceeded"

    def __init__(self, metric: UsageMetric, limit: int, used: int, requested: int) -> None:
        super().__init__(
            f"{metric}: {used} of {limit} used, {requested} more requested",
        )
        self.metric, self.limit, self.used, self.requested = metric, limit, used, requested


class LedgerReason(StrEnum):
    CHECK_RUN = "check_run"
    AUTOFIX = "autofix"
    QUESTION = "question"


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One line of usage: always whole units, always with a reason and a
    reference to what caused it (a run, a document, a question)."""

    id: UUID
    organization_id: UUID
    metric: UsageMetric
    quantity: int
    reason: LedgerReason
    reference: str
    period_start: date
    created_at: datetime

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("ledger quantities are whole positive units")


def counted_pages(page_count: int | None, characters: int) -> int:
    """Pages a version counts for: a PDF's own, a DOCX's as printed."""
    if page_count:
        return page_count
    return max(1, math.ceil(characters / CHARACTERS_PER_PAGE))


def ensure_allowance(plan: Plan, metric: UsageMetric, used: int, requested: int) -> None:
    limit = plan.limit(metric)
    if used + requested > limit:
        raise QuotaExceededError(metric, limit, used, requested)
