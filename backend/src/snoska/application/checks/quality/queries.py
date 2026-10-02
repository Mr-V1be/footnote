from __future__ import annotations

from dataclasses import dataclass

from snoska.domain.checks.catalog import CheckCatalog
from snoska.domain.checks.quality import QualityReport
from snoska.ports.checks.quality import QualityReportStore


@dataclass(frozen=True, slots=True)
class QualityView:
    """The latest measurement and whether it was taken on the current rules."""

    report: QualityReport | None
    current_revision: str

    @property
    def current(self) -> bool:
        return self.report is not None and self.report.catalog_revision == self.current_revision


class QualityQueries:
    """Reads: how well the checks did on the reference set."""

    def __init__(self, store: QualityReportStore, catalog: CheckCatalog) -> None:
        self._store = store
        self._catalog = catalog

    def latest(self) -> QualityView:
        return QualityView(report=self._store.load(), current_revision=self._catalog.revision)
