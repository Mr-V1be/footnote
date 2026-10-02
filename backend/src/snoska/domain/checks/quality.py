from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from snoska.domain.checks.catalog import CheckMethod
from snoska.domain.checks.outcome import ResultStatus


@dataclass(frozen=True, slots=True)
class Observation:
    """One check on one reference document: what was expected and what came out."""

    document: str
    check_code: str
    family: str
    method: CheckMethod
    expected_violation: bool
    status: ResultStatus


@dataclass(frozen=True, slots=True)
class Metrics:
    """Confusion counts of a group of observations.

    A violation is the positive class. Only a reported violation counts as
    found: an expected violation that ended as "needs review", "not
    applicable" or "passed" is a miss for recall, and "needs review" is
    counted on its own so its share stays visible. Errors are left out of
    both measures and reported.
    """

    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0
    reviews: int = 0
    errors: int = 0

    @property
    def precision(self) -> float | None:
        reported = self.true_positives + self.false_positives
        return self.true_positives / reported if reported else None

    @property
    def recall(self) -> float | None:
        expected = self.true_positives + self.false_negatives
        return self.true_positives / expected if expected else None

    @property
    def observations(self) -> int:
        return (
            self.true_positives
            + self.false_positives
            + self.false_negatives
            + self.true_negatives
            + self.errors
        )

    def add(self, observation: Observation) -> Metrics:
        status, expected = observation.status, observation.expected_violation
        if status is ResultStatus.ERROR:
            return _bump(self, errors=1)
        reviewed = 1 if status is ResultStatus.NEEDS_REVIEW else 0
        if status is ResultStatus.VIOLATION:
            return _bump(self, true_positives=1) if expected else _bump(self, false_positives=1)
        if expected:
            return _bump(self, false_negatives=1, reviews=reviewed)
        return _bump(self, true_negatives=1, reviews=reviewed)


def _bump(metrics: Metrics, **deltas: int) -> Metrics:
    values = {
        name: getattr(metrics, name) + deltas.get(name, 0)
        for name in (
            "true_positives",
            "false_positives",
            "false_negatives",
            "true_negatives",
            "reviews",
            "errors",
        )
    }
    return Metrics(**values)


def group_metrics[K](
    observations: Iterable[Observation], key: Callable[[Observation], K]
) -> Mapping[K, Metrics]:
    grouped: dict[K, Metrics] = defaultdict(Metrics)
    for observation in observations:
        group = key(observation)
        grouped[group] = grouped[group].add(observation)
    return dict(grouped)
