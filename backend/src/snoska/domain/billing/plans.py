from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from snoska.domain.shared.errors import NotFoundError, ValidationError


class UsageMetric(StrEnum):
    PAGES = "pages"
    CHECKS = "checks"
    QUESTIONS = "questions"
    AUTOFIXES = "autofixes"
    MEMBERS = "members"


# Metrics counted in the ledger month by month; members are counted live.
METERED: tuple[UsageMetric, ...] = (
    UsageMetric.PAGES,
    UsageMetric.CHECKS,
    UsageMetric.QUESTIONS,
    UsageMetric.AUTOFIXES,
)


class UnknownPlanError(NotFoundError):
    code = "unknown_plan"


@dataclass(frozen=True, slots=True)
class Plan:
    """A plan as the catalogue states it: monthly price and limits."""

    code: str
    rank: int
    price_kopecks: int
    limits: Mapping[UsageMetric, int]

    def __post_init__(self) -> None:
        if self.price_kopecks < 0:
            raise ValidationError(f"plan {self.code}: negative price")
        missing = set(UsageMetric) - set(self.limits)
        if missing:
            raise ValidationError(f"plan {self.code}: no limit for {sorted(missing)}")

    @property
    def free(self) -> bool:
        return self.price_kopecks == 0

    def limit(self, metric: UsageMetric) -> int:
        return self.limits[metric]


class PlanCatalog:
    def __init__(self, plans: Iterable[Plan], default: str, currency: str) -> None:
        self._plans = {plan.code: plan for plan in plans}
        if default not in self._plans:
            raise ValidationError(f"default plan {default!r} is not in the catalogue")
        self.default = self._plans[default]
        self.currency = currency

    def get(self, code: str) -> Plan:
        try:
            return self._plans[code]
        except KeyError as exc:
            raise UnknownPlanError(f"unknown plan {code!r}") from exc

    def all(self) -> tuple[Plan, ...]:
        return tuple(sorted(self._plans.values(), key=lambda plan: plan.rank))
