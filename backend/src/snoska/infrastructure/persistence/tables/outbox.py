from __future__ import annotations

from sqlalchemy import Column, DateTime, Index, Integer, Table, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB

from snoska.infrastructure.persistence.tables.metadata import metadata

outbox_messages = Table(
    "outbox_messages",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("job_name", Text, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("available_at", DateTime(timezone=True), nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("dispatched_at", DateTime(timezone=True), nullable=True),
    Column("last_error", Text, nullable=True),
    Index(
        "ix_outbox_messages_due",
        "available_at",
        postgresql_where=text("dispatched_at IS NULL"),
    ),
)

# Channel the database notifies when new messages are inserted.
OUTBOX_CHANNEL = "snoska_outbox"
