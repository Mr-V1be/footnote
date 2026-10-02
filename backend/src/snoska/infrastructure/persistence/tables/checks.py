from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
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

from snoska.infrastructure.persistence.tables.metadata import metadata

RUN_STATUSES = "('queued', 'running', 'completed', 'failed')"
RESULT_STATUSES = "('passed', 'violation', 'needs_review', 'not_applicable', 'error')"
REVIEW_STATUSES = "('open', 'accepted', 'rejected', 'fixed')"

check_runs = Table(
    "check_runs",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("organization_id", Uuid, nullable=False),
    Column("document_id", Uuid, nullable=False),
    Column("version_id", Uuid, nullable=False),
    Column("catalog_revision", Text, nullable=False),
    Column("requested_by", Uuid, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("status", Text, nullable=False),
    Column("total", Integer, nullable=False),
    Column("done", Integer, nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("failure_code", Text, nullable=True),
    Column("revision", Integer, nullable=False),
    ForeignKeyConstraint(
        ["version_id", "organization_id"],
        ["document_versions.id", "document_versions.organization_id"],
        ondelete="CASCADE",
    ),
    ForeignKeyConstraint(
        ["document_id", "organization_id"],
        ["documents.id", "documents.organization_id"],
        ondelete="CASCADE",
    ),
    UniqueConstraint("id", "organization_id"),
    CheckConstraint(f"status IN {RUN_STATUSES}", name="status_known"),
    CheckConstraint("total >= 0 AND done >= 0 AND done <= total", name="progress_in_range"),
    CheckConstraint("attempts >= 0", name="attempts_non_negative"),
    CheckConstraint("(status = 'failed') = (failure_code IS NOT NULL)", name="failure_iff_failed"),
    CheckConstraint(
        "(status IN ('completed', 'failed')) = (finished_at IS NOT NULL)",
        name="finished_iff_settled",
    ),
    Index("ix_check_runs_version_recent", "version_id", text("created_at DESC")),
    Index("ix_check_runs_document", "document_id"),
    # At most one run of a version is waiting or running at a time.
    Index(
        "uq_check_runs_pending_version",
        "version_id",
        unique=True,
        postgresql_where=text("status IN ('queued', 'running')"),
    ),
)

check_results = Table(
    "check_results",
    metadata,
    Column("run_id", Uuid, nullable=False),
    Column("organization_id", Uuid, nullable=False),
    Column("check_code", Text, nullable=False),
    Column("method", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("evidence", JSONB, nullable=False),
    Column("cited_act", Text, nullable=True),
    Column("cited_edition_id", Uuid, nullable=True),
    Column("cited_anchor", Text, nullable=True),
    Column("cited_citation", Text, nullable=True),
    Column("error_code", Text, nullable=True),
    Column("attempts", Integer, nullable=False),
    Column("duration_ms", Integer, nullable=False),
    Column("model", Text, nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("run_id", "check_code"),
    ForeignKeyConstraint(
        ["run_id", "organization_id"],
        ["check_runs.id", "check_runs.organization_id"],
        ondelete="CASCADE",
    ),
    CheckConstraint(f"status IN {RESULT_STATUSES}", name="status_known"),
    CheckConstraint("method IN ('deterministic', 'model')", name="method_known"),
    CheckConstraint("(status = 'error') = (error_code IS NOT NULL)", name="error_iff_failed"),
    CheckConstraint("attempts >= 1 AND duration_ms >= 0", name="metrics_non_negative"),
)

findings = Table(
    "findings",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("organization_id", Uuid, nullable=False),
    Column("run_id", Uuid, nullable=False),
    Column("check_code", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("severity", Text, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("title", Text, nullable=False),
    Column("detail", JSONB, nullable=False),
    Column("recommendation", Text, nullable=False),
    Column("norm_citation", Text, nullable=False),
    Column("norm_act", Text, nullable=True),
    Column("norm_edition_id", Uuid, nullable=True),
    Column("norm_anchor", Text, nullable=True),
    Column("block_ordinal", Integer, nullable=True),
    Column("span_start", Integer, nullable=True),
    Column("span_end", Integer, nullable=True),
    # Places a finding about the whole document covers, shown on request.
    Column("places", JSONB, nullable=False, server_default="[]"),
    Column("fingerprint", Text, nullable=False),
    Column("review", Text, nullable=False),
    Column("reviewed_by", Uuid, nullable=True),
    Column("reviewed_at", DateTime(timezone=True), nullable=True),
    Column("revision", Integer, nullable=False),
    ForeignKeyConstraint(
        ["run_id", "organization_id"],
        ["check_runs.id", "check_runs.organization_id"],
        ondelete="CASCADE",
    ),
    ForeignKeyConstraint(
        ["run_id", "check_code"],
        ["check_results.run_id", "check_results.check_code"],
        ondelete="CASCADE",
    ),
    UniqueConstraint("id", "organization_id"),
    UniqueConstraint("run_id", "ordinal"),
    CheckConstraint("kind IN ('violation', 'review')", name="kind_known"),
    CheckConstraint("severity IN ('critical', 'important', 'advice')", name="severity_known"),
    CheckConstraint(f"review IN {REVIEW_STATUSES}", name="review_known"),
    CheckConstraint(
        "(block_ordinal IS NULL AND span_start IS NULL AND span_end IS NULL) OR "
        "(block_ordinal >= 0 AND span_start >= 0 AND span_end > span_start)",
        name="location_complete",
    ),
    Index("ix_findings_fingerprint", "fingerprint"),
)

text_embeddings = Table(
    "text_embeddings",
    metadata,
    Column("organization_id", Uuid, nullable=False),
    Column("space_code", Text, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("embedding", Vector(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("organization_id", "space_code", "sha256"),
    ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    ForeignKeyConstraint(["space_code"], ["embedding_spaces.code"]),
)

# Channel the database notifies when a run is created or changes.
CHECK_RUNS_CHANNEL = "snoska_check_runs"
