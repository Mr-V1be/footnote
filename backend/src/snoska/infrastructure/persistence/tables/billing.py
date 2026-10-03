from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Sequence,
    Table,
    Text,
    Uuid,
)

from snoska.infrastructure.persistence.tables.metadata import metadata

subscriptions = Table(
    "subscriptions",
    metadata,
    Column("organization_id", Uuid, primary_key=True),
    Column("plan_code", Text, nullable=False),
    Column("period_start", Date, nullable=False),
    Column("pending_plan_code", Text, nullable=True),
    Column("revision", Integer, nullable=False),
)

usage_ledger = Table(
    "usage_ledger",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("organization_id", Uuid, nullable=False),
    Column("metric", Text, nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("reason", Text, nullable=False),
    Column("reference", Text, nullable=False),
    Column("period_start", Date, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("quantity > 0", name="quantity_positive"),
    Index("ix_usage_ledger_period", "organization_id", "period_start", "metric"),
)

INVOICE_NUMBERS = Sequence("invoice_number_seq", metadata=metadata)

invoices = Table(
    "invoices",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("organization_id", Uuid, nullable=False),
    Column("number", Text, nullable=False, unique=True),
    Column("plan_code", Text, nullable=False),
    Column("amount_kopecks", Integer, nullable=False),
    Column("period_start", Date, nullable=False),
    Column("status", Text, nullable=False),
    Column("issued_at", DateTime(timezone=True), nullable=False),
    Column("payment_id", Text, nullable=True),
    Column("payment_url", Text, nullable=True),
    Column("paid_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("status IN ('open', 'paid', 'void')", name="status_known"),
    CheckConstraint("amount_kopecks >= 0", name="amount_non_negative"),
)

payment_events = Table(
    "payment_events",
    metadata,
    Column("organization_id", Uuid, nullable=False),
    Column("provider", Text, nullable=False),
    Column("event_id", Text, nullable=False),
    Column("invoice_id", Uuid, nullable=False),
    Column("received_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("provider", "event_id"),
)
