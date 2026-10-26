"""Checks: runs, results, findings and stored passage embeddings.

Every table belongs to a tenant and is protected by row-level security like
the document tables. A trigger tells listeners (the API's progress streams)
whenever a run is created or changes.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-02 21:17:44.893770+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("check_runs", "check_results", "findings", "text_embeddings")
TENANT_PREDICATE = "organization_id = NULLIF(current_setting('footnote.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "text_embeddings",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("space_code", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_text_embeddings_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space_code"],
            ["embedding_spaces.code"],
            name=op.f("fk_text_embeddings_space_code_embedding_spaces"),
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "space_code", "sha256", name=op.f("pk_text_embeddings")
        ),
    )
    op.create_table(
        "check_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_revision", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("done", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(status = 'failed') = (failure_code IS NOT NULL)",
            name=op.f("ck_check_runs_failure_iff_failed"),
        ),
        sa.CheckConstraint(
            "(status IN ('completed', 'failed')) = (finished_at IS NOT NULL)",
            name=op.f("ck_check_runs_finished_iff_settled"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name=op.f("ck_check_runs_status_known"),
        ),
        sa.CheckConstraint(
            "total >= 0 AND done >= 0 AND done <= total",
            name=op.f("ck_check_runs_progress_in_range"),
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_check_runs_attempts_non_negative")),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["documents.id", "documents.organization_id"],
            name=op.f("fk_check_runs_document_id_organization_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_id", "organization_id"],
            ["document_versions.id", "document_versions.organization_id"],
            name=op.f("fk_check_runs_version_id_organization_id_document_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_check_runs")),
        sa.UniqueConstraint("id", "organization_id", name=op.f("uq_check_runs_id_organization_id")),
    )
    op.create_index("ix_check_runs_document", "check_runs", ["document_id"], unique=False)
    op.create_index(
        "ix_check_runs_version_recent",
        "check_runs",
        ["version_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "uq_check_runs_pending_version",
        "check_runs",
        ["version_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_table(
        "check_results",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("check_code", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cited_act", sa.Text(), nullable=True),
        sa.Column("cited_edition_id", sa.Uuid(), nullable=True),
        sa.Column("cited_anchor", sa.Text(), nullable=True),
        sa.Column("cited_citation", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(status = 'error') = (error_code IS NOT NULL)",
            name=op.f("ck_check_results_error_iff_failed"),
        ),
        sa.CheckConstraint(
            "method IN ('deterministic', 'model')", name=op.f("ck_check_results_method_known")
        ),
        sa.CheckConstraint(
            "status IN ('passed', 'violation', 'needs_review', 'not_applicable', 'error')",
            name=op.f("ck_check_results_status_known"),
        ),
        sa.CheckConstraint(
            "attempts >= 1 AND duration_ms >= 0", name=op.f("ck_check_results_metrics_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "organization_id"],
            ["check_runs.id", "check_runs.organization_id"],
            name=op.f("fk_check_results_run_id_organization_id_check_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", "check_code", name=op.f("pk_check_results")),
    )
    op.create_table(
        "findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("check_code", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("norm_citation", sa.Text(), nullable=False),
        sa.Column("norm_act", sa.Text(), nullable=True),
        sa.Column("norm_edition_id", sa.Uuid(), nullable=True),
        sa.Column("norm_anchor", sa.Text(), nullable=True),
        sa.Column("block_ordinal", sa.Integer(), nullable=True),
        sa.Column("span_start", sa.Integer(), nullable=True),
        sa.Column("span_end", sa.Integer(), nullable=True),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("review", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint("kind IN ('violation', 'review')", name=op.f("ck_findings_kind_known")),
        sa.CheckConstraint(
            "review IN ('open', 'accepted', 'rejected', 'fixed')",
            name=op.f("ck_findings_review_known"),
        ),
        sa.CheckConstraint(
            "severity IN ('critical', 'important', 'advice')",
            name=op.f("ck_findings_severity_known"),
        ),
        sa.CheckConstraint(
            "(block_ordinal IS NULL AND span_start IS NULL AND span_end IS NULL) OR (block_ordinal >= 0 AND span_start >= 0 AND span_end > span_start)",
            name=op.f("ck_findings_location_complete"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "check_code"],
            ["check_results.run_id", "check_results.check_code"],
            name=op.f("fk_findings_run_id_check_code_check_results"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "organization_id"],
            ["check_runs.id", "check_runs.organization_id"],
            name=op.f("fk_findings_run_id_organization_id_check_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_findings")),
        sa.UniqueConstraint("id", "organization_id", name=op.f("uq_findings_id_organization_id")),
        sa.UniqueConstraint("run_id", "ordinal", name=op.f("uq_findings_run_id_ordinal")),
    )
    op.create_index("ix_findings_fingerprint", "findings", ["fingerprint"], unique=False)

    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({TENANT_PREDICATE}) WITH CHECK ({TENANT_PREDICATE})"
        )

    op.execute(
        """
        CREATE FUNCTION notify_check_run() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM pg_notify(
                'footnote_check_runs',
                json_build_object('organization_id', NEW.organization_id, 'run_id', NEW.id)::text
            );
            RETURN NULL;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER check_run_changed AFTER INSERT OR UPDATE ON check_runs "
        "FOR EACH ROW EXECUTE FUNCTION notify_check_run()"
    )

    app_role = op.get_context().config.attributes["app_role"]
    for table in TENANT_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {app_role}")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS check_run_changed ON check_runs")
    op.execute("DROP FUNCTION IF EXISTS notify_check_run()")
    op.drop_index("ix_findings_fingerprint", table_name="findings")
    op.drop_table("findings")
    op.drop_table("check_results")
    op.drop_index(
        "uq_check_runs_pending_version",
        table_name="check_runs",
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.drop_index("ix_check_runs_version_recent", table_name="check_runs")
    op.drop_index("ix_check_runs_document", table_name="check_runs")
    op.drop_table("check_runs")
    op.drop_table("text_embeddings")
