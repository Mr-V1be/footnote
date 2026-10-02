from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from snoska.domain.checks.quality import QualityReport


class ReferenceSetError(Exception):
    """The reference set or its labels cannot be used as they are."""


@dataclass(frozen=True, slots=True)
class ReferenceDocument:
    """A document written for measurement, with the violations an expert finds in it."""

    file_name: str
    title: str
    kind: str
    format_code: str
    pages: int
    expected: frozenset[str]
    typical: bool = False


class ReferenceSet(Protocol):
    def documents(self) -> Sequence[ReferenceDocument]: ...

    async def content(self, document: ReferenceDocument) -> bytes: ...


class QualityReportStore(Protocol):
    """Where the latest benchmark result is kept for the product to show."""

    def load(self) -> QualityReport | None: ...

    def save(self, report: QualityReport) -> None: ...
