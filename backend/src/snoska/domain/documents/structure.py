from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class BlockKind(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"


class Alignment(StrEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class LayoutSource(StrEnum):
    """Where page geometry came from: declared by the file or measured from ink."""

    DECLARED = "declared"
    MEASURED = "measured"


@dataclass(frozen=True, slots=True)
class FontUsage:
    """A distinct font run inside a block and how many characters use it."""

    family: str | None
    size_pt: float | None
    bold: bool
    italic: bool
    chars: int


@dataclass(frozen=True, slots=True)
class ParagraphFormat:
    alignment: Alignment | None = None
    first_line_indent_mm: float | None = None
    left_indent_mm: float | None = None
    line_spacing: float | None = None
    space_before_pt: float | None = None
    space_after_pt: float | None = None


@dataclass(frozen=True, slots=True)
class TableCell:
    text: str
    col_span: int = 1
    row_span: int = 1


@dataclass(frozen=True, slots=True)
class TableContent:
    rows: tuple[tuple[TableCell, ...], ...]

    @property
    def column_count(self) -> int:
        return max((sum(cell.col_span for cell in row) for row in self.rows), default=0)


@dataclass(frozen=True, slots=True)
class Block:
    """A unit of document content in reading order.

    ``level`` is the heading level (1 is the top) or the list nesting depth
    (0 is the outermost). ``label`` is the numbering exactly as a reader sees
    it, e.g. ``1.2.`` or ``а)``. ``confidence`` is set for recognised text.
    """

    ordinal: int
    kind: BlockKind
    text: str
    level: int | None = None
    label: str | None = None
    page: int | None = None
    fonts: tuple[FontUsage, ...] = ()
    paragraph: ParagraphFormat | None = None
    table: TableContent | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class PageSetup:
    """Page geometry of a section (DOCX) or a page (PDF), in millimetres."""

    source: LayoutSource
    width_mm: float
    height_mm: float
    margin_top_mm: float | None
    margin_bottom_mm: float | None
    margin_left_mm: float | None
    margin_right_mm: float | None
    first_page: int | None = None


@dataclass(frozen=True, slots=True)
class DocumentLayout:
    pages: tuple[PageSetup, ...] = ()


class RequisiteKind(StrEnum):
    """Document requisites recognised in the text (GOST R 7.0.97-2016, sec. 5)."""

    ORGANIZATION_NAME = "organization_name"
    DOCUMENT_TYPE = "document_type"
    DATE = "date"
    REGISTRATION_NUMBER = "registration_number"
    PLACE = "place"
    ACCESS_RESTRICTION = "access_restriction"
    APPROVAL_STAMP = "approval_stamp"
    TITLE = "title"
    ATTACHMENT_NOTE = "attachment_note"
    SIGNATURE = "signature"
    EXECUTOR_NOTE = "executor_note"


@dataclass(frozen=True, slots=True)
class Requisite:
    kind: RequisiteKind
    block_ordinal: int
    start: int
    end: int
    value: str


@dataclass(frozen=True, slots=True)
class OutlineEntry:
    block_ordinal: int
    level: int
    label: str | None
    text: str


@dataclass(frozen=True, slots=True)
class DocumentStructure:
    blocks: tuple[Block, ...]
    requisites: tuple[Requisite, ...] = ()
    layout: DocumentLayout = field(default_factory=DocumentLayout)

    def outline(self) -> tuple[OutlineEntry, ...]:
        """Navigation tree derived from headings; never stored separately."""
        return tuple(
            OutlineEntry(
                block_ordinal=block.ordinal,
                level=block.level or 1,
                label=block.label,
                text=block.text,
            )
            for block in self.blocks
            if block.kind is BlockKind.HEADING
        )
