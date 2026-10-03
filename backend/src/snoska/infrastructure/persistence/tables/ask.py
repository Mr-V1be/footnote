from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

from snoska.infrastructure.persistence.tables.metadata import metadata

conversations = Table(
    "conversations",
    metadata,
    Column("id", Uuid, nullable=False),
    Column("organization_id", Uuid, nullable=False),
    Column("user_id", Uuid, nullable=False),
    Column("title", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("id"),
    UniqueConstraint("id", "organization_id"),
    Index("ix_conversations_user", "organization_id", "user_id", "updated_at"),
)

conversation_turns = Table(
    "conversation_turns",
    metadata,
    Column("id", Uuid, nullable=False),
    Column("organization_id", Uuid, nullable=False),
    Column("conversation_id", Uuid, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("question", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("answer", Text, nullable=True),
    Column("citations", JSONB, nullable=False),
    Column("model", Text, nullable=False),
    Column("asked_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("id"),
    UniqueConstraint("conversation_id", "ordinal"),
    ForeignKeyConstraint(
        ["conversation_id", "organization_id"],
        ["conversations.id", "conversations.organization_id"],
        ondelete="CASCADE",
    ),
    CheckConstraint("status IN ('answered', 'not_found')", name="status_known"),
)
