from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from snoska.domain.checks.catalog import CheckMethod
from snoska.domain.checks.outcome import ResultStatus
from snoska.domain.checks.quality import DocumentTiming, Observation, QualityReport

FORMAT_VERSION = 1


def _timing(item: DocumentTiming) -> dict[str, Any]:
    return {
        "file": item.file_name,
        "title": item.title,
        "kind": item.kind,
        "pages": item.pages,
        "typical": item.typical,
        "parse_ms": item.parse_ms,
        "deterministic_ms": item.deterministic_ms,
        "model_ms": item.model_ms,
    }


def _observation(item: Observation) -> dict[str, Any]:
    return {
        "document": item.document,
        "check": item.check_code,
        "family": item.family,
        "method": item.method.value,
        "expected_violation": item.expected_violation,
        "status": item.status.value,
    }


class JsonQualityReportStore:
    """Keeps the latest benchmark result as a JSON file in the repository,
    so the measurement the product shows is the one that was reviewed."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> QualityReport | None:
        if not self._path.is_file():
            return None
        data = json.loads(self._path.read_text(encoding="utf-8"))
        if data.get("format") != FORMAT_VERSION:
            raise ValueError(f"{self._path}: unsupported format {data.get('format')!r}")
        return QualityReport(
            measured_at=datetime.fromisoformat(data["measured_at"]),
            catalog_revision=data["catalog_revision"],
            model=data["model"],
            documents=tuple(
                DocumentTiming(
                    file_name=item["file"],
                    title=item["title"],
                    kind=item["kind"],
                    pages=item["pages"],
                    typical=item["typical"],
                    parse_ms=item["parse_ms"],
                    deterministic_ms=item["deterministic_ms"],
                    model_ms=item["model_ms"],
                )
                for item in data["documents"]
            ),
            observations=tuple(
                Observation(
                    document=item["document"],
                    check_code=item["check"],
                    family=item["family"],
                    method=CheckMethod(item["method"]),
                    expected_violation=item["expected_violation"],
                    status=ResultStatus(item["status"]),
                )
                for item in data["observations"]
            ),
        )

    def save(self, report: QualityReport) -> None:
        data = {
            "format": FORMAT_VERSION,
            "measured_at": report.measured_at.isoformat(timespec="seconds"),
            "catalog_revision": report.catalog_revision,
            "model": report.model,
            "documents": [_timing(item) for item in report.documents],
            "observations": [_observation(item) for item in report.observations],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def _slug(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-") or "model"


class JsonModelTrialStore:
    """One JSON file per candidate model, beside the main measurement."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def all(self) -> list[QualityReport]:
        if not self._directory.is_dir():
            return []
        reports = [
            JsonQualityReportStore(path).load() for path in sorted(self._directory.glob("*.json"))
        ]
        return [report for report in reports if report is not None]

    def save(self, report: QualityReport) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        # One file per model and size of the measured set: a part of the set
        # does not replace a trial on all of it.
        name = f"{_slug(report.model or 'none')}--{len(report.documents)}"
        JsonQualityReportStore(self._directory / f"{name}.json").save(report)
