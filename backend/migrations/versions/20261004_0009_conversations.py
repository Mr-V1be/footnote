"""Questions to the corpus: conversations and their answered turns.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-04 00:50:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("conversations", "conversation_turns")
TENANT_PREDICATE = "organization_id = NULLIF(current_setting('footnote.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
        sa.UniqueConstraint(
            "id", "organization_id", name=op.f("uq_conversations_id_organization_id")
        ),
    )
    op.create_index(
        "ix_conversations_user", "conversations", ["organization_id", "user_id", "updated_at"]
    )
    op.create_table(
        "conversation_turns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('answered', 'not_found')",
            name=op.f("ck_conversation_turns_status_known"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            ["conversations.id", "conversations.organization_id"],
            name=op.f("fk_conversation_turns_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_turns")),
        sa.UniqueConstraint(
            "conversation_id", "ordinal", name=op.f("uq_conversation_turns_conversation_id_ordinal")
        ),
    )
    app_role = op.get_context().config.attributes["app_role"]
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({TENANT_PREDICATE}) WITH CHECK ({TENANT_PREDICATE})"
        )
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON conversations TO {app_role}")
    op.execute(f"GRANT SELECT, INSERT ON conversation_turns TO {app_role}")


def downgrade() -> None:
    op.drop_table("conversation_turns")
    op.drop_table("conversations")
