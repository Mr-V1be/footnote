from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    """Capabilities checked by the application layer.

    Roles grant permissions; code never checks role names directly.
    """

    DOCUMENTS_READ = "documents.read"
    DOCUMENTS_UPLOAD = "documents.upload"
    CORPUS_READ = "corpus.read"
    PLATFORM_TENANTS_READ = "platform.tenants.read"
