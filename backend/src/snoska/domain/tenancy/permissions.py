from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    """Capabilities checked by the application layer.

    Roles grant permissions; code never checks role names directly.
    """

    DOCUMENTS_READ = "documents.read"
    DOCUMENTS_UPLOAD = "documents.upload"
    CHECKS_RUN = "checks.run"
    # Accept or reject a finding: a legal judgement.
    FINDINGS_DECIDE = "findings.decide"
    # Mark a finding fixed or reopen it: work on the document.
    FINDINGS_RESOLVE = "findings.resolve"
    CORPUS_READ = "corpus.read"
    PLATFORM_TENANTS_READ = "platform.tenants.read"
