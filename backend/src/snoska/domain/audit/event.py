from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from snoska.domain.tenancy.access import Actor

AuditValue = str | int | bool


class AuditAction(StrEnum):
    """Everything the audit log records, grouped by the part before the dot."""

    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_VERSION_ADDED = "document.version_added"
    DOCUMENT_AUTOFIXED = "document.autofixed"
    CHECK_REQUESTED = "check.requested"
    FINDING_REVIEWED = "finding.reviewed"
    MEMBER_INVITED = "member.invited"
    MEMBER_ROLE_CHANGED = "member.role_changed"
    MEMBER_REMOVED = "member.removed"
    WORKSPACE_CREATED = "workspace.created"
    WORKSPACE_UPDATED = "workspace.updated"
    WORKSPACE_DELETED = "workspace.deleted"
    WORKSPACE_MEMBER_SET = "workspace.member_set"
    WORKSPACE_MEMBER_REMOVED = "workspace.member_removed"
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"
    WEBHOOK_CREATED = "webhook.created"
    WEBHOOK_UPDATED = "webhook.updated"
    WEBHOOK_DELETED = "webhook.deleted"
    PLAN_CHANGE_REQUESTED = "billing.plan_change_requested"
    INVOICE_PAID = "billing.invoice_paid"
    PLAN_CHANGED = "billing.plan_changed"

    @property
    def category(self) -> str:
        return self.value.split(".", 1)[0]


AUDIT_CATEGORIES: tuple[str, ...] = tuple(dict.fromkeys(action.category for action in AuditAction))


@dataclass(frozen=True, slots=True)
class AuditTarget:
    """What the action was about: a document, a member, a key..."""

    type: str
    id: str
    label: str


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One entry of an organization's audit log: who did what, to what, when.
    Entries are written in the same transaction as the change and never edited."""

    id: UUID
    organization_id: UUID
    occurred_at: datetime
    actor: Actor
    action: AuditAction
    target: AuditTarget
    details: Mapping[str, AuditValue] = field(default_factory=dict)
