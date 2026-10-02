from __future__ import annotations

from datetime import datetime
from uuid import UUID

from snoska.api.schemas.common import ApiModel
from snoska.api.schemas.tenancy import WorkspaceOut
from snoska.application.documents.queries import DocumentDetails
from snoska.domain.documents.structure import Block, DocumentStructure, PageSetup
from snoska.domain.documents.version import DocumentVersion
from snoska.ports.document_repositories import DocumentListItem


class DocumentListItemOut(ApiModel):
    id: UUID
    title: str
    kind: str
    created_at: datetime
    updated_at: datetime
    latest_version: int
    status: str
    failure_code: str | None
    format: str
    size_bytes: int
    page_count: int | None
    created_by_name: str | None

    @classmethod
    def of(cls, item: DocumentListItem) -> DocumentListItemOut:
        return cls(
            id=item.id,
            title=item.title,
            kind=item.kind_code,
            created_at=item.created_at,
            updated_at=item.updated_at,
            latest_version=item.latest_version_number,
            status=item.latest_status.value,
            failure_code=item.latest_failure_code.value if item.latest_failure_code else None,
            format=item.latest_format_code,
            size_bytes=item.latest_size_bytes,
            page_count=item.latest_page_count,
            created_by_name=item.created_by_name,
        )


class DocumentPageOut(ApiModel):
    items: list[DocumentListItemOut]
    next_cursor: str | None


class VersionOut(ApiModel):
    number: int
    filename: str
    format: str
    media_type: str
    size_bytes: int
    status: str
    failure_code: str | None
    uploaded_at: datetime
    parsed_at: datetime | None
    method: str | None
    page_count: int | None
    block_count: int | None
    requisite_count: int | None
    ocr_confidence: float | None

    @classmethod
    def of(cls, version: DocumentVersion) -> VersionOut:
        summary = version.summary
        return cls(
            number=version.number,
            filename=version.file.filename,
            format=version.file.format_code,
            media_type=version.file.media_type,
            size_bytes=version.file.size_bytes,
            status=version.status.value,
            failure_code=version.failure_code.value if version.failure_code else None,
            uploaded_at=version.created_at,
            parsed_at=version.parsed_at,
            method=summary.method.value if summary else None,
            page_count=summary.page_count if summary else None,
            block_count=summary.block_count if summary else None,
            requisite_count=summary.requisite_count if summary else None,
            ocr_confidence=summary.ocr_confidence if summary else None,
        )


class DocumentOut(ApiModel):
    id: UUID
    title: str
    kind: str
    workspace: WorkspaceOut
    created_at: datetime
    updated_at: datetime
    latest_version: int
    versions: list[VersionOut]

    @classmethod
    def of(cls, details: DocumentDetails) -> DocumentOut:
        document = details.document
        return cls(
            id=document.id,
            title=document.title,
            kind=document.kind_code,
            workspace=WorkspaceOut(
                id=details.workspace.id, slug=details.workspace.slug, name=details.workspace.name
            ),
            created_at=document.created_at,
            updated_at=document.updated_at,
            latest_version=document.latest_version_number,
            versions=[VersionOut.of(version) for version in details.versions],
        )


class FontOut(ApiModel):
    family: str | None
    size_pt: float | None
    bold: bool
    italic: bool
    chars: int


class ParagraphFormatOut(ApiModel):
    alignment: str | None
    first_line_indent_mm: float | None
    left_indent_mm: float | None
    line_spacing: float | None
    space_before_pt: float | None
    space_after_pt: float | None


class TableCellOut(ApiModel):
    text: str
    col_span: int
    row_span: int


class BlockOut(ApiModel):
    ordinal: int
    kind: str
    text: str
    level: int | None
    label: str | None
    page: int | None
    fonts: list[FontOut]
    paragraph: ParagraphFormatOut | None
    table: list[list[TableCellOut]] | None
    confidence: float | None

    @classmethod
    def of(cls, block: Block) -> BlockOut:
        p = block.paragraph
        return cls(
            ordinal=block.ordinal,
            kind=block.kind.value,
            text=block.text,
            level=block.level,
            label=block.label,
            page=block.page,
            fonts=[
                FontOut(
                    family=f.family, size_pt=f.size_pt, bold=f.bold, italic=f.italic, chars=f.chars
                )
                for f in block.fonts
            ],
            paragraph=(
                ParagraphFormatOut(
                    alignment=p.alignment.value if p.alignment else None,
                    first_line_indent_mm=p.first_line_indent_mm,
                    left_indent_mm=p.left_indent_mm,
                    line_spacing=p.line_spacing,
                    space_before_pt=p.space_before_pt,
                    space_after_pt=p.space_after_pt,
                )
                if p is not None
                else None
            ),
            table=(
                [
                    [
                        TableCellOut(text=c.text, col_span=c.col_span, row_span=c.row_span)
                        for c in row
                    ]
                    for row in block.table.rows
                ]
                if block.table is not None
                else None
            ),
            confidence=block.confidence,
        )


class RequisiteOut(ApiModel):
    kind: str
    block_ordinal: int
    start: int
    end: int
    value: str


class OutlineEntryOut(ApiModel):
    block_ordinal: int
    level: int
    label: str | None
    text: str


class PageSetupOut(ApiModel):
    source: str
    width_mm: float
    height_mm: float
    margin_top_mm: float | None
    margin_bottom_mm: float | None
    margin_left_mm: float | None
    margin_right_mm: float | None
    first_page: int | None

    @classmethod
    def of(cls, page: PageSetup) -> PageSetupOut:
        return cls(
            source=page.source.value,
            width_mm=page.width_mm,
            height_mm=page.height_mm,
            margin_top_mm=page.margin_top_mm,
            margin_bottom_mm=page.margin_bottom_mm,
            margin_left_mm=page.margin_left_mm,
            margin_right_mm=page.margin_right_mm,
            first_page=page.first_page,
        )


class StructureOut(ApiModel):
    version: VersionOut
    blocks: list[BlockOut]
    requisites: list[RequisiteOut]
    outline: list[OutlineEntryOut]
    layout: list[PageSetupOut]

    @classmethod
    def of(cls, version: DocumentVersion, structure: DocumentStructure | None) -> StructureOut:
        if structure is None:
            return cls(
                version=VersionOut.of(version), blocks=[], requisites=[], outline=[], layout=[]
            )
        return cls(
            version=VersionOut.of(version),
            blocks=[BlockOut.of(block) for block in structure.blocks],
            requisites=[
                RequisiteOut(
                    kind=r.kind.value,
                    block_ordinal=r.block_ordinal,
                    start=r.start,
                    end=r.end,
                    value=r.value,
                )
                for r in structure.requisites
            ],
            outline=[
                OutlineEntryOut(
                    block_ordinal=e.block_ordinal, level=e.level, label=e.label, text=e.text
                )
                for e in structure.outline()
            ],
            layout=[PageSetupOut.of(page) for page in structure.layout.pages],
        )


class UploadOut(ApiModel):
    document_id: UUID
    version_number: int
    created: bool
