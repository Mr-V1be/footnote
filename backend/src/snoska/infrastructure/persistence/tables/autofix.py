from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, Integer, PrimaryKeyConstraint, Table, Text, Uuid

from snoska.infrastructure.persistence.tables.metadata import metadata

version_changes = Table(
    "version_changes",
    metadata,
    Column("organization_id", Uuid, nullable=False),
    Column("version_id", Uuid, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("check_code", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("block_ordinal", Integer, nullable=True),
    Column("before", Text, nullable=False),
    Column("after", Text, nullable=False),
    Column("places", Integer, nullable=False),
    PrimaryKeyConstraint("version_id", "ordinal"),
    CheckConstraint(
        "kind IN ('margins', 'font_size', 'line_spacing', 'first_line_indent', 'text', 'format')",
        name="kind_known",
    ),
)
