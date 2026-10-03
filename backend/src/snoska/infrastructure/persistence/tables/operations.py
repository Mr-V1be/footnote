from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, DateTime, Index, Table, Text, Uuid

from snoska.infrastructure.persistence.tables.metadata import metadata

# Platform tables: no tenant owns them, row-level security does not apply.

task_states = Table(
    "task_states",
    metadata,
    Column("name", Text, primary_key=True),
    Column("next_run_at", DateTime(timezone=True), nullable=False),
    Column("last_run_at", DateTime(timezone=True), nullable=True),
)

edition_checks = Table(
    "edition_checks",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("act_code", Text, nullable=False),
    Column("checked_at", DateTime(timezone=True), nullable=False),
    Column("outcome", Text, nullable=False),
    Column("revision", Text, nullable=True),
    Column("edition_id", Uuid, nullable=True),
    Column("error", Text, nullable=True),
    CheckConstraint("outcome IN ('unchanged', 'new_edition', 'failed')", name="outcome_known"),
    Index("ix_edition_checks_time", "checked_at"),
)

# Answers of the model by the hash of the request that produced them. A key
# is reached only by sending the very same text, so sharing it across
# organizations reveals nothing a requester does not already hold.
model_completions = Table(
    "model_completions",
    metadata,
    Column("key", Text, primary_key=True),
    Column("model", Text, nullable=False),
    Column("text", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
