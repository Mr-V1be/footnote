from __future__ import annotations

from snoska.api.schemas.common import ApiModel


class DocumentKindOut(ApiModel):
    code: str
    is_default: bool


class DocumentFormatOut(ApiModel):
    code: str
    media_type: str
    extensions: list[str]


class CatalogOut(ApiModel):
    kinds: list[DocumentKindOut]
    formats: list[DocumentFormatOut]
    requisite_kinds: list[str]
    max_upload_bytes: int
