from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    false,
)

from footnote.infrastructure.persistence.tables.metadata import metadata

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
    # Only listed members (and owners) reach a restricted workspace.
    Column("restricted", Boolean, nullable=False, server_default=false()),
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
    # The interface language the person last used, for mail sent to them.
    Column("locale", Text, nullable=True),
    CheckConstraint("locale ~ '^[a-z]{2,3}$'", name="locale_is_a_language_code"),
)

workspace_members = Table(
    "workspace_members",
    metadata,
    Column("organization_id", Uuid, nullable=False),
    Column("workspace_id", Uuid, nullable=False),
    Column("user_id", Uuid, nullable=False),
    Column("role_code", Text, nullable=False),
    Column("added_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("workspace_id", "user_id"),
    ForeignKeyConstraint(
        ["workspace_id", "organization_id"],
        ["workspaces.id", "workspaces.organization_id"],
        ondelete="CASCADE",
    ),
)
