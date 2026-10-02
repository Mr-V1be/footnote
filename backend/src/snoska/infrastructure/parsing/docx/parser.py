from __future__ import annotations

import io
import zipfile
from collections import Counter

import anyio.to_thread
import docx
from docx.document import Document as DocxDocument
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.parser import parse_xml
from lxml.etree import XMLSyntaxError, _Element

from snoska.domain.documents.structure import (
    Block,
    BlockKind,
    DocumentLayout,
    FontUsage,
    LayoutSource,
    PageSetup,
)
from snoska.domain.documents.version import ExtractionMethod, ParseFailureCode
from snoska.infrastructure.parsing.docx.content import (
    body_elements,
    clean_text,
    paragraph_runs,
    read_table,
    run_text,
    table_text,
)
from snoska.infrastructure.parsing.docx.numbering import NumberingResolver
from snoska.infrastructure.parsing.docx.styles import RunProps, StyleSheet
from snoska.infrastructure.parsing.docx.xml import w
from snoska.infrastructure.parsing.text_patterns import looks_like_heading, split_manual_label
from snoska.infrastructure.parsing.units import emu_to_mm
from snoska.ports.document_parsing import DocumentParseError, ParsedDocument

MAX_BLOCKS = 20_000


def _fonts(runs: list[tuple[str, RunProps]]) -> tuple[FontUsage, ...]:
    usage: Counter[RunProps] = Counter()
    for text, props in runs:
        visible = len(text.strip())
        if visible:
            usage[props] += visible
    return tuple(
        FontUsage(
            family=props.family,
            size_pt=props.size_pt,
            bold=props.bold,
            italic=props.italic,
            chars=chars,
        )
        for props, chars in usage.most_common()
    )


def _mm(length: int | None) -> float | None:
    return emu_to_mm(length) if length is not None else None


class DocxParser:
    format_code = "docx"

    async def parse(self, content: bytes) -> ParsedDocument:
        return await anyio.to_thread.run_sync(self._parse, content)

    def _parse(self, content: bytes) -> ParsedDocument:
        try:
            document = docx.Document(io.BytesIO(content))
        except (zipfile.BadZipFile, KeyError, ValueError, XMLSyntaxError) as exc:
            raise DocumentParseError(ParseFailureCode.CORRUPTED_FILE, str(exc)) from exc

        sheet = StyleSheet(document.styles.element, self._theme(document))
        numbering = NumberingResolver(self._numbering(document))
        blocks: list[Block] = []
        for element in body_elements(document.element.body):
            if len(blocks) >= MAX_BLOCKS:
                raise DocumentParseError(ParseFailureCode.TOO_LARGE, "document has too many blocks")
            block = (
                self._table(element, len(blocks))
                if element.tag == w("tbl")
                else self._paragraph(element, len(blocks), sheet, numbering)
            )
            if block is not None:
                blocks.append(block)

        layout = DocumentLayout(
            pages=tuple(
                PageSetup(
                    source=LayoutSource.DECLARED,
                    width_mm=_mm(section.page_width) or 0.0,
                    height_mm=_mm(section.page_height) or 0.0,
                    margin_top_mm=_mm(section.top_margin),
                    margin_bottom_mm=_mm(section.bottom_margin),
                    margin_left_mm=_mm(section.left_margin),
                    margin_right_mm=_mm(section.right_margin),
                )
                for section in document.sections
            )
        )
        return ParsedDocument(
            blocks=tuple(blocks),
            layout=layout,
            method=ExtractionMethod.DOCX,
            # Word stores a page count in docProps, but only as the authoring
            # tool last computed it; it is not reported as a fact.
            page_count=None,
            ocr_confidence=None,
        )

    @staticmethod
    def _theme(document: DocxDocument) -> _Element | None:
        try:
            part = document.part.part_related_by(RT.THEME)
        except KeyError:
            return None
        return parse_xml(part.blob)

    @staticmethod
    def _numbering(document: DocxDocument) -> _Element | None:
        try:
            numbering: _Element = document.part.numbering_part.element
        except (KeyError, NotImplementedError):
            return None
        return numbering

    @staticmethod
    def _table(element: _Element, ordinal: int) -> Block | None:
        content = read_table(element)
        if not content.rows:
            return None
        return Block(ordinal=ordinal, kind=BlockKind.TABLE, text=table_text(content), table=content)

    @staticmethod
    def _paragraph(
        element: _Element, ordinal: int, sheet: StyleSheet, numbering: NumberingResolver
    ) -> Block | None:
        props = sheet.paragraph(element)
        runs = [(run_text(run), sheet.run(run, props.style_id)) for run in paragraph_runs(element)]
        text = clean_text("".join(text for text, _ in runs))
        if not text:
            return None
        fonts = _fonts(runs)
        emphasized = bool(fonts) and all(font.bold for font in fonts)

        kind = BlockKind.PARAGRAPH
        level: int | None = None
        label: str | None = None
        numbered_top = False
        if props.numbering is not None:
            label = numbering.next_label(props.numbering.num_id, props.numbering.level)
            kind = BlockKind.LIST_ITEM
            level = props.numbering.level
            numbered_top = level == 0 and not numbering.is_bullet(
                props.numbering.num_id, props.numbering.level
            )
        else:
            manual = split_manual_label(text)
            if manual is not None:
                label, text, level = manual.label, manual.text, manual.depth
                kind = BlockKind.LIST_ITEM
                numbered_top = manual.depth == 0 and not manual.is_bullet

        if props.heading_level is not None:
            kind, level = BlockKind.HEADING, props.heading_level
        elif looks_like_heading(text, emphasized=emphasized, numbered_top=numbered_top):
            kind = BlockKind.HEADING
            level = 1 if label is None or numbered_top else (level or 0) + 1

        return Block(
            ordinal=ordinal,
            kind=kind,
            text=text,
            level=level,
            label=label,
            fonts=fonts,
            paragraph=props.format,
        )
