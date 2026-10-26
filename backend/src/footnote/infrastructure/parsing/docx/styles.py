from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from lxml.etree import _Element

from footnote.domain.documents.structure import Alignment, ParagraphFormat
from footnote.infrastructure.parsing.docx.xml import NS, attr, child, int_attr, toggle, w
from footnote.infrastructure.parsing.units import points_to_mm

TWIPS_PER_POINT = 20
HALF_POINTS_PER_POINT = 2
AUTO_LINE_UNITS = 240  # w:spacing/@w:line is in 240ths of a line for lineRule="auto"
MAX_BASED_ON_DEPTH = 20

_HEADING_STYLE = re.compile(r"^(?:heading|заголовок)\s*(\d)$", re.IGNORECASE)
_ALIGNMENTS = {
    "left": Alignment.LEFT,
    "start": Alignment.LEFT,
    "center": Alignment.CENTER,
    "right": Alignment.RIGHT,
    "end": Alignment.RIGHT,
    "both": Alignment.JUSTIFY,
    "distribute": Alignment.JUSTIFY,
}


@dataclass(frozen=True, slots=True)
class RunProps:
    family: str | None
    size_pt: float | None
    bold: bool
    italic: bool


@dataclass(frozen=True, slots=True)
class NumberingRef:
    num_id: str
    level: int


@dataclass(frozen=True, slots=True)
class ParagraphProps:
    style_id: str | None
    format: ParagraphFormat
    heading_level: int | None
    numbering: NumberingRef | None


def _first[T](sources: Sequence[_Element | None], read: Callable[[_Element], T | None]) -> T | None:
    for source in sources:
        if source is None:
            continue
        value = read(source)
        if value is not None:
            return value
    return None


class StyleSheet:
    """Effective formatting: direct → style chain (basedOn) → document defaults."""

    def __init__(self, styles_root: _Element | None, theme_root: _Element | None) -> None:
        self._styles: dict[str, _Element] = {}
        self._default_paragraph_style: str | None = None
        self._default_ppr: _Element | None = None
        self._default_rpr: _Element | None = None
        if styles_root is not None:
            for style in styles_root.findall(w("style")):
                style_id = attr(style, "styleId")
                if style_id is None:
                    continue
                self._styles[style_id] = style
                if attr(style, "type") == "paragraph" and attr(style, "default") in ("1", "true"):
                    self._default_paragraph_style = style_id
            defaults = child(styles_root, "docDefaults")
            self._default_ppr = child(child(defaults, "pPrDefault"), "pPr")
            self._default_rpr = child(child(defaults, "rPrDefault"), "rPr")
        self._theme_fonts = self._read_theme_fonts(theme_root)

    @staticmethod
    def _read_theme_fonts(theme_root: _Element | None) -> dict[str, str]:
        fonts: dict[str, str] = {}
        if theme_root is None:
            return fonts
        for key in ("major", "minor"):
            latin = theme_root.find(f".//a:{key}Font/a:latin", NS)
            if latin is not None and latin.get("typeface"):
                fonts[key] = latin.get("typeface", "")
        return fonts

    def _chain(self, style_id: str | None, part: str) -> list[_Element | None]:
        chain: list[_Element | None] = []
        seen: set[str] = set()
        current = style_id
        while current and current not in seen and len(seen) < MAX_BASED_ON_DEPTH:
            seen.add(current)
            style = self._styles.get(current)
            if style is None:
                break
            chain.append(child(style, part))
            current = attr(child(style, "basedOn"), "val")
        return chain

    def style_name(self, style_id: str | None) -> str | None:
        style = self._styles.get(style_id or "")
        return attr(child(style, "name"), "val") if style is not None else None

    def paragraph(self, p: _Element) -> ParagraphProps:
        direct = child(p, "pPr")
        style_id = attr(child(direct, "pStyle"), "val") or self._default_paragraph_style
        sources: list[_Element | None] = [direct, *self._chain(style_id, "pPr"), self._default_ppr]
        return ParagraphProps(
            style_id=style_id,
            format=self._paragraph_format(sources),
            heading_level=self._heading_level(style_id, sources),
            numbering=self._numbering(sources),
        )

    def run(self, r: _Element, paragraph_style_id: str | None) -> RunProps:
        direct = child(r, "rPr")
        run_style = attr(child(direct, "rStyle"), "val")
        sources: list[_Element | None] = [
            direct,
            *self._chain(run_style, "rPr"),
            *self._chain(paragraph_style_id, "rPr"),
            self._default_rpr,
        ]
        size = _first(sources, lambda rpr: int_attr(child(rpr, "sz"), "val"))
        return RunProps(
            family=_first(sources, self._font_family),
            size_pt=size / HALF_POINTS_PER_POINT if size is not None else None,
            bold=bool(_first(sources, lambda rpr: toggle(child(rpr, "b")))),
            italic=bool(_first(sources, lambda rpr: toggle(child(rpr, "i")))),
        )

    def _font_family(self, rpr: _Element) -> str | None:
        fonts = child(rpr, "rFonts")
        if fonts is None:
            return None
        explicit = attr(fonts, "hAnsi") or attr(fonts, "ascii")
        if explicit:
            return explicit
        theme = attr(fonts, "hAnsiTheme") or attr(fonts, "asciiTheme")
        if theme:
            return self._theme_fonts.get("major" if theme.startswith("major") else "minor")
        return None

    def _heading_level(
        self, style_id: str | None, sources: Sequence[_Element | None]
    ) -> int | None:
        outline = _first(sources, lambda ppr: int_attr(child(ppr, "outlineLvl"), "val"))
        if outline is not None and outline < 9:
            return outline + 1
        name = self.style_name(style_id) or ""
        match = _HEADING_STYLE.match(name)
        if match:
            return int(match.group(1))
        return 1 if name.lower() == "title" else None

    @staticmethod
    def _numbering(sources: Sequence[_Element | None]) -> NumberingRef | None:
        num_id = _first(sources, lambda ppr: attr(child(child(ppr, "numPr"), "numId"), "val"))
        if num_id is None or num_id == "0":
            return None
        level = _first(sources, lambda ppr: int_attr(child(child(ppr, "numPr"), "ilvl"), "val"))
        return NumberingRef(num_id=num_id, level=level or 0)

    @staticmethod
    def _paragraph_format(sources: Sequence[_Element | None]) -> ParagraphFormat:
        def twips_attr(tag: str, name: str) -> Callable[[_Element], int | None]:
            return lambda ppr: int_attr(child(ppr, tag), name)

        jc = _first(sources, lambda ppr: attr(child(ppr, "jc"), "val"))
        first_line = _first(sources, twips_attr("ind", "firstLine"))
        hanging = _first(sources, twips_attr("ind", "hanging"))
        left = _first(sources, twips_attr("ind", "left"))
        if left is None:
            left = _first(sources, twips_attr("ind", "start"))
        line = _first(sources, twips_attr("spacing", "line"))
        line_rule = _first(sources, lambda ppr: attr(child(ppr, "spacing"), "lineRule"))
        before = _first(sources, twips_attr("spacing", "before"))
        after = _first(sources, twips_attr("spacing", "after"))
        indent = (
            first_line if first_line is not None else (-hanging if hanging is not None else None)
        )
        return ParagraphFormat(
            alignment=_ALIGNMENTS.get(jc or "", Alignment.LEFT if jc is None else None),
            first_line_indent_mm=(
                points_to_mm(indent / TWIPS_PER_POINT) if indent is not None else None
            ),
            left_indent_mm=points_to_mm(left / TWIPS_PER_POINT) if left is not None else None,
            line_spacing=(
                round(line / AUTO_LINE_UNITS, 2)
                if line is not None and (line_rule in (None, "auto"))
                else None
            ),
            space_before_pt=before / TWIPS_PER_POINT if before is not None else None,
            space_after_pt=after / TWIPS_PER_POINT if after is not None else None,
        )
