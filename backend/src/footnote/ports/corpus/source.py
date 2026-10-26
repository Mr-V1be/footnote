from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from footnote.domain.corpus.acts import LegalAct
from footnote.domain.corpus.units import ParsedUnit


class CorpusSourceError(Exception):
    """The source could not be reached or returned an unusable document."""


@dataclass(frozen=True, slots=True)
class FetchedEdition:
    source_code: str
    source_revision: str
    amended_by: str | None
    retrieved_at: datetime
    units: tuple[ParsedUnit, ...]


class CorpusSource(Protocol):
    code: str

    async def fetch_current(self, act: LegalAct) -> FetchedEdition: ...


@dataclass(frozen=True, slots=True)
class TrackedAct:
    """An act and the source-specific references needed to fetch it."""

    act: LegalAct
    source_refs: Mapping[str, str]


class ActCatalog(Protocol):
    def get(self, act_code: str) -> TrackedAct: ...

    def all(self) -> tuple[TrackedAct, ...]: ...
