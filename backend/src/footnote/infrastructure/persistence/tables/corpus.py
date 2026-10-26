from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
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

legal_acts = Table(
    "legal_acts",
    metadata,
    Column("code", Text, primary_key=True),
    Column("kind", Text, nullable=False),
    # Names in every interface language, by language code.
    Column("short_title", JSONB, nullable=False),
    Column("title", JSONB, nullable=False),
    Column("adopted_on", Date, nullable=False),
    CheckConstraint("short_title ? 'ru' AND title ? 'ru'", name="names_in_source_language"),
)

corpus_editions = Table(
    "corpus_editions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("act_code", Text, ForeignKey("legal_acts.code"), nullable=False),
    Column("source_code", Text, nullable=False),
    Column("source_revision", Text, nullable=False),
    Column("amended_by", Text, nullable=True),
    Column("content_sha256", String(64), nullable=False),
    Column("retrieved_at", DateTime(timezone=True), nullable=False),
    Column("status", Text, nullable=False),
    Column("activated_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint("act_code", "content_sha256"),
    CheckConstraint("status IN ('ingested', 'active', 'superseded')", name="status_known"),
    # At most one active edition per act.
    Index(
        "uq_corpus_editions_active_act",
        "act_code",
        unique=True,
        postgresql_where=text("status = 'active'"),
    ),
)

norm_units = Table(
    "norm_units",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "edition_id", Uuid, ForeignKey("corpus_editions.id", ondelete="CASCADE"), nullable=False
    ),
    Column("parent_id", Uuid, ForeignKey("norm_units.id", ondelete="CASCADE"), nullable=True),
    Column("ordinal", Integer, nullable=False),
    Column("depth", Integer, nullable=False),
    Column("kind", Text, nullable=False),
    Column("number", Text, nullable=True),
    Column("anchor", Text, nullable=False),
    Column("citation", Text, nullable=False),
    Column("heading", Text, nullable=True),
    Column("text", Text, nullable=False),
    Column("notes", JSONB, nullable=False),
    Column("repealed", Boolean, nullable=False),
    Column("embedding_sha256", String(64), nullable=True),
    UniqueConstraint("edition_id", "ordinal"),
    UniqueConstraint("edition_id", "anchor"),
    Index("ix_norm_units_embedding_sha256", "embedding_sha256"),
    CheckConstraint(
        "kind IN ('chapter', 'article', 'part', 'clause', 'subclause', 'paragraph')",
        name="kind_known",
    ),
)

embedding_spaces = Table(
    "embedding_spaces",
    metadata,
    Column("code", Text, primary_key=True),
    Column("dimensions", Integer, nullable=False),
    CheckConstraint("dimensions > 0", name="dimensions_positive"),
)

# Vectors are keyed by the hash of the embedded passage, so unchanged text is
# shared across editions. The column has no fixed dimension; every space gets
# a partial HNSW index over a cast to its dimension, created when the space is
# registered (`footnote corpus reindex`).
norm_embeddings = Table(
    "norm_embeddings",
    metadata,
    Column("space_code", Text, ForeignKey("embedding_spaces.code"), nullable=False),
    Column("content_sha256", String(64), nullable=False),
    Column("embedding", Vector(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("space_code", "content_sha256"),
)

# An edition is searchable in a space once every passage of it has a vector
# there. Search never sees an edition that is indexed only in part.
edition_indexes = Table(
    "edition_indexes",
    metadata,
    Column(
        "edition_id", Uuid, ForeignKey("corpus_editions.id", ondelete="CASCADE"), nullable=False
    ),
    Column(
        "space_code",
        Text,
        ForeignKey("embedding_spaces.code", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("ready_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("edition_id", "space_code"),
)
