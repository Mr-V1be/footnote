from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)

from snoska.infrastructure.persistence.tables.metadata import metadata

organizations = Table(
    "organizations",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("alias", Text, nullable=False, unique=True),
    Column("name", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

workspaces = Table(
    "workspaces",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "organization_id",
        Uuid,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("slug", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("organization_id", "slug"),
    # Lets child tables reference (workspace, organization) together so a row
    # can never point to a workspace of another tenant.
    UniqueConstraint("id", "organization_id"),
    CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="slug_format"),
    CheckConstraint("char_length(name) BETWEEN 1 AND 200", name="name_length"),
)

user_profiles = Table(
    "user_profiles",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("email", Text, nullable=True),
    Column("display_name", Text, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
