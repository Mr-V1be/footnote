from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class ResultStatus(StrEnum):
    """The verdict of one check on one document version."""

    PASSED = "passed"
    VIOLATION = "violation"
    # The check could not reach a grounded verdict: a lawyer has to look.
    NEEDS_REVIEW = "needs_review"
    # The document lacks what the check needs (e.g. no font data in a scan).
    NOT_APPLICABLE = "not_applicable"
    # The check failed to run (provider down, no valid answer after retries).
    ERROR = "error"


class FindingKind(StrEnum):
    VIOLATION = "violation"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class TextLocation:
    """A span [start, end) of a block's text. The quoted words are derived
    from the stored structure, which never changes for a version."""

    block_ordinal: int
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError(f"empty or negative span {self.start}..{self.end}")


DetailValue = str | int | float


@dataclass(frozen=True, slots=True)
class Detail:
    """What exactly is wrong.

    A rule states it as a message ``code`` with ``params``; the interface
    renders it through its translations. A language model states it in its
    own words (``text``), which are shown as they are.
    """

    code: str | None = None
    params: Mapping[str, DetailValue] = field(default_factory=dict)
    text: str | None = None

    def __post_init__(self) -> None:
        if (self.code is None) == (self.text is None):
            raise ValueError("a detail is either a message code or a text")

    @classmethod
    def message(cls, code: str, **params: DetailValue) -> Detail:
        return cls(code=code, params=params)

    @classmethod
    def written(cls, text: str) -> Detail:
        return cls(text=text)


@dataclass(frozen=True, slots=True)
class FindingDraft:
    """A finding as a check produces it, before it is stored.

    ``location`` is None when the finding concerns the document as a whole,
    for example a required element that is not there at all. Such a finding
    may still list the ``places`` it covers (a font size broken in most
    paragraphs): they are not marked in the text, only shown on request.
    """

    kind: FindingKind
    detail: Detail
    location: TextLocation | None = None
    recommendation: str | None = None
    places: tuple[TextLocation, ...] = ()

    def __post_init__(self) -> None:
        if self.places and self.location is not None:
            raise ValueError("a finding on one place does not list other places")


@dataclass(frozen=True, slots=True)
class CitedProvision:
    """The provision of the corpus a model check based its verdict on."""

    act_code: str
    edition_id: UUID
    anchor: str
    citation: str


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    """What one check concluded.

    ``evidence`` are the passages a passed check relied on, shown to the
    reader as "where we found it". ``cited`` is the provision a model check
    actually cited, among those it was given.
    """

    status: ResultStatus
    findings: tuple[FindingDraft, ...] = ()
    evidence: tuple[TextLocation, ...] = ()
    cited: CitedProvision | None = None
    error_code: str | None = None
    attempts: int = 1

    @classmethod
    def passed(cls, evidence: tuple[TextLocation, ...] = ()) -> CheckOutcome:
        return cls(ResultStatus.PASSED, evidence=evidence)

    @classmethod
    def not_applicable(cls) -> CheckOutcome:
        return cls(ResultStatus.NOT_APPLICABLE)

    @classmethod
    def violation(cls, *findings: FindingDraft) -> CheckOutcome:
        if not findings:
            raise ValueError("a violation carries at least one finding")
        return cls(ResultStatus.VIOLATION, findings=findings)

    @classmethod
    def failed(cls, error_code: str, attempts: int = 1) -> CheckOutcome:
        return cls(ResultStatus.ERROR, error_code=error_code, attempts=attempts)
