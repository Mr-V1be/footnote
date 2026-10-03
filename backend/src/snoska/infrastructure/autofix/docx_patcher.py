from __future__ import annotations

import io
import re
from typing import cast

import anyio.to_thread
import docx
from docx.document import Document as DocxDocument
from docx.oxml.text.paragraph import CT_P
from docx.shared import Mm, Pt
from docx.text.paragraph import Paragraph
from docx.types import ProvidesStoryPart
from lxml.etree import _Element

from snoska.domain.autofix.actions import (
    AppliedChange,
    ChangeKind,
    FixAction,
    FixPlan,
    ReplaceText,
    SetFirstLineIndent,
    SetFontSize,
    SetLineSpacing,
    SetMargins,
)
from snoska.domain.checks.rules.typography import dominant_size
from snoska.domain.documents.structure import Block, DocumentStructure
from snoska.infrastructure.parsing.docx.content import block_elements
from snoska.infrastructure.parsing.docx.xml import w
from snoska.infrastructure.parsing.units import emu_to_mm
from snoska.ports.autofix.patching import PatchResult

_SIDES = ("left", "right", "top", "bottom")
_TEXT = w("t")


def _number(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def _replace_in_paragraph(paragraph: _Element, before: str, after: str) -> bool:
    """Replace the first occurrence of ``before`` across the paragraph's runs,
    keeping the formatting of the run the match starts in."""
    nodes = list(paragraph.iter(_TEXT))
    text = "".join(node.text or "" for node in nodes)
    pattern = re.escape(before).replace(r"\ ", r"\s+")
    match = re.search(pattern, text)
    if match is None:
        return False
    start, end = match.span()
    offset = 0
    placed = False
    for node in nodes:
        value = node.text or ""
        low, high = offset, offset + len(value)
        offset = high
        if high <= start or low >= end:
            continue
        head = value[: max(start - low, 0)]
        tail = value[min(end - low, len(value)) :]
        node.text = head + (after if not placed else "") + tail
        placed = True
    return placed


class DocxPatcher:
    """Corrects the formatting of a DOCX with python-docx.

    Blocks are found by the same traversal the parser numbers them with, so a
    finding's block ordinal points at the paragraph or table it was about.
    """

    format_code = "docx"

    async def apply(
        self, content: bytes, plan: FixPlan, structure: DocumentStructure
    ) -> PatchResult:
        return await anyio.to_thread.run_sync(self._apply, content, plan, structure)

    def _apply(self, content: bytes, plan: FixPlan, structure: DocumentStructure) -> PatchResult:
        document = docx.Document(io.BytesIO(content))
        elements = list(block_elements(document.element.body))
        blocks = {block.ordinal: block for block in structure.blocks}
        changes: list[AppliedChange] = []
        missed: list[FixAction] = []
        for action in plan.actions:
            change: AppliedChange | None
            match action:
                case SetMargins():
                    change = self._margins(document, action)
                case SetFontSize():
                    change = self._font(elements, blocks, action)
                case SetLineSpacing():
                    change = self._spacing(elements, blocks, action)
                case SetFirstLineIndent():
                    change = self._indent(elements, blocks, action)
                case ReplaceText():
                    change = self._replace(elements, action)
            if change is None:
                missed.append(action)
            else:
                changes.append(change)
        buffer = io.BytesIO()
        document.save(buffer)
        return PatchResult(content=buffer.getvalue(), changes=tuple(changes), missed=tuple(missed))

    @staticmethod
    def _margins(document: DocxDocument, action: SetMargins) -> AppliedChange | None:
        widths = (action.left_mm, action.right_mm, action.top_mm, action.bottom_mm)
        minimum = dict(zip(_SIDES, widths, strict=True))
        before: list[str] = []
        after: list[str] = []
        for section in document.sections:
            for side in _SIDES:
                attribute = f"{side}_margin"
                current = getattr(section, attribute)
                current_mm = emu_to_mm(current) if current is not None else 0.0
                if current_mm < minimum[side] - 0.5:
                    setattr(section, attribute, Mm(minimum[side]))
                    before.append(f"{side}={round(current_mm)}")
                    after.append(f"{side}={round(minimum[side])}")
        if not after:
            return None
        return AppliedChange(
            check_code=action.check_code,
            kind=ChangeKind.FORMAT,
            block_ordinal=None,
            before=";".join(dict.fromkeys(before)),
            after=";".join(dict.fromkeys(after)),
        )

    @staticmethod
    def _paragraphs(
        elements: list[_Element], ordinals: tuple[int, ...]
    ) -> list[tuple[int, Paragraph]]:
        """The paragraphs among the blocks (tables keep their formatting)."""
        return [
            (ordinal, Paragraph(cast(CT_P, elements[ordinal]), cast(ProvidesStoryPart, None)))
            for ordinal in ordinals
            if 0 <= ordinal < len(elements) and elements[ordinal].tag == w("p")
        ]

    def _font(
        self, elements: list[_Element], blocks: dict[int, Block], action: SetFontSize
    ) -> AppliedChange | None:
        sizes: dict[float, int] = {}
        targets: set[float] = set()
        for ordinal, paragraph in self._paragraphs(elements, action.block_ordinals):
            block = blocks.get(ordinal)
            current = dominant_size(block) if block else None
            if current is None or action.min_pt <= current <= action.max_pt:
                continue
            target = min(max(current, action.min_pt), action.max_pt)
            for run in paragraph.runs:
                run.font.size = Pt(target)
            sizes[current] = sizes.get(current, 0) + 1
            targets.add(target)
        if not sizes:
            return None
        return AppliedChange(
            check_code=action.check_code,
            kind=ChangeKind.FORMAT,
            block_ordinal=None,
            before=", ".join(_number(size) for size in sorted(sizes)),
            after=", ".join(_number(size) for size in sorted(targets)),
            places=sum(sizes.values()),
        )

    def _spacing(
        self, elements: list[_Element], blocks: dict[int, Block], action: SetLineSpacing
    ) -> AppliedChange | None:
        before: set[float] = set()
        after: set[float] = set()
        count = 0
        for ordinal, paragraph in self._paragraphs(elements, action.block_ordinals):
            block = blocks.get(ordinal)
            current = block.paragraph.line_spacing if block and block.paragraph else None
            if current is None or action.min_multiple <= current <= action.max_multiple:
                continue
            target = min(max(current, action.min_multiple), action.max_multiple)
            paragraph.paragraph_format.line_spacing = target
            before.add(current)
            after.add(target)
            count += 1
        if not count:
            return None
        return AppliedChange(
            check_code=action.check_code,
            kind=ChangeKind.FORMAT,
            block_ordinal=None,
            before=", ".join(_number(value) for value in sorted(before)),
            after=", ".join(_number(value) for value in sorted(after)),
            places=count,
        )

    def _indent(
        self, elements: list[_Element], blocks: dict[int, Block], action: SetFirstLineIndent
    ) -> AppliedChange | None:
        before: set[float] = set()
        count = 0
        for ordinal, paragraph in self._paragraphs(elements, action.block_ordinals):
            block = blocks.get(ordinal)
            current = block.paragraph.first_line_indent_mm if block and block.paragraph else None
            paragraph.paragraph_format.first_line_indent = Mm(action.indent_mm)
            before.add(round((current or 0.0) / 10, 2))
            count += 1
        if not count:
            return None
        return AppliedChange(
            check_code=action.check_code,
            kind=ChangeKind.FORMAT,
            block_ordinal=None,
            before=", ".join(_number(value) for value in sorted(before)),
            after=_number(round(action.indent_mm / 10, 2)),
            places=count,
        )

    @staticmethod
    def _replace(elements: list[_Element], action: ReplaceText) -> AppliedChange | None:
        if not 0 <= action.block_ordinal < len(elements):
            return None
        element = elements[action.block_ordinal]
        paragraphs = [element] if element.tag == w("p") else list(element.iter(w("p")))
        for paragraph in paragraphs:
            if _replace_in_paragraph(paragraph, action.before, action.after):
                return AppliedChange(
                    check_code=action.check_code,
                    kind=ChangeKind.TEXT,
                    block_ordinal=action.block_ordinal,
                    before=action.before,
                    after=action.after,
                )
        return None
