from __future__ import annotations

import math
import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import replace

import structlog

from footnote.application.checks.embeddings import MemoryEmbeddings
from footnote.application.checks.engine import (
    CheckEngine,
    CheckErrorCode,
    DocumentUnderCheck,
    Executed,
)
from footnote.domain.checks.catalog import CheckCatalog, CheckDefinition, CheckMethod
from footnote.domain.checks.outcome import CheckOutcome
from footnote.domain.checks.quality import DocumentTiming, Observation, QualityReport
from footnote.domain.documents.requisites import RequisiteDetector
from footnote.domain.documents.structure import DocumentStructure
from footnote.ports.checks.quality import (
    ModelTrialStore,
    QualityReportStore,
    ReferenceDocument,
    ReferenceSet,
    ReferenceSetError,
)
from footnote.ports.clock import Clock
from footnote.ports.document_parsing import DocumentParserRegistry

log = structlog.get_logger(__name__)

MILLISECONDS = 1000
# Errors that mean the model part did not run at all, so it has no time.
_NOT_RUN = frozenset({CheckErrorCode.MODEL_NOT_CONFIGURED, CheckErrorCode.MODEL_UNAVAILABLE})

DocumentDone = Callable[[DocumentTiming], None]


class BenchmarkIncompleteError(Exception):
    """The measurement could not finish; the last one is kept."""


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * MILLISECONDS)


class CheckBenchmark:
    """Operations: run every applicable check on the reference set, compare
    the verdicts with the labels and keep the result for the product to show.

    Documents are parsed and checked the way the product does it, outside the
    database: passage vectors stay in memory. The deterministic and the model
    checks run one after the other so each part has its own time; in the
    product they run side by side.
    """

    def __init__(
        self,
        references: ReferenceSet,
        parsers: DocumentParserRegistry,
        catalog: CheckCatalog,
        engine: CheckEngine,
        detector: RequisiteDetector,
        store: QualityReportStore,
        clock: Clock,
        model_name: str | None,
    ) -> None:
        self._references = references
        self._parsers = parsers
        self._catalog = catalog
        self._engine = engine
        self._detector = detector
        self._store = store
        self._clock = clock
        self._model_name = model_name

    def model_requests(self, per_request: int, *, only: Collection[str] = ()) -> int:
        """Requests a measurement makes to the model: one per batch of a
        document's legal requirements (answers found invalid ask again)."""
        total = 0
        for reference in self._selected(only):
            legal = sum(
                1 for check in self._checks_for(reference) if check.method is CheckMethod.MODEL
            )
            total += math.ceil(legal / per_request)
        return total

    def _selected(self, only: Collection[str]) -> list[ReferenceDocument]:
        references = [
            reference
            for reference in self._references.documents()
            if not only or reference.file_name in only
        ]
        if not references:
            raise ReferenceSetError("no reference document to measure")
        return references

    async def run(
        self,
        on_document: DocumentDone | None = None,
        *,
        only: Collection[str] = (),
        store: QualityReportStore | ModelTrialStore | None = None,
    ) -> QualityReport:
        """Measure on the whole set, or on the files named in ``only``; the
        result goes to ``store`` (a model's trial) or the main measurement."""
        references = self._selected(only)
        timings: list[DocumentTiming] = []
        observations: list[Observation] = []
        for reference in references:
            checks = self._checks_for(reference)
            timing, outcomes = await self._measure(reference, checks)
            if any(
                outcome.error_code == CheckErrorCode.MODEL_DAILY_LIMIT
                for outcome in outcomes.values()
            ):
                # A measurement with unanswered requirements would understate
                # the model: nothing is kept, the last measurement stays.
                raise BenchmarkIncompleteError(
                    f"{reference.file_name}: the model's requests for today ran out"
                )
            timings.append(timing)
            observations.extend(
                Observation(
                    document=reference.file_name,
                    check_code=check.code,
                    family=check.family,
                    method=check.method,
                    expected_violation=check.code in reference.expected,
                    status=outcomes[check.code].status,
                )
                for check in checks
            )
            log.info("checks.benchmark_document", document=reference.file_name)
            if on_document is not None:
                on_document(timing)
        report = QualityReport(
            measured_at=self._clock.now(),
            catalog_revision=self._catalog.revision,
            model=self._model_name,
            documents=tuple(timings),
            observations=tuple(observations),
        )
        (store or self._store).save(report)
        return report

    def _checks_for(self, reference: ReferenceDocument) -> tuple[CheckDefinition, ...]:
        checks = self._catalog.applicable(reference.kind)
        unknown = reference.expected - {check.code for check in checks}
        if unknown:
            raise ReferenceSetError(
                f"{reference.file_name}: {', '.join(sorted(unknown))} "
                f"do not apply to the kind {reference.kind!r}"
            )
        return tuple(checks)

    async def _measure(
        self, reference: ReferenceDocument, checks: Sequence[CheckDefinition]
    ) -> tuple[DocumentTiming, dict[str, CheckOutcome]]:
        started = time.perf_counter()
        structure = await self._parse(reference)
        parse_ms = _elapsed_ms(started)
        document = DocumentUnderCheck(
            title=reference.title,
            kind=reference.kind,
            structure=structure,
            embeddings=MemoryEmbeddings(),
        )
        outcomes: dict[str, CheckOutcome] = {}

        async def record(executed: Executed) -> None:
            outcomes[executed.check.code] = executed.outcome

        spent: dict[CheckMethod, int] = {}
        for method in CheckMethod:
            group = [check for check in checks if check.method is method]
            started = time.perf_counter()
            await self._engine.run(document, group, record)
            spent[method] = _elapsed_ms(started)
        for check in checks:
            # A method without an executor leaves its checks without a verdict.
            outcomes.setdefault(check.code, CheckOutcome.failed(CheckErrorCode.INTERNAL_ERROR))
        model_ran = not any(
            outcomes[check.code].error_code in _NOT_RUN
            for check in checks
            if check.method is CheckMethod.MODEL
        )
        timing = DocumentTiming(
            file_name=reference.file_name,
            title=reference.title,
            kind=reference.kind,
            pages=reference.pages,
            typical=reference.typical,
            parse_ms=parse_ms,
            deterministic_ms=spent[CheckMethod.DETERMINISTIC],
            model_ms=spent[CheckMethod.MODEL] if model_ran else None,
        )
        return timing, outcomes

    async def _parse(self, reference: ReferenceDocument) -> DocumentStructure:
        content = await self._references.content(reference)
        parsed = await self._parsers.for_format(reference.format_code).parse(content)
        if not parsed.blocks:
            raise ReferenceSetError(f"{reference.file_name}: no text was extracted")
        structure = DocumentStructure(blocks=parsed.blocks, layout=parsed.layout)
        return replace(structure, requisites=self._detector.detect(structure.blocks))
