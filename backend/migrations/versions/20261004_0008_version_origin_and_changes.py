"""Versions made by the platform, and the journal of what they changed.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-04 00:40:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_PREDICATE = "organization_id = NULLIF(current_setting('footnote.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.add_column(
        "document_versions",
        sa.Column("origin", sa.Text(), nullable=False, server_default="upload"),
    )
    op.add_column("document_versions", sa.Column("derived_from", sa.Integer(), nullable=True))
    op.create_table(
        "version_changes",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("check_code", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("block_ordinal", sa.Integer(), nullable=True),
        sa.Column("before", sa.Text(), nullable=False),
        sa.Column("after", sa.Text(), nullable=False),
        sa.Column("places", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('format', 'text')", name=op.f("ck_version_changes_kind_known")
        ),
        sa.PrimaryKeyConstraint("version_id", "ordinal", name=op.f("pk_version_changes")),
    )
    op.execute("ALTER TABLE version_changes ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON version_changes "
        f"USING ({TENANT_PREDICATE}) WITH CHECK ({TENANT_PREDICATE})"
    )
    app_role = op.get_context().config.attributes["app_role"]
    op.execute(f"GRANT SELECT, INSERT ON version_changes TO {app_role}")


def downgrade() -> None:
    op.drop_table("version_changes")
    op.drop_column("document_versions", "derived_from")
    op.drop_column("document_versions", "origin")
