from __future__ import annotations

import re
import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from footnote.domain.documents.structure import (
    Alignment,
    Block,
    BlockKind,
    FontUsage,
    ParagraphFormat,
)
from footnote.infrastructure.parsing.pdf.lines import PageContent, PlacedTable, TextLine
from footnote.infrastructure.parsing.text_patterns import looks_like_heading, split_manual_label
from footnote.infrastructure.parsing.units import points_to_mm

# Geometry tolerances, in points unless stated otherwise.
EDGE_TOLERANCE = 4.0
INDENT_MIN = 8.0
CENTER_TOLERANCE = 8.0
RIGHT_ALIGNED_MIN_OFFSET = 90.0
SHORT_LINE_RATIO = 0.75  # a line shorter than this share of the text width ends a paragraph
SENTENCE_END_GAP_RATIO = 0.08
PARAGRAPH_GAP_RATIO = 1.45  # line pitch above this multiple of the usual pitch starts a paragraph
HEADING_SIZE_DELTA = 1.0
MAGNITUDE_CHANGE = 1.5
FURNITURE_ZONE = 0.07  # top and bottom share of the page holding running headers/footers
MAX_HEADING_LEVEL = 3

_PAGE_NUMBER = re.compile(
    r"^[-–—\s]*(?:стр\.?|страница)?\s*\d{1,4}(?:\s*(?:из|/)\s*\d{1,4})?[-–—\s]*$", re.IGNORECASE
)
_SENTENCE_END = (".", "!", "?", ":", ";")


@dataclass(frozen=True, slots=True)
class BodyGeometry:
    left: float
    right: float
    magnitude: float
    pitch: float

    @property
    def width(self) -> float:
        return max(self.right - self.left, 1.0)


def magnitude(line: TextLine) -> float:
    """Font size when known; for recognised text the line height stands in."""
    return line.size_pt or line.height


def _sized(line: TextLine) -> bool:
    """Font sizes are reliable; recognised line heights vary with the glyphs."""
    return line.size_pt is not None


def measure_body(pages: Sequence[PageContent]) -> BodyGeometry:
    lines = [line for page in pages for line in page.lines]
    if not lines:
        return BodyGeometry(left=0.0, right=0.0, magnitude=0.0, pitch=0.0)
    left_edges = Counter(round(line.x0 / 2) * 2 for line in lines)
    left = float(left_edges.most_common(1)[0][0])
    rights = sorted(line.x1 for line in lines)
    right = rights[int(len(rights) * 0.9) - 1 if len(rights) > 1 else 0]
    sized = [line for line in lines if _sized(line)] or lines
    weighted = [magnitude(line) for line in sized for _ in range(max(1, len(line.text) // 20))]
    body = statistics.median(weighted)
    pitches = [
        current.top - previous.top
        for page in pages
        for previous, current in zip(page.lines, page.lines[1:], strict=False)
        if 0 < current.top - previous.top < body * 3
    ]
    pitch = statistics.median(pitches) if pitches else body * 1.2
    return BodyGeometry(left=left, right=right, magnitude=body, pitch=pitch)


def strip_furniture(pages: Sequence[PageContent]) -> list[PageContent]:
    """Drops page numbers and running headers/footers repeated across pages."""

    def in_zone(line: TextLine, page: PageContent) -> bool:
        return line.top < page.height * FURNITURE_ZONE or line.bottom > page.height * (
            1 - FURNITURE_ZONE
        )

    def signature(text: str) -> str:
        return re.sub(r"\d+", "#", text.casefold())

    repeated = Counter(
        signature(line.text) for page in pages for line in page.lines if in_zone(line, page)
    )
    threshold = max(2, len(pages) // 2)
    cleaned: list[PageContent] = []
    for page in pages:
        kept = tuple(
            line
            for line in page.lines
            if not (
                in_zone(line, page)
                and (_PAGE_NUMBER.match(line.text) or repeated[signature(line.text)] >= threshold)
            )
        )
        cleaned.append(
            PageContent(
                number=page.number,
                width=page.width,
                height=page.height,
                lines=kept,
                tables=page.tables,
            )
        )
    return cleaned


def _center(line: TextLine) -> float:
    return (line.x0 + line.x1) / 2


def _leaves_set_off_block(previous: TextLine, line: TextLine, geometry: BodyGeometry) -> bool:
    """A block set off to the right (an approval stamp) ends where a line starts
    elsewhere and is not centred with it: the title below a stamp is a block
    of its own even when no extra space separates them."""
    set_off = previous.x0 > geometry.left + RIGHT_ALIGNED_MIN_OFFSET
    moved = abs(line.x0 - previous.x0) > INDENT_MIN
    return set_off and moved and abs(_center(line) - _center(previous)) > CENTER_TOLERANCE


def _starts_paragraph(previous: TextLine, line: TextLine, geometry: BodyGeometry) -> bool:
    gap = line.top - previous.top > geometry.pitch * PARAGRAPH_GAP_RATIO
    if gap or _leaves_set_off_block(previous, line, geometry):
        return True
    if _sized(line) and _sized(previous):
        if abs(magnitude(line) - magnitude(previous)) > MAGNITUDE_CHANGE:
            return True
        if line.bold != previous.bold:
            return True
    ends_sentence = previous.text.endswith(_SENTENCE_END)
    if split_manual_label(line.text) is not None and ends_sentence:
        return True
    # Inside a paragraph every line but the last runs to the right edge, so a
    # short line closes its paragraph unless the sentence visibly continues.
    short_previous = previous.x1 < geometry.left + geometry.width * SHORT_LINE_RATIO
    continues = line.text[:1].islower() and not ends_sentence
    if short_previous and not continues:
        return True
    # A finished sentence on a line that stops short of the right edge ends the
    # paragraph; in justified text only the last line falls short.
    stops_short = previous.x1 < geometry.right - geometry.width * SENTENCE_END_GAP_RATIO
    indented = line.x0 > geometry.left + INDENT_MIN
    return ends_sentence and (indented or stops_short)


def _join(lines: Sequence[TextLine]) -> str:
    text = lines[0].text
    for line in lines[1:]:
        if text.endswith("-") and len(text) > 1 and text[-2].isalpha() and line.text[:1].islower():
            text = text[:-1] + line.text
        else:
            text = f"{text} {line.text}"
    return text


def _alignment(lines: Sequence[TextLine], geometry: BodyGeometry) -> Alignment:
    first = lines[0]
    if len(lines) == 1:
        left_gap = first.x0 - geometry.left
        right_gap = geometry.right - first.x1
        if left_gap > INDENT_MIN * 2 and abs(left_gap - right_gap) < CENTER_TOLERANCE:
            return Alignment.CENTER
        if right_gap < EDGE_TOLERANCE and left_gap > RIGHT_ALIGNED_MIN_OFFSET:
            return Alignment.RIGHT
        return Alignment.LEFT
    body_lines = lines[:-1]
    if all(abs(line.x1 - geometry.right) < EDGE_TOLERANCE for line in body_lines):
        return Alignment.JUSTIFY
    centers = [((line.x0 + line.x1) / 2) for line in lines]
    middle = (geometry.left + geometry.right) / 2
    if all(abs(center - middle) < CENTER_TOLERANCE for center in centers):
        return Alignment.CENTER
    return Alignment.LEFT


def _fonts(lines: Sequence[TextLine]) -> tuple[FontUsage, ...]:
    usage: Counter[tuple[str | None, float | None, bool, bool]] = Counter()
    for line in lines:
        for font in line.fonts:
            usage[(font.family, font.size_pt, font.bold, font.italic)] += font.chars
    return tuple(
        FontUsage(family=family, size_pt=size, bold=bold, italic=italic, chars=chars)
        for (family, size, bold, italic), chars in usage.most_common()
    )


@dataclass(frozen=True, slots=True)
class _Paragraph:
    page: int
    lines: tuple[TextLine, ...]


class ParagraphBuilder:
    """Turns positioned lines into blocks: paragraphs, list items, headings, tables."""

    def __init__(self, pages: Sequence[PageContent]) -> None:
        self._pages = strip_furniture(pages)
        self._geometry = measure_body(self._pages)
        heading_sizes = sorted(
            {
                round(magnitude(line) * 2) / 2
                for page in self._pages
                for line in page.lines
                if _sized(line) and magnitude(line) > self._geometry.magnitude + HEADING_SIZE_DELTA
            },
            reverse=True,
        )
        self._heading_rank = {size: rank for rank, size in enumerate(heading_sizes)}

    def build(self) -> list[Block]:
        items: list[_Paragraph | tuple[int, PlacedTable]] = []
        for page in self._pages:
            items.extend(self._page_items(page))
        merged = self._merge_across_pages(items)
        blocks: list[Block] = []
        for item in merged:
            ordinal = len(blocks)
            if isinstance(item, _Paragraph):
                blocks.append(self._paragraph_block(item, ordinal))
            else:
                page_number, table = item
                blocks.append(
                    Block(
                        ordinal=ordinal,
                        kind=BlockKind.TABLE,
                        text="\n".join(
                            "\t".join(cell.text.replace("\n", " ") for cell in row)
                            for row in table.content.rows
                        ),
                        page=page_number,
                        table=table.content,
                    )
                )
        return blocks

    def _page_items(self, page: PageContent) -> list[_Paragraph | tuple[int, PlacedTable]]:
        events: list[tuple[float, TextLine | PlacedTable]] = [
            (line.top, line) for line in page.lines
        ]
        events.extend((table.top, table) for table in page.tables)
        events.sort(key=lambda event: event[0])
        items: list[_Paragraph | tuple[int, PlacedTable]] = []
        current: list[TextLine] = []
        for _, element in events:
            if isinstance(element, PlacedTable):
                if current:
                    items.append(_Paragraph(page=page.number, lines=tuple(current)))
                    current = []
                items.append((page.number, element))
                continue
            if current and _starts_paragraph(current[-1], element, self._geometry):
                items.append(_Paragraph(page=page.number, lines=tuple(current)))
                current = []
            current.append(element)
        if current:
            items.append(_Paragraph(page=page.number, lines=tuple(current)))
        return items

    @staticmethod
    def _merge_across_pages(
        items: list[_Paragraph | tuple[int, PlacedTable]],
    ) -> list[_Paragraph | tuple[int, PlacedTable]]:
        merged: list[_Paragraph | tuple[int, PlacedTable]] = []
        for item in items:
            previous = merged[-1] if merged else None
            if (
                isinstance(item, _Paragraph)
                and isinstance(previous, _Paragraph)
                and item.page == previous.page + 1
                and not previous.lines[-1].text.endswith(_SENTENCE_END)
                and item.lines[0].text[:1].islower()
            ):
                merged[-1] = _Paragraph(page=previous.page, lines=previous.lines + item.lines)
                continue
            merged.append(item)
        return merged

    def _paragraph_block(self, paragraph: _Paragraph, ordinal: int) -> Block:
        lines = paragraph.lines
        geometry = self._geometry
        text = _join(lines)
        fonts = _fonts(lines)
        confidences = [line.confidence for line in lines if line.confidence is not None]

        kind = BlockKind.PARAGRAPH
        label: str | None = None
        level: int | None = None
        numbered_top = False
        manual = split_manual_label(text)
        if manual is not None:
            label, text, level = manual.label, manual.text, manual.depth
            kind = BlockKind.LIST_ITEM
            numbered_top = manual.depth == 0 and not manual.is_bullet

        sizes = [magnitude(line) for line in lines if _sized(line)]
        size = round(statistics.median(sizes) * 2) / 2 if sizes else None
        if size is not None and size in self._heading_rank and len(text) < 200:
            kind = BlockKind.HEADING
            level = min(self._heading_rank[size] + 1, MAX_HEADING_LEVEL)
        elif len(lines) <= 2 and looks_like_heading(
            text.replace("\n", " "),
            emphasized=all(line.bold for line in lines),
            numbered_top=numbered_top,
        ):
            kind = BlockKind.HEADING
            level = min(
                len(self._heading_rank) + (1 if label is None or numbered_top else 2),
                MAX_HEADING_LEVEL,
            )

        rest_left = min((line.x0 for line in lines[1:]), default=geometry.left)
        return Block(
            ordinal=ordinal,
            kind=kind,
            text=text,
            level=level,
            label=label,
            page=paragraph.page,
            fonts=fonts,
            paragraph=ParagraphFormat(
                alignment=_alignment(lines, geometry),
                first_line_indent_mm=points_to_mm(lines[0].x0 - rest_left),
                left_indent_mm=points_to_mm(max(rest_left - geometry.left, 0.0)),
            ),
            confidence=round(statistics.fmean(confidences), 3) if confidences else None,
        )
