from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from footnote.infrastructure.persistence.tables.metadata import metadata

api_keys = Table(
    "api_keys",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("organization_id", Uuid, nullable=False),
    Column("name", Text, nullable=False),
    Column("prefix", Text, nullable=False, unique=True),
    Column("token_hash", Text, nullable=False),
    Column("scopes", ARRAY(Text), nullable=False),
    Column("created_by", Uuid, nullable=False),
    Column("created_by_label", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_used_at", DateTime(timezone=True), nullable=True),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
)

webhook_endpoints = Table(
    "webhook_endpoints",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("organization_id", Uuid, nullable=False),
    Column("url", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("events", ARRAY(Text), nullable=False),
    # The signing secret, sealed with the platform's key.
    Column("secret_sealed", Text, nullable=False),
    Column("active", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("id", "organization_id"),
)

webhook_deliveries = Table(
    "webhook_deliveries",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("organization_id", Uuid, nullable=False),
    Column("endpoint_id", Uuid, nullable=False),
    Column("event_id", Uuid, nullable=False),
    Column("event", Text, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("next_attempt_at", DateTime(timezone=True), nullable=True),
    Column("last_status_code", Integer, nullable=True),
    Column("last_error", Text, nullable=True),
    Column("last_duration_ms", Integer, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("delivered_at", DateTime(timezone=True), nullable=True),
    ForeignKeyConstraint(
        ["endpoint_id", "organization_id"],
        ["webhook_endpoints.id", "webhook_endpoints.organization_id"],
        ondelete="CASCADE",
    ),
    CheckConstraint(
        "status IN ('pending', 'delivered', 'retrying', 'failed')", name="status_known"
    ),
    Index("ix_webhook_deliveries_endpoint_time", "endpoint_id", "created_at"),
)
