from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from snoska.api.schemas.common import ApiModel
from snoska.application.checks.quality.queries import QualityView
from snoska.domain.checks.quality import DocumentTiming, Metrics


class MetricsOut(ApiModel):
    """Confusion counts of a group of observations, with the shares derived.

    A share is null when there is nothing to count it from: no violation was
    reported (precision) or none is labelled (recall), or the checks did not
    run at all (see ``errors``).
    """

    observations: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    reviews: int
    errors: int
    precision: float | None
    recall: float | None

    @classmethod
    def of(cls, metrics: Metrics) -> MetricsOut:
        return cls(
            observations=metrics.observations,
            true_positives=metrics.true_positives,
            false_positives=metrics.false_positives,
            false_negatives=metrics.false_negatives,
            true_negatives=metrics.true_negatives,
            reviews=metrics.reviews,
            errors=metrics.errors,
            precision=metrics.precision,
            recall=metrics.recall,
        )


class GroupMetricsOut(ApiModel):
    code: str
    metrics: MetricsOut


class DocumentTimingOut(ApiModel):
    file_name: str
    title: str
    kind: str
    pages: int
    typical: bool
    parse_ms: int
    deterministic_ms: int
    model_ms: int | None
    total_ms: int | None

    @classmethod
    def of(cls, timing: DocumentTiming) -> DocumentTimingOut:
        return cls(
            file_name=timing.file_name,
            title=timing.title,
            kind=timing.kind,
            pages=timing.pages,
            typical=timing.typical,
            parse_ms=timing.parse_ms,
            deterministic_ms=timing.deterministic_ms,
            model_ms=timing.model_ms,
            total_ms=timing.total_ms,
        )


def _groups(grouped: Mapping[str, Metrics]) -> list[GroupMetricsOut]:
    return [GroupMetricsOut(code=code, metrics=MetricsOut.of(m)) for code, m in grouped.items()]


class QualityOut(ApiModel):
    """How the checks did on the labelled reference set, as last measured.

    ``current`` is false when the catalogue changed after the measurement.
    ``model`` is null when no model was connected: the model checks were
    not measured.
    """

    measured_at: datetime
    catalog_revision: str
    current: bool
    model: str | None
    documents: list[DocumentTimingOut]
    methods: list[GroupMetricsOut]
    families: list[GroupMetricsOut]
    checks: list[GroupMetricsOut]

    @classmethod
    def of(cls, view: QualityView) -> QualityOut | None:
        report = view.report
        if report is None:
            return None
        return cls(
            measured_at=report.measured_at,
            catalog_revision=report.catalog_revision,
            current=view.current,
            model=report.model,
            documents=[DocumentTimingOut.of(item) for item in report.documents],
            methods=_groups({method.value: m for method, m in report.by_method().items()}),
            families=_groups(report.by_family()),
            checks=_groups(report.by_check()),
        )
