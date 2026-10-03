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
