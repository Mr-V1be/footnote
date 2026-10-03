from __future__ import annotations

from snoska.domain.audit.event import AuditTarget
from snoska.domain.documents.document import Document


def document_target(document: Document) -> AuditTarget:
    return AuditTarget(type="document", id=str(document.id), label=document.title)
