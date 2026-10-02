from __future__ import annotations

from dataclasses import dataclass

from snoska.application.documents.upload import UploadLimits
from snoska.domain.documents.formats import DocumentFormat, FormatRegistry
from snoska.domain.documents.kinds import DocumentKind, DocumentKindRegistry
from snoska.domain.documents.structure import RequisiteKind


@dataclass(frozen=True, slots=True)
class DocumentCatalog:
    """Registries the interface renders from instead of hard-coding lists."""

    kinds: tuple[DocumentKind, ...]
    default_kind: DocumentKind
    formats: tuple[DocumentFormat, ...]
    requisite_kinds: tuple[RequisiteKind, ...]
    max_upload_bytes: int


class CatalogQuery:
    def __init__(
        self, kinds: DocumentKindRegistry, formats: FormatRegistry, limits: UploadLimits
    ) -> None:
        self._catalog = DocumentCatalog(
            kinds=kinds.all(),
            default_kind=kinds.default,
            formats=formats.all(),
            requisite_kinds=tuple(RequisiteKind),
            max_upload_bytes=limits.max_bytes,
        )

    def get(self) -> DocumentCatalog:
        return self._catalog
