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
    # Ask the corpus a question; answers use the organization's quota.
    NORMS_ASK = "norms.ask"
    # Administration of the organization.
    MEMBERS_MANAGE = "members.manage"
    WORKSPACES_MANAGE = "workspaces.manage"
    AUDIT_READ = "audit.read"
    INTEGRATIONS_MANAGE = "integrations.manage"
    BILLING_READ = "billing.read"
    BILLING_MANAGE = "billing.manage"
    # The platform's operator.
    PLATFORM_TENANTS_READ = "platform.tenants.read"
    PLATFORM_PLANS_MANAGE = "platform.plans.manage"
    PLATFORM_SYSTEM_READ = "platform.system.read"
