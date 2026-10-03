from __future__ import annotations

from collections.abc import Iterator

from lxml.etree import _Element

from snoska.domain.documents.structure import TableCell, TableContent
from snoska.domain.shared.text import normalize_whitespace
from snoska.infrastructure.parsing.docx.xml import attr, child, int_attr, w

_TEXT_TAGS = (w("t"), w("tab"), w("br"), w("cr"))


def run_text(run: _Element) -> str:
    parts: list[str] = []
    for node in run.iter(*_TEXT_TAGS):
        if node.tag == w("t"):
            parts.append(node.text or "")
        elif node.tag == w("tab"):
            parts.append(" ")
        else:
            parts.append("\n")
    return "".join(parts)


def clean_text(raw: str) -> str:
    """Collapse whitespace but keep manual line breaks inside a paragraph."""
    lines = (normalize_whitespace(line) for line in raw.split("\n"))
    return "\n".join(line for line in lines if line).strip()


def paragraph_runs(paragraph: _Element) -> Iterator[_Element]:
    """Runs in reading order, including those inside hyperlinks and fields."""
    yield from paragraph.iter(w("r"))


def paragraph_text(paragraph: _Element) -> str:
    return clean_text("".join(run_text(run) for run in paragraph_runs(paragraph)))


def body_elements(container: _Element) -> Iterator[_Element]:
    """Paragraphs and tables in order, unwrapping content controls."""
    for element in container.iterchildren():
        if element.tag in (w("p"), w("tbl")):
            yield element
        elif element.tag == w("sdt"):
            content = child(element, "sdtContent")
            if content is not None:
                yield from body_elements(content)


def block_elements(container: _Element) -> Iterator[_Element]:
    """The body elements that become blocks, in the order the blocks are
    numbered: paragraphs with text and tables with rows. The parser and the
    corrector both count blocks this way, so an ordinal finds its element."""
    for element in body_elements(container):
        if element.tag == w("tbl"):
            if read_table(element).rows:
                yield element
        elif paragraph_text(element):
            yield element


class _MutableCell:
    __slots__ = ("col_span", "row_span", "text")

    def __init__(self, text: str, col_span: int) -> None:
        self.text = text
        self.col_span = col_span
        self.row_span = 1


def read_table(table: _Element) -> TableContent:
    """Rows of cells with horizontal (gridSpan) and vertical (vMerge) spans."""
    rows: list[list[_MutableCell]] = []
    open_merges: dict[int, _MutableCell] = {}
    for tr in table.findall(w("tr")):
        cells: list[_MutableCell] = []
        column = 0
        for tc in tr.findall(w("tc")):
            properties = child(tc, "tcPr")
            span = int_attr(child(properties, "gridSpan"), "val") or 1
            merge = child(properties, "vMerge")
            merge_value = attr(merge, "val") if merge is not None else None
            if merge is not None and merge_value != "restart":
                origin = open_merges.get(column)
                if origin is not None:
                    origin.row_span += 1
                column += span
                continue
            text = "\n".join(text for p in tc.iter(w("p")) if (text := paragraph_text(p)))
            cell = _MutableCell(text, span)
            cells.append(cell)
            if merge_value == "restart":
                open_merges[column] = cell
            else:
                open_merges.pop(column, None)
            column += span
        rows.append(cells)
    return TableContent(
        rows=tuple(
            tuple(
                TableCell(text=cell.text, col_span=cell.col_span, row_span=cell.row_span)
                for cell in row
            )
            for row in rows
            if row
        )
    )


def table_text(content: TableContent) -> str:
    return "\n".join(
        "\t".join(cell.text.replace("\n", " ") for cell in row) for row in content.rows
    )
