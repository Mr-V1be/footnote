"""Initial schema: tenancy, documents, corpus, outbox.

Tenant tables are protected by row-level security keyed on the
transaction-local ``snoska.tenant_id`` setting; the runtime role does not own
them, so the policies always apply to it.

Revision ID: 0001
Revises:
Create Date: 2026-10-02 17:26:49.685634+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "workspaces",
    "documents",
    "document_versions",
    "document_structures",
    "document_blocks",
)
TENANT_PREDICATE = "organization_id = NULLIF(current_setting('snoska.tenant_id', true), '')::uuid"
INITIAL_SPACE = ("bge-m3", 1024)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "embedding_spaces",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.CheckConstraint("dimensions > 0", name=op.f("ck_embedding_spaces_dimensions_positive")),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_embedding_spaces")),
    )
    op.create_table(
        "legal_acts",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("short_title", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("adopted_on", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_legal_acts")),
    )
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("alias", name=op.f("uq_organizations_alias")),
    )
    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_name", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_messages")),
    )
    op.create_index(
        "ix_outbox_messages_due",
        "outbox_messages",
        ["available_at"],
        unique=False,
        postgresql_where=sa.text("dispatched_at IS NULL"),
    )
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_profiles")),
    )
    op.create_table(
        "corpus_editions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("act_code", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("source_revision", sa.Text(), nullable=False),
        sa.Column("amended_by", sa.Text(), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('ingested', 'active', 'superseded')",
            name=op.f("ck_corpus_editions_status_known"),
        ),
        sa.ForeignKeyConstraint(
            ["act_code"],
            ["legal_acts.code"],
            name=op.f("fk_corpus_editions_act_code_legal_acts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_corpus_editions")),
        sa.UniqueConstraint(
            "act_code",
            "content_sha256",
            name=op.f("uq_corpus_editions_act_code_content_sha256"),
        ),
    )
    op.create_index(
        "uq_corpus_editions_active_act",
        "corpus_editions",
        ["act_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "norm_embeddings",
        sa.Column("space_code", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["space_code"],
            ["embedding_spaces.code"],
            name=op.f("fk_norm_embeddings_space_code_embedding_spaces"),
        ),
        sa.PrimaryKeyConstraint("space_code", "content_sha256", name=op.f("pk_norm_embeddings")),
    )
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name=op.f("ck_workspaces_slug_format")
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200",
            name=op.f("ck_workspaces_name_length"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_workspaces_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
        sa.UniqueConstraint("id", "organization_id", name=op.f("uq_workspaces_id_organization_id")),
        sa.UniqueConstraint(
            "organization_id", "slug", name=op.f("uq_workspaces_organization_id_slug")
        ),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("kind_code", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latest_version_number", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 300",
            name=op.f("ck_documents_title_length"),
        ),
        sa.CheckConstraint(
            "latest_version_number >= 0",
            name=op.f("ck_documents_version_number_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "organization_id"],
            ["workspaces.id", "workspaces.organization_id"],
            name=op.f("fk_documents_workspace_id_organization_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("id", "organization_id", name=op.f("uq_documents_id_organization_id")),
    )
    op.create_index(
        "ix_documents_title_trgm",
        "documents",
        ["title"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_documents_workspace_recent",
        "documents",
        [
            "workspace_id",
            sa.literal_column("updated_at DESC"),
            sa.literal_column("id DESC"),
        ],
        unique=False,
    )
    op.create_table(
        "norm_units",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("number", sa.Text(), nullable=True),
        sa.Column("anchor", sa.Text(), nullable=False),
        sa.Column("citation", sa.Text(), nullable=False),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("repealed", sa.Boolean(), nullable=False),
        sa.Column("embedding_sha256", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "kind IN ('chapter', 'article', 'part', 'clause', 'subclause', 'paragraph')",
            name=op.f("ck_norm_units_kind_known"),
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["corpus_editions.id"],
            name=op.f("fk_norm_units_edition_id_corpus_editions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["norm_units.id"],
            name=op.f("fk_norm_units_parent_id_norm_units"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_norm_units")),
        sa.UniqueConstraint("edition_id", "anchor", name=op.f("uq_norm_units_edition_id_anchor")),
        sa.UniqueConstraint("edition_id", "ordinal", name=op.f("uq_norm_units_edition_id_ordinal")),
    )
    op.create_index(
        "ix_norm_units_embedding_sha256",
        "norm_units",
        ["embedding_sha256"],
        unique=False,
    )
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("blob_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("format_code", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("upload_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("parse_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("method", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("block_count", sa.Integer(), nullable=True),
        sa.Column("requisite_count", sa.Integer(), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "(status = 'failed') = (failure_code IS NOT NULL)",
            name=op.f("ck_document_versions_failure_iff_failed"),
        ),
        sa.CheckConstraint(
            "(status = 'parsed') = (method IS NOT NULL AND block_count IS NOT NULL)",
            name=op.f("ck_document_versions_summary_iff_parsed"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'parsing', 'parsed', 'failed')",
            name=op.f("ck_document_versions_status_known"),
        ),
        sa.CheckConstraint("number >= 1", name=op.f("ck_document_versions_number_positive")),
        sa.CheckConstraint("size_bytes >= 0", name=op.f("ck_document_versions_size_non_negative")),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["documents.id", "documents.organization_id"],
            name=op.f("fk_document_versions_document_id_organization_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_versions")),
        sa.UniqueConstraint(
            "document_id",
            "number",
            name=op.f("uq_document_versions_document_id_number"),
        ),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            name=op.f("uq_document_versions_id_organization_id"),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "upload_key",
            name=op.f("uq_document_versions_organization_id_upload_key"),
        ),
    )
    op.create_table(
        "document_structures",
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("layout", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("requisites", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id", "organization_id"],
            ["document_versions.id", "document_versions.organization_id"],
            name=op.f("fk_document_structures_version_id_organization_id_document_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("version_id", name=op.f("pk_document_structures")),
        sa.UniqueConstraint(
            "version_id",
            "organization_id",
            name=op.f("uq_document_structures_version_id_organization_id"),
        ),
    )
    op.create_table(
        "document_blocks",
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("attrs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "kind IN ('heading', 'paragraph', 'list_item', 'table')",
            name=op.f("ck_document_blocks_kind_known"),
        ),
        sa.ForeignKeyConstraint(
            ["version_id", "organization_id"],
            ["document_structures.version_id", "document_structures.organization_id"],
            name=op.f("fk_document_blocks_version_id_organization_id_document_structures"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("version_id", "ordinal", name=op.f("pk_document_blocks")),
    )

    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({TENANT_PREDICATE}) WITH CHECK ({TENANT_PREDICATE})"
        )

    op.execute(
        """
        CREATE FUNCTION notify_outbox() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM pg_notify('snoska_outbox', '');
            RETURN NULL;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER outbox_notify AFTER INSERT ON outbox_messages "
        "FOR EACH STATEMENT EXECUTE FUNCTION notify_outbox()"
    )

    code, dimensions = INITIAL_SPACE
    op.execute(
        sa.text(
            "INSERT INTO embedding_spaces (code, dimensions) VALUES (:code, :dimensions)"
        ).bindparams(code=code, dimensions=dimensions)
    )
    op.execute(
        f"CREATE INDEX ix_norm_embeddings_bge_m3_hnsw ON norm_embeddings "
        f"USING hnsw ((embedding::vector({dimensions})) vector_cosine_ops) "
        f"WHERE space_code = '{code}'"
    )

    app_role = op.get_context().config.attributes["app_role"]
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {app_role}")
    op.execute(f"REVOKE INSERT, UPDATE, DELETE ON embedding_spaces FROM {app_role}")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS outbox_notify ON outbox_messages")
    op.execute("DROP FUNCTION IF EXISTS notify_outbox()")
    op.drop_table("document_blocks")
    op.drop_table("document_structures")
    op.drop_table("document_versions")
    op.drop_index("ix_norm_units_embedding_sha256", table_name="norm_units")
    op.drop_table("norm_units")
    op.drop_index("ix_documents_workspace_recent", table_name="documents")
    op.drop_index(
        "ix_documents_title_trgm",
        table_name="documents",
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    op.drop_table("documents")
    op.drop_table("workspaces")
    op.drop_table("norm_embeddings")
    op.drop_index(
        "uq_corpus_editions_active_act",
        table_name="corpus_editions",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_table("corpus_editions")
    op.drop_table("user_profiles")
    op.drop_index(
        "ix_outbox_messages_due",
        table_name="outbox_messages",
        postgresql_where=sa.text("dispatched_at IS NULL"),
    )
    op.drop_table("outbox_messages")
    op.drop_table("organizations")
    op.drop_table("legal_acts")
    op.drop_table("embedding_spaces")
