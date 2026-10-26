from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from footnote.infrastructure.persistence.tables.metadata import metadata

documents = Table(
    "documents",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("organization_id", Uuid, nullable=False),
    Column("workspace_id", Uuid, nullable=False),
    Column("title", Text, nullable=False),
    Column("kind_code", Text, nullable=False),
    Column("created_by", Uuid, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("latest_version_number", Integer, nullable=False),
    Column("revision", Integer, nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "organization_id"],
        ["workspaces.id", "workspaces.organization_id"],
        ondelete="CASCADE",
    ),
    UniqueConstraint("id", "organization_id"),
    CheckConstraint("latest_version_number >= 0", name="version_number_non_negative"),
    CheckConstraint("char_length(title) BETWEEN 1 AND 300", name="title_length"),
    Index(
        "ix_documents_workspace_recent",
        "workspace_id",
        text("updated_at DESC"),
        text("id DESC"),
    ),
    Index(
        "ix_documents_title_trgm",
        "title",
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    ),
)

PARSE_STATUSES = "('queued', 'parsing', 'parsed', 'failed')"

document_versions = Table(
    "document_versions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("organization_id", Uuid, nullable=False),
    Column("document_id", Uuid, nullable=False),
    Column("number", Integer, nullable=False),
    Column("blob_key", Text, nullable=False),
    Column("filename", Text, nullable=False),
    Column("format_code", Text, nullable=False),
    Column("media_type", Text, nullable=False),
    Column("size_bytes", BigInteger, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("uploaded_by", Uuid, nullable=False),
    Column("origin", Text, nullable=False, server_default="upload"),
    # The version an automatic correction was made from.
    Column("derived_from", Integer, nullable=True),
    Column("upload_key", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("status", Text, nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("parse_started_at", DateTime(timezone=True), nullable=True),
    Column("parsed_at", DateTime(timezone=True), nullable=True),
    Column("failure_code", Text, nullable=True),
    Column("method", Text, nullable=True),
    Column("page_count", Integer, nullable=True),
    Column("block_count", Integer, nullable=True),
    Column("character_count", Integer, nullable=True),
    Column("ocr_confidence", Float, nullable=True),
    ForeignKeyConstraint(
        ["document_id", "organization_id"],
        ["documents.id", "documents.organization_id"],
        ondelete="CASCADE",
    ),
    UniqueConstraint("document_id", "number"),
    UniqueConstraint("organization_id", "upload_key"),
    UniqueConstraint("id", "organization_id"),
    CheckConstraint(f"status IN {PARSE_STATUSES}", name="status_known"),
    CheckConstraint("number >= 1", name="number_positive"),
    CheckConstraint("size_bytes >= 0", name="size_non_negative"),
    CheckConstraint(
        "(status = 'parsed') = (method IS NOT NULL AND block_count IS NOT NULL)",
        name="summary_iff_parsed",
    ),
    CheckConstraint("(status = 'failed') = (failure_code IS NOT NULL)", name="failure_iff_failed"),
)

document_structures = Table(
    "document_structures",
    metadata,
    Column("version_id", Uuid, primary_key=True),
    Column("organization_id", Uuid, nullable=False),
    Column("layout", JSONB, nullable=False),
    ForeignKeyConstraint(
        ["version_id", "organization_id"],
        ["document_versions.id", "document_versions.organization_id"],
        ondelete="CASCADE",
    ),
    UniqueConstraint("version_id", "organization_id"),
)

document_blocks = Table(
    "document_blocks",
    metadata,
    Column("version_id", Uuid, nullable=False),
    Column("organization_id", Uuid, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("kind", Text, nullable=False),
    Column("text", Text, nullable=False),
    Column("level", Integer, nullable=True),
    Column("label", Text, nullable=True),
    Column("page", Integer, nullable=True),
    Column("attrs", JSONB, nullable=False),
    PrimaryKeyConstraint("version_id", "ordinal"),
    ForeignKeyConstraint(
        ["version_id", "organization_id"],
        ["document_structures.version_id", "document_structures.organization_id"],
        ondelete="CASCADE",
    ),
    CheckConstraint("kind IN ('heading', 'paragraph', 'list_item', 'table')", name="kind_known"),
)
