from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from footnote.domain.documents.structure import BlockKind, LayoutSource
from footnote.domain.documents.version import ExtractionMethod, ParseFailureCode
from footnote.infrastructure.parsing.ocr.tesseract import TesseractConfig, TesseractOcrEngine
from footnote.infrastructure.parsing.pdf.lines import parse_font_name
from footnote.infrastructure.parsing.pdf.parser import PdfLimits, PdfParser
from footnote.ports.document_parsing import DocumentParseError

DEMO = Path(__file__).parents[3] / "demo" / "documents"


def parser() -> PdfParser:
    return PdfParser(TesseractOcrEngine(TesseractConfig()), PdfLimits())


async def test_text_layer_paragraphs_numbering_and_measured_margins() -> None:
    parsed = await parser().parse(
        (DEMO / "polyarnaya-zvezda" / "dogovor-porucheniya-15-2026.pdf").read_bytes()
    )
    assert parsed.method is ExtractionMethod.PDF_TEXT
    labels = [block.label for block in parsed.blocks if block.kind is BlockKind.LIST_ITEM]
    assert labels[:3] == ["1.1.", "1.2.", "2.1."]
    headings = [block.text for block in parsed.blocks if block.kind is BlockKind.HEADING]
    assert "Предмет договора" in headings
    page = parsed.layout.pages[0]
    assert page.source is LayoutSource.MEASURED
    assert page.margin_left_mm == pytest.approx(25, abs=1.5)
    assert parsed.blocks[2].fonts[0].family == "TimesNewRoman"


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed")
async def test_scanned_pages_are_recognised() -> None:
    parsed = await parser().parse((DEMO / "polyarnaya-zvezda" / "prikaz-7-od.pdf").read_bytes())
    assert parsed.method is ExtractionMethod.PDF_OCR
    assert parsed.ocr_confidence is not None
    assert parsed.ocr_confidence > 0.8
    text = " ".join(block.text for block in parsed.blocks)
    assert "ПРИКАЗ" in text
    assert "Об утверждении Политики" in text


async def test_garbage_is_reported_as_corrupted() -> None:
    with pytest.raises(DocumentParseError) as error:
        await parser().parse(b"%PDF-1.7\nthis is not a pdf")
    assert error.value.code is ParseFailureCode.CORRUPTED_FILE


@pytest.mark.parametrize(
    ("raw", "family", "bold"),
    [
        ("ABCDEF+TimesNewRomanPSMT", "TimesNewRoman", False),
        ("TimesNewRomanPS-BoldMT", "TimesNewRoman", True),
        ("Arial,Bold", "Arial", True),
        ("Times-Roman", "Times", False),
    ],
)
def test_font_names(raw: str, family: str, bold: bool) -> None:
    font = parse_font_name(raw)
    assert (font.family, font.bold) == (family, bold)
