from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from snoska.domain.checks.catalog import CheckCatalog
from snoska.domain.checks.quality import QualityReport
from snoska.ports.checks.quality import ModelTrialStore, QualityReportStore


@dataclass(frozen=True, slots=True)
class QualityView:
    """The latest measurement and whether it was taken on the current rules."""

    report: QualityReport | None
    current_revision: str
    # Candidate models measured to choose the one the checks run on.
    trials: Sequence[QualityReport] = ()

    @property
    def trial_documents(self) -> frozenset[str]:
        """Documents every trial that ran measured the model on: models are
        compared on the same documents."""
        measured = [trial.model_measured() for trial in self.trials]
        measured = [files for files in measured if files]
        return frozenset.intersection(*measured) if measured else frozenset()

    @property
    def current(self) -> bool:
        return self.report is not None and self.report.catalog_revision == self.current_revision


class QualityQueries:
    """Reads: how well the checks did on the reference set."""

    def __init__(
        self,
        store: QualityReportStore,
        catalog: CheckCatalog,
        trials: ModelTrialStore | None = None,
    ) -> None:
        self._store = store
        self._catalog = catalog
        self._trials = trials

    def latest(self) -> QualityView:
        return QualityView(
            report=self._store.load(),
            current_revision=self._catalog.revision,
            trials=tuple(self._trials.all()) if self._trials else (),
        )
