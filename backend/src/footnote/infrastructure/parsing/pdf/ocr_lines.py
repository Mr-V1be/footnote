from __future__ import annotations

from footnote.infrastructure.parsing.pdf.lines import PageContent, TextLine
from footnote.ports.ocr import OcrPage

POINTS_PER_INCH = 72


def recognised_page(ocr: OcrPage, number: int) -> PageContent:
    """Converts recogniser output (pixels) into page lines (points).

    Fonts are unknown for recognised text, so lines carry no font usage and
    the paragraph builder relies on geometry alone.
    """
    scale = POINTS_PER_INCH / ocr.dpi
    lines = tuple(
        TextLine(
            text=line.text,
            x0=line.left * scale,
            x1=line.right * scale,
            top=line.top * scale,
            bottom=line.bottom * scale,
            size_pt=None,
            fonts=(),
            confidence=line.confidence,
        )
        for line in sorted(ocr.lines, key=lambda line: (line.top, line.left))
        if line.text.strip()
    )
    return PageContent(
        number=number,
        width=ocr.width * scale,
        height=ocr.height * scale,
        lines=lines,
        tables=(),
    )
