from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, DateTime, Index, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

from snoska.infrastructure.persistence.tables.metadata import metadata

audit_events = Table(
    "audit_events",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("organization_id", Uuid, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("actor_kind", Text, nullable=False),
    Column("actor_id", Uuid, nullable=True),
    Column("actor_label", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column("target_type", Text, nullable=False),
    Column("target_id", Text, nullable=False),
    Column("target_label", Text, nullable=False),
    Column("details", JSONB, nullable=False, server_default="{}"),
    CheckConstraint("actor_kind IN ('user', 'api_key', 'system')", name="actor_kind_known"),
    Index("ix_audit_events_org_time", "organization_id", "occurred_at", "id"),
)
