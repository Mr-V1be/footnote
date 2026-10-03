"""Journal lines of an automatic correction say what they measure.

A formatting change was "format"; it is now margins, font size, line spacing
or first-line indent, so the comparison shows its values with units. Lines
journaled as "format" stay valid.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-06 00:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = "'margins', 'font_size', 'line_spacing', 'first_line_indent', 'text', 'format'"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_version_changes_kind_known"), "version_changes", type_="check")
    op.create_check_constraint(
        op.f("ck_version_changes_kind_known"), "version_changes", f"kind IN ({KINDS})"
    )


def downgrade() -> None:
    op.execute("UPDATE version_changes SET kind = 'format' WHERE kind NOT IN ('format', 'text')")
    op.drop_constraint(op.f("ck_version_changes_kind_known"), "version_changes", type_="check")
    op.create_check_constraint(
        op.f("ck_version_changes_kind_known"), "version_changes", "kind IN ('format', 'text')"
    )
