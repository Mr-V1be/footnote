"""Periodic tasks and the history of corpus edition checks (platform tables).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-04 01:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_states",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_task_states")),
    )
    op.create_table(
        "edition_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("act_code", sa.Text(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("revision", sa.Text(), nullable=True),
        sa.Column("edition_id", sa.Uuid(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "outcome IN ('unchanged', 'new_edition', 'failed')",
            name=op.f("ck_edition_checks_outcome_known"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_edition_checks")),
    )
    op.create_index("ix_edition_checks_time", "edition_checks", ["checked_at"])
    app_role = op.get_context().config.attributes["app_role"]
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON task_states TO {app_role}")
    op.execute(f"GRANT SELECT, INSERT ON edition_checks TO {app_role}")


def downgrade() -> None:
    op.drop_table("edition_checks")
    op.drop_table("task_states")
