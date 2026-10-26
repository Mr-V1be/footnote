from __future__ import annotations

import io
import statistics
from dataclasses import dataclass

import anyio.to_thread
import pdfplumber
from pdfminer.pdfdocument import PDFEncryptionError
from pdfplumber.utils.exceptions import MalformedPDFException, PdfminerException

from footnote.domain.documents.structure import Block, DocumentLayout, LayoutSource, PageSetup
from footnote.domain.documents.version import ExtractionMethod, ParseFailureCode
from footnote.infrastructure.parsing.pdf.lines import PageContent
from footnote.infrastructure.parsing.pdf.ocr_lines import recognised_page
from footnote.infrastructure.parsing.pdf.paragraphs import ParagraphBuilder
from footnote.infrastructure.parsing.pdf.text_layer import (
    MIN_TEXT_CHARS,
    read_text_page,
    visible_char_count,
)
from footnote.infrastructure.parsing.units import points_to_mm
from footnote.ports.document_parsing import DocumentParseError, ParsedDocument
from footnote.ports.ocr import OcrEngine


@dataclass(frozen=True, slots=True)
class PdfLimits:
    max_pages: int = 300
    max_scanned_pages: int = 60
    ocr_dpi: int = 300


@dataclass(frozen=True, slots=True)
class _ScannedPage:
    number: int
    png: bytes


def _render_png(page: pdfplumber.page.Page, dpi: int) -> bytes:
    image = page.to_image(resolution=dpi).original.convert("L")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()


def _measured_setup(page: PageContent) -> PageSetup:
    """Margins measured from where ink actually is on the page."""
    tops = [line.top for line in page.lines] + [table.top for table in page.tables]
    bottoms = [line.bottom for line in page.lines] + [table.bottom for table in page.tables]
    lefts = [line.x0 for line in page.lines]
    rights = [line.x1 for line in page.lines]
    return PageSetup(
        source=LayoutSource.MEASURED,
        width_mm=points_to_mm(page.width),
        height_mm=points_to_mm(page.height),
        margin_top_mm=points_to_mm(min(tops)) if tops else None,
        margin_bottom_mm=points_to_mm(page.height - max(bottoms)) if bottoms else None,
        margin_left_mm=points_to_mm(min(lefts)) if lefts else None,
        margin_right_mm=points_to_mm(page.width - max(rights)) if rights else None,
        first_page=page.number,
    )


class PdfParser:
    """Text-layer extraction with OCR fallback for pages that are images."""

    format_code = "pdf"

    def __init__(self, ocr: OcrEngine, limits: PdfLimits) -> None:
        self._ocr = ocr
        self._limits = limits

    async def parse(self, content: bytes) -> ParsedDocument:
        analysed = await anyio.to_thread.run_sync(self._analyse, content)
        pages: list[PageContent] = []
        recognised = 0
        for item in analysed:
            if isinstance(item, _ScannedPage):
                result = await self._ocr.recognize(item.png, dpi=self._limits.ocr_dpi)
                pages.append(recognised_page(result, item.number))
                recognised += 1
            else:
                pages.append(item)
        blocks: list[Block] = await anyio.to_thread.run_sync(
            lambda: ParagraphBuilder(pages).build()
        )
        confidences = [
            line.confidence for page in pages for line in page.lines if line.confidence is not None
        ]
        if recognised == 0:
            method = ExtractionMethod.PDF_TEXT
        elif recognised == len(pages):
            method = ExtractionMethod.PDF_OCR
        else:
            method = ExtractionMethod.PDF_MIXED
        return ParsedDocument(
            blocks=tuple(blocks),
            layout=DocumentLayout(pages=tuple(_measured_setup(page) for page in pages)),
            method=method,
            page_count=len(pages),
            ocr_confidence=round(statistics.fmean(confidences), 3) if confidences else None,
        )

    def _analyse(self, content: bytes) -> list[PageContent | _ScannedPage]:
        try:
            pdf = pdfplumber.open(io.BytesIO(content))
        except PdfminerException as exc:
            if isinstance(exc.args[0] if exc.args else None, PDFEncryptionError):
                raise DocumentParseError(
                    ParseFailureCode.ENCRYPTED_FILE, "PDF is encrypted"
                ) from exc
            raise DocumentParseError(ParseFailureCode.CORRUPTED_FILE, str(exc)) from exc
        except MalformedPDFException as exc:
            raise DocumentParseError(ParseFailureCode.CORRUPTED_FILE, str(exc)) from exc
        with pdf:
            if len(pdf.pages) > self._limits.max_pages:
                raise DocumentParseError(ParseFailureCode.TOO_LARGE, "too many pages")
            analysed: list[PageContent | _ScannedPage] = []
            scanned = 0
            for number, page in enumerate(pdf.pages, start=1):
                if visible_char_count(page) >= MIN_TEXT_CHARS:
                    analysed.append(read_text_page(page, number))
                else:
                    scanned += 1
                    if scanned > self._limits.max_scanned_pages:
                        raise DocumentParseError(
                            ParseFailureCode.TOO_LARGE, "too many scanned pages"
                        )
                    analysed.append(
                        _ScannedPage(number=number, png=_render_png(page, self._limits.ocr_dpi))
                    )
                page.close()
            return analysed
