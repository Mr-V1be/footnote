from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from footnote.domain.shared.errors import InvalidStateError
from footnote.domain.shared.locale import LocalizedText


class ActKind(StrEnum):
    FEDERAL_LAW = "federal_law"
    GOVERNMENT_DECREE = "government_decree"
    STANDARD = "standard"


@dataclass(frozen=True, slots=True)
class LegalAct:
    """A normative act tracked by the corpus, named as each interface
    language names it ("152-ФЗ", "152-FZ"); the source wording is the act's
    own, the one the corpus cites it by."""

    code: str
    kind: ActKind
    short_title: LocalizedText
    title: LocalizedText
    adopted_on: date


class EditionStatus(StrEnum):
    INGESTED = "ingested"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


@dataclass(slots=True)
class Edition:
    """One redaction of an act as published by its source.

    An edition becomes ACTIVE only once every unit is embedded, so search
    never serves a redaction with missing vectors.
    """

    id: UUID
    act_code: str
    source_code: str
    source_revision: str
    amended_by: str | None
    content_sha256: str
    retrieved_at: datetime
    status: EditionStatus
    activated_at: datetime | None

    def activate(self, now: datetime) -> None:
        if self.status is not EditionStatus.INGESTED:
            raise InvalidStateError(f"cannot activate an edition in status {self.status}")
        self.status = EditionStatus.ACTIVE
        self.activated_at = now

    def supersede(self) -> None:
        if self.status is not EditionStatus.ACTIVE:
            raise InvalidStateError(f"cannot supersede an edition in status {self.status}")
        self.status = EditionStatus.SUPERSEDED
