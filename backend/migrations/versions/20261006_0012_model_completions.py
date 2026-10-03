"""Answers of the model kept by request, so a repeated request costs nothing.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-06 01:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_completions",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_model_completions")),
    )
    app_role = op.get_context().config.attributes["app_role"]
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON model_completions TO {app_role}")


def downgrade() -> None:
    op.drop_table("model_completions")
