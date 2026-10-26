from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, delete, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from footnote.domain.documents.structure import (
    Alignment,
    Block,
    BlockKind,
    DocumentLayout,
    DocumentStructure,
    FontUsage,
    LayoutSource,
    PageSetup,
    ParagraphFormat,
    TableCell,
    TableContent,
)
from footnote.infrastructure.persistence.tables.documents import (
    document_blocks,
    document_structures,
    document_versions,
)

# Rows per INSERT; keeps statements well below the protocol parameter limit.
_INSERT_BATCH = 500


def _block_attrs(block: Block) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    if block.fonts:
        attrs["fonts"] = [
            {"f": f.family, "s": f.size_pt, "b": f.bold, "i": f.italic, "n": f.chars}
            for f in block.fonts
        ]
    if block.paragraph is not None:
        p = block.paragraph
        attrs["para"] = {
            "align": p.alignment.value if p.alignment else None,
            "indent_first_mm": p.first_line_indent_mm,
            "indent_left_mm": p.left_indent_mm,
            "line_spacing": p.line_spacing,
            "space_before_pt": p.space_before_pt,
            "space_after_pt": p.space_after_pt,
        }
    if block.table is not None:
        attrs["table"] = [
            [{"t": cell.text, "cs": cell.col_span, "rs": cell.row_span} for cell in row]
            for row in block.table.rows
        ]
    if block.confidence is not None:
        attrs["conf"] = block.confidence
    return attrs


def _block(row: RowMapping) -> Block:
    attrs: dict[str, Any] = row["attrs"]
    para = attrs.get("para")
    table = attrs.get("table")
    return Block(
        ordinal=row["ordinal"],
        kind=BlockKind(row["kind"]),
        text=row["text"],
        level=row["level"],
        label=row["label"],
        page=row["page"],
        fonts=tuple(
            FontUsage(family=f["f"], size_pt=f["s"], bold=f["b"], italic=f["i"], chars=f["n"])
            for f in attrs.get("fonts", ())
        ),
        paragraph=(
            ParagraphFormat(
                alignment=Alignment(para["align"]) if para.get("align") else None,
                first_line_indent_mm=para.get("indent_first_mm"),
                left_indent_mm=para.get("indent_left_mm"),
                line_spacing=para.get("line_spacing"),
                space_before_pt=para.get("space_before_pt"),
                space_after_pt=para.get("space_after_pt"),
            )
            if para is not None
            else None
        ),
        table=(
            TableContent(
                rows=tuple(
                    tuple(
                        TableCell(text=cell["t"], col_span=cell["cs"], row_span=cell["rs"])
                        for cell in row_cells
                    )
                    for row_cells in table
                )
            )
            if table is not None
            else None
        ),
        confidence=attrs.get("conf"),
    )


def _layout_json(layout: DocumentLayout) -> list[dict[str, Any]]:
    return [
        {
            "source": page.source.value,
            "width_mm": page.width_mm,
            "height_mm": page.height_mm,
            "margin_top_mm": page.margin_top_mm,
            "margin_bottom_mm": page.margin_bottom_mm,
            "margin_left_mm": page.margin_left_mm,
            "margin_right_mm": page.margin_right_mm,
            "first_page": page.first_page,
        }
        for page in layout.pages
    ]


def _layout(data: list[dict[str, Any]]) -> DocumentLayout:
    return DocumentLayout(
        pages=tuple(
            PageSetup(
                source=LayoutSource(page["source"]),
                width_mm=page["width_mm"],
                height_mm=page["height_mm"],
                margin_top_mm=page["margin_top_mm"],
                margin_bottom_mm=page["margin_bottom_mm"],
                margin_left_mm=page["margin_left_mm"],
                margin_right_mm=page["margin_right_mm"],
                first_page=page.get("first_page"),
            )
            for page in data
        )
    )


class SqlDocumentStructureRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def replace(self, version_id: UUID, structure: DocumentStructure) -> None:
        organization_id = await self._connection.scalar(
            select(document_versions.c.organization_id).where(document_versions.c.id == version_id)
        )
        if organization_id is None:
            raise LookupError("version not found")
        await self._connection.execute(
            delete(document_structures).where(document_structures.c.version_id == version_id)
        )
        await self._connection.execute(
            insert(document_structures).values(
                version_id=version_id,
                organization_id=organization_id,
                layout=_layout_json(structure.layout),
            )
        )
        rows = [
            {
                "version_id": version_id,
                "organization_id": organization_id,
                "ordinal": block.ordinal,
                "kind": block.kind.value,
                "text": block.text,
                "level": block.level,
                "label": block.label,
                "page": block.page,
                "attrs": _block_attrs(block),
            }
            for block in structure.blocks
        ]
        for start in range(0, len(rows), _INSERT_BATCH):
            await self._connection.execute(
                insert(document_blocks), rows[start : start + _INSERT_BATCH]
            )

    async def load(self, version_id: UUID) -> DocumentStructure | None:
        head = await self._connection.execute(
            select(document_structures).where(document_structures.c.version_id == version_id)
        )
        header = head.mappings().first()
        if header is None:
            return None
        result = await self._connection.execute(
            select(document_blocks)
            .where(document_blocks.c.version_id == version_id)
            .order_by(document_blocks.c.ordinal)
        )
        return DocumentStructure(
            blocks=tuple(_block(row) for row in result.mappings()),
            layout=_layout(header["layout"]),
        )
