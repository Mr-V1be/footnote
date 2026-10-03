from __future__ import annotations

import shutil
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from snoska.application.checks.deterministic import DeterministicExecutor
from snoska.application.checks.engine import CheckEngine, DocumentUnderCheck, ExecutorSession
from snoska.application.checks.quality.benchmark import CheckBenchmark
from snoska.bootstrap.container import load_check_catalog
from snoska.bootstrap.settings import ChecksSettings
from snoska.domain.checks.catalog import CheckDefinition, CheckMethod
from snoska.domain.checks.outcome import ResultStatus
from snoska.domain.checks.quality import (
    DocumentTiming,
    Metrics,
    Observation,
    QualityReport,
)
from snoska.domain.checks.rules.registry import DEFAULT_RULES
from snoska.domain.documents.formats import SUPPORTED_FORMATS
from snoska.domain.documents.requisites import RequisiteDetector
from snoska.infrastructure.checks.quality_store import JsonQualityReportStore
from snoska.infrastructure.checks.reference import YamlReferenceSet
from snoska.infrastructure.parsing.docx.parser import DocxParser
from snoska.infrastructure.parsing.ocr.tesseract import TesseractConfig, TesseractOcrEngine
from snoska.infrastructure.parsing.pdf.parser import PdfLimits, PdfParser
from snoska.infrastructure.parsing.registry import ParserRegistry
from snoska.ports.ai import ModelNotConfiguredError
from snoska.ports.checks.quality import ReferenceDocument, ReferenceSetError

SETTINGS = ChecksSettings()
MOMENT = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return MOMENT


class _Store:
    def __init__(self) -> None:
        self.saved: QualityReport | None = None

    def load(self) -> QualityReport | None:
        return self.saved

    def save(self, report: QualityReport) -> None:
        self.saved = report


class _NoModel:
    """The model executor as it is while no provider is connected."""

    method = CheckMethod.MODEL

    async def open(
        self,
        document: DocumentUnderCheck,  # noqa: ARG002 - the executor protocol
        checks: Sequence[CheckDefinition],  # noqa: ARG002
    ) -> ExecutorSession:
        raise ModelNotConfiguredError("no model API is configured")


def _observation(code: str, *, expected: bool, status: ResultStatus) -> Observation:
    return Observation(
        document="a.docx",
        check_code=code,
        family="formatting",
        method=CheckMethod.DETERMINISTIC,
        expected_violation=expected,
        status=status,
    )


def _benchmark(references: YamlReferenceSet | _Labels, store: _Store) -> CheckBenchmark:
    parsers = ParserRegistry(
        [DocxParser(), PdfParser(TesseractOcrEngine(TesseractConfig()), PdfLimits())]
    )
    engine = CheckEngine(
        {
            CheckMethod.DETERMINISTIC: DeterministicExecutor(DEFAULT_RULES),
            CheckMethod.MODEL: _NoModel(),
        }
    )
    return CheckBenchmark(
        references,
        parsers,
        load_check_catalog(SETTINGS),
        engine,
        RequisiteDetector(),
        store,
        _Clock(),
        model_name=None,
    )


class _Labels:
    """One real document with labels written in the test."""

    def __init__(self, expected: frozenset[str]) -> None:
        self._document = ReferenceDocument(
            file_name="prikaz-zarya.docx",
            title="Приказ",
            kind="order",
            format_code="docx",
            pages=1,
            expected=expected,
        )

    def documents(self) -> Sequence[ReferenceDocument]:
        return [self._document]

    async def content(self, document: ReferenceDocument) -> bytes:
        return (SETTINGS.reference_dir / document.file_name).read_bytes()


def test_needs_review_is_a_miss_and_errors_stay_out() -> None:
    metrics = Metrics()
    for observation in (
        _observation("x", expected=True, status=ResultStatus.VIOLATION),
        _observation("x", expected=True, status=ResultStatus.NEEDS_REVIEW),
        _observation("x", expected=False, status=ResultStatus.VIOLATION),
        _observation("x", expected=False, status=ResultStatus.PASSED),
        _observation("x", expected=True, status=ResultStatus.ERROR),
    ):
        metrics = metrics.add(observation)
    assert (metrics.true_positives, metrics.false_positives) == (1, 1)
    assert (metrics.false_negatives, metrics.true_negatives) == (1, 1)
    assert (metrics.reviews, metrics.errors, metrics.observations) == (1, 1, 5)
    assert metrics.precision == pytest.approx(0.5)
    assert metrics.recall == pytest.approx(0.5)
    assert Metrics().precision is None


def test_report_store_round_trip(tmp_path: Path) -> None:
    report = QualityReport(
        measured_at=MOMENT,
        catalog_revision="abc",
        model=None,
        documents=(
            DocumentTiming(
                file_name="a.docx",
                title="А",
                kind="order",
                pages=1,
                typical=True,
                parse_ms=12,
                deterministic_ms=1,
                model_ms=None,
            ),
        ),
        observations=(_observation("x", expected=True, status=ResultStatus.VIOLATION),),
    )
    store = JsonQualityReportStore(tmp_path / "quality" / "benchmark.json")
    assert store.load() is None
    store.save(report)
    assert store.load() == report
    assert report.typical is not None
    assert report.typical.total_ms is None


def test_reference_labels_must_name_existing_files(tmp_path: Path) -> None:
    (tmp_path / "labels.yaml").write_text(
        "documents:\n  - {file: missing.docx, title: T, kind: order, pages: 1, violations: []}\n",
        encoding="utf-8",
    )
    with pytest.raises(ReferenceSetError, match="missing"):
        YamlReferenceSet(tmp_path, SUPPORTED_FORMATS).documents()


async def test_a_label_for_a_check_of_another_kind_stops_the_benchmark() -> None:
    labels = _Labels(frozenset({"personal_data.consent_term"}))
    with pytest.raises(ReferenceSetError, match="consent_term"):
        await _benchmark(labels, _Store()).run()


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed")
async def test_reference_set_reproduces_the_committed_measurement() -> None:
    """The rules' numbers in data/quality and docs/quality.md are what the code
    gives today, on the current catalogue; the model part waits for a provider."""
    store = _Store()
    report = await _benchmark(
        YamlReferenceSet(SETTINGS.reference_dir, SUPPORTED_FORMATS), store
    ).run()
    assert store.saved == report

    rules = report.by_method()[CheckMethod.DETERMINISTIC]
    assert rules.recall == pytest.approx(1.0)
    assert rules.precision is not None
    assert rules.precision >= 0.9
    model = report.by_method()[CheckMethod.MODEL]
    assert model.errors == model.observations
    assert report.typical is not None
    assert report.typical.pages >= 8
    assert report.typical.model_ms is None

    committed = JsonQualityReportStore(SETTINGS.quality_report).load()
    assert committed is not None
    assert committed.catalog_revision == report.catalog_revision

    def verdicts(source: QualityReport) -> set[tuple[str, str, ResultStatus]]:
        return {
            (item.document, item.check_code, item.status)
            for item in source.observations
            if item.method is CheckMethod.DETERMINISTIC
        }

    assert verdicts(committed) == verdicts(report)
