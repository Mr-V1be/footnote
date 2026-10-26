from __future__ import annotations

from typing import Any

from pdfplumber.page import Page

from footnote.domain.documents.structure import TableCell, TableContent
from footnote.domain.shared.text import normalize_whitespace
from footnote.infrastructure.parsing.pdf.lines import (
    PageContent,
    PlacedTable,
    TextLine,
    dominant_size,
    fonts_of,
)
from footnote.infrastructure.parsing.text_patterns import normalize_symbols

# A page whose text layer has fewer visible characters is treated as a scan.
MIN_TEXT_CHARS = 25


def visible_char_count(page: Page) -> int:
    return sum(1 for char in page.chars if str(char.get("text", "")).strip())


def _table_content(rows: list[list[str | None]]) -> TableContent:
    """pdfplumber reports cells covered by a horizontal span as None."""
    built: list[tuple[TableCell, ...]] = []
    for row in rows:
        cells: list[TableCell] = []
        for value in row:
            if value is None and cells:
                last = cells[-1]
                cells[-1] = TableCell(text=last.text, col_span=last.col_span + 1, row_span=1)
                continue
            text = "\n".join(
                line
                for line in (normalize_whitespace(part) for part in (value or "").split("\n"))
                if line
            )
            cells.append(TableCell(text=text))
        if any(cell.text for cell in cells):
            built.append(tuple(cells))
    return TableContent(rows=tuple(built))


def read_text_page(page: Page, number: int) -> PageContent:
    tables: list[PlacedTable] = []
    remaining = page
    for found in page.find_tables():
        content = _table_content(found.extract())
        x0, top, x1, bottom = found.bbox
        remaining = remaining.outside_bbox((x0, top, x1, bottom))
        if content.rows:
            tables.append(PlacedTable(top=float(top), bottom=float(bottom), content=content))

    lines: list[TextLine] = []
    raw_lines: list[dict[str, Any]] = remaining.extract_text_lines(return_chars=True, strip=True)
    for raw in raw_lines:
        text = normalize_symbols(normalize_whitespace(str(raw.get("text", ""))))
        if not text:
            continue
        fonts = fonts_of(raw.get("chars", ()))
        lines.append(
            TextLine(
                text=text,
                x0=float(raw["x0"]),
                x1=float(raw["x1"]),
                top=float(raw["top"]),
                bottom=float(raw["bottom"]),
                size_pt=dominant_size(fonts),
                fonts=fonts,
            )
        )
    lines.sort(key=lambda line: (round(line.top, 1), line.x0))
    return PageContent(
        number=number,
        width=float(page.width),
        height=float(page.height),
        lines=tuple(lines),
        tables=tuple(sorted(tables, key=lambda table: table.top)),
    )
