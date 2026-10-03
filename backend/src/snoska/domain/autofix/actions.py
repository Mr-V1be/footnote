from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# What a correction does, as data a file adapter carries out. Every action
# names the check it answers, so the journal can say why it was made.


@dataclass(frozen=True, slots=True)
class SetMargins:
    """Raise page margins to at least these widths (millimetres)."""

    check_code: str
    left_mm: float
    right_mm: float
    top_mm: float
    bottom_mm: float


@dataclass(frozen=True, slots=True)
class SetFontSize:
    """Set the running text of these blocks to a size within the range."""

    check_code: str
    block_ordinals: tuple[int, ...]
    min_pt: float
    max_pt: float


@dataclass(frozen=True, slots=True)
class SetLineSpacing:
    check_code: str
    block_ordinals: tuple[int, ...]
    min_multiple: float
    max_multiple: float


@dataclass(frozen=True, slots=True)
class SetFirstLineIndent:
    check_code: str
    block_ordinals: tuple[int, ...]
    indent_mm: float


@dataclass(frozen=True, slots=True)
class ReplaceText:
    """Replace words of one block: a date's spelling, a signature's order,
    a section number. ``before`` is looked up in the block as it is."""

    check_code: str
    block_ordinal: int
    before: str
    after: str


FixAction = SetMargins | SetFontSize | SetLineSpacing | SetFirstLineIndent | ReplaceText


class SkipReason(StrEnum):
    # Writing it needs a person: an approval stamp, a number, a title.
    NEEDS_PERSON = "needs_person"
    # Not an oversight of formatting but of content: a lawyer's matter.
    LEGAL = "legal"
    # The file type cannot be edited (a PDF, a scan).
    NOT_EDITABLE = "not_editable"
    # The correction would change the structure (renumbering, nesting).
    UNSAFE = "unsafe"


@dataclass(frozen=True, slots=True)
class Skipped:
    check_code: str
    finding_id: str
    reason: SkipReason


@dataclass(frozen=True, slots=True)
class FixPlan:
    actions: tuple[FixAction, ...]
    skipped: tuple[Skipped, ...]

    @property
    def empty(self) -> bool:
        return not self.actions


class ChangeKind(StrEnum):
    """What a journal line measures, so its values can be read with units."""

    MARGINS = "margins"  # "left=20;right=10", millimetres per side
    FONT_SIZE = "font_size"  # points
    LINE_SPACING = "line_spacing"  # multiples of a line
    FIRST_LINE_INDENT = "first_line_indent"  # centimetres
    TEXT = "text"  # the words before and after
    # A formatting change journaled before measures were told apart.
    FORMAT = "format"


@dataclass(frozen=True, slots=True)
class AppliedChange:
    """One line of a correction's journal: what was there and what is now.

    ``block_ordinal`` refers to the source version; ``places`` counts the
    blocks a formatting change touched.
    """

    check_code: str
    kind: ChangeKind
    block_ordinal: int | None
    before: str
    after: str
    places: int = 1
