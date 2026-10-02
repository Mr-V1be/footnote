from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from snoska.domain.shared.errors import NotFoundError


class CatalogError(ValueError):
    """The check catalogue is inconsistent; raised while loading, before any run."""


class UnknownCheckError(NotFoundError):
    code = "unknown_check"


class CheckMethod(StrEnum):
    """How a check reaches its verdict."""

    # Rules over the parsed structure: fonts, geometry, requisites, numbering.
    DETERMINISTIC = "deterministic"
    # A language model reading document passages next to the norm it applies.
    MODEL = "model"


class Severity(StrEnum):
    CRITICAL = "critical"
    IMPORTANT = "important"
    ADVICE = "advice"

    @property
    def rank(self) -> int:
        """Sort key: the most serious first."""
        return _SEVERITY_RANK[self]


_SEVERITY_RANK = {Severity.CRITICAL: 0, Severity.IMPORTANT: 1, Severity.ADVICE: 2}


@dataclass(frozen=True, slots=True)
class LawNorm:
    """Provisions of an act in the corpus. Their text is quoted from the corpus
    edition in force, so a citation is never written by hand or by a model."""

    act_code: str
    anchors: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.anchors:
            raise CatalogError(f"{self.act_code}: a law norm needs at least one anchor")

    @property
    def primary(self) -> str:
        return self.anchors[0]


@dataclass(frozen=True, slots=True)
class StandardNorm:
    """A clause of a standard. The standard's text is not redistributed: the
    check states the rule in its own words and refers to the clause."""

    standard: str
    clause: str

    @property
    def citation(self) -> str:
        return f"п. {self.clause} {self.standard}"


Norm = LawNorm | StandardNorm


@dataclass(frozen=True, slots=True)
class ModelBrief:
    """What the language model is asked about one requirement.

    ``search`` describes the passage the requirement is about; it drives
    retrieval over the document. ``keywords`` are stems that make a passage
    more likely to be relevant regardless of wording.
    """

    question: str
    criteria: str
    search: str
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CheckDefinition:
    """One entry of the check registry.

    A check is described entirely by data: the document kinds it applies to,
    the norm, the default severity and how it is evaluated — a deterministic
    rule with parameters or a brief for the language model. Adding a check is
    adding an entry; the engine does not change.
    """

    code: str
    family: str
    method: CheckMethod
    kinds: frozenset[str]
    norm: Norm
    severity: Severity
    title: str
    requirement: str
    recommendation: str
    rule: str | None = None
    params: Mapping[str, object] = field(default_factory=dict)
    brief: ModelBrief | None = None

    def __post_init__(self) -> None:
        if not self.kinds:
            raise CatalogError(f"{self.code}: applies to no document kind")
        if self.method is CheckMethod.DETERMINISTIC:
            if not self.rule:
                raise CatalogError(f"{self.code}: a deterministic check names its rule")
            # A finding on a law quotes the provision the verdict rests on;
            # rules state requirements of standards in their own words.
            if not isinstance(self.norm, StandardNorm):
                raise CatalogError(f"{self.code}: a deterministic check refers to a standard")
        if self.method is CheckMethod.MODEL:
            if self.brief is None:
                raise CatalogError(f"{self.code}: a model check needs a brief")
            if not isinstance(self.norm, LawNorm):
                raise CatalogError(f"{self.code}: a model check is grounded in a law in the corpus")

    def applies_to(self, kind: str) -> bool:
        return kind in self.kinds


@dataclass(frozen=True, slots=True)
class CheckFamily:
    """A group of checks shown and measured together (e.g. formatting, 152-FZ)."""

    code: str
    rank: int


class CheckCatalog:
    """The registry of checks at one revision.

    ``revision`` identifies the catalogue content; every run records it, so a
    result can always be traced to the exact rules that produced it.
    """

    def __init__(
        self,
        families: Iterable[CheckFamily],
        checks: Iterable[CheckDefinition],
        revision: str,
    ) -> None:
        self.revision = revision
        self._families = {family.code: family for family in families}
        self._checks: dict[str, CheckDefinition] = {}
        for check in checks:
            if check.code in self._checks:
                raise CatalogError(f"duplicate check code {check.code!r}")
            if check.family not in self._families:
                raise CatalogError(f"{check.code}: unknown family {check.family!r}")
            self._checks[check.code] = check

    def get(self, code: str) -> CheckDefinition:
        try:
            return self._checks[code]
        except KeyError as exc:
            raise UnknownCheckError(f"unknown check {code!r}") from exc

    def families(self) -> tuple[CheckFamily, ...]:
        return tuple(sorted(self._families.values(), key=lambda family: family.rank))

    def all(self) -> tuple[CheckDefinition, ...]:
        return tuple(self._checks.values())

    def applicable(self, kind: str) -> tuple[CheckDefinition, ...]:
        """Checks for a document kind, in catalogue order (rules before models)."""
        return tuple(
            sorted(
                (check for check in self._checks.values() if check.applies_to(kind)),
                key=lambda check: check.method is CheckMethod.MODEL,
            )
        )
