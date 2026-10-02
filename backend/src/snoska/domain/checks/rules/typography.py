from __future__ import annotations

from collections import Counter

from snoska.domain.checks.catalog import CatalogError
from snoska.domain.checks.outcome import CheckOutcome, Detail
from snoska.domain.checks.rules.base import Offence, RuleParams, body_blocks, offences_outcome
from snoska.domain.documents.structure import Block, BlockKind, DocumentStructure

# Below this share of body blocks with known values a document says too
# little about itself (a scan, a PDF without metrics) for a verdict.
MIN_KNOWN_SHARE = 0.5


def dominant_size(block: Block) -> float | None:
    """The font size most of the block's characters are set in."""
    sizes: Counter[float] = Counter()
    for font in block.fonts:
        if font.size_pt is not None and font.chars > 0:
            sizes[round(font.size_pt * 2) / 2] += font.chars
    return sizes.most_common(1)[0][0] if sizes else None


def _enough_known(known: int, total: int) -> bool:
    return total > 0 and known / total >= MIN_KNOWN_SHARE


def _most_common(values: list[float]) -> float:
    """The offending value seen most often, named in the document-wide finding."""
    return Counter(values).most_common(1)[0][0] if values else 0.0


class BodyFontSizeRule:
    """Running text is set in sizes within a range (tables may be smaller)."""

    id = "body_font_size"

    def validate(self, params: RuleParams) -> None:
        if params.number("min_pt") > params.number("max_pt"):
            raise CatalogError("min_pt is above max_pt")

    def evaluate(self, structure: DocumentStructure, params: RuleParams) -> CheckOutcome:
        low, high = params.number("min_pt"), params.number("max_pt")
        body = body_blocks(structure)
        sized = [(block, dominant_size(block)) for block in body]
        known = [(block, size) for block, size in sized if size is not None]
        if not _enough_known(len(known), len(body)):
            return CheckOutcome.not_applicable()
        offending = [(block, size) for block, size in known if not low <= size <= high]
        offences = [
            Offence(block, Detail.message("font_size", size=size)) for block, size in offending
        ]
        common = _most_common([size for _, size in offending])
        return offences_outcome(offences, Detail.message("font_size_widespread", size=common))


class LineSpacingRule:
    """Running text is set with line spacing within a range of multiples."""

    id = "line_spacing"

    def validate(self, params: RuleParams) -> None:
        if params.number("min") > params.number("max"):
            raise CatalogError("min is above max")

    def evaluate(self, structure: DocumentStructure, params: RuleParams) -> CheckOutcome:
        low, high = params.number("min"), params.number("max")
        body = body_blocks(structure)
        known = [
            (block, block.paragraph.line_spacing)
            for block in body
            if block.paragraph is not None and block.paragraph.line_spacing is not None
        ]
        if not _enough_known(len(known), len(body)):
            return CheckOutcome.not_applicable()
        offending = [(block, value) for block, value in known if not low <= value <= high]
        offences = [
            Offence(block, Detail.message("line_spacing", value=value))
            for block, value in offending
        ]
        common = _most_common([value for _, value in offending])
        return offences_outcome(offences, Detail.message("line_spacing_widespread", value=common))


class ParagraphIndentRule:
    """Paragraphs of running text start with a first-line indent of a set width.

    List items are left out: their hanging indent belongs to the numbering.
    """

    id = "paragraph_indent"

    def validate(self, params: RuleParams) -> None:
        if params.number("tolerance_mm") < 0:
            raise CatalogError("tolerance_mm is negative")
        params.number("indent_mm")

    def evaluate(self, structure: DocumentStructure, params: RuleParams) -> CheckOutcome:
        target, tolerance = params.number("indent_mm"), params.number("tolerance_mm")
        paragraphs = [
            block for block in body_blocks(structure) if block.kind is BlockKind.PARAGRAPH
        ]
        known = [
            (block, block.paragraph.first_line_indent_mm or 0.0)
            for block in paragraphs
            if block.paragraph is not None
        ]
        if not _enough_known(len(known), len(paragraphs)):
            return CheckOutcome.not_applicable()
        offending = [(block, indent) for block, indent in known if abs(indent - target) > tolerance]
        offences = [
            Offence(block, Detail.message("paragraph_indent", cm=_centimetres(indent)))
            for block, indent in offending
        ]
        common = _most_common([_centimetres(indent) for _, indent in offending])
        return offences_outcome(offences, Detail.message("paragraph_indent_widespread", cm=common))


def _centimetres(millimetres: float) -> float:
    return round(millimetres / 10, 2)
