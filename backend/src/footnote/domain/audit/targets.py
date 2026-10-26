from __future__ import annotations

from footnote.domain.audit.event import AuditTarget
from footnote.domain.documents.document import Document


def document_target(document: Document) -> AuditTarget:
    return AuditTarget(type="document", id=str(document.id), label=document.title)
