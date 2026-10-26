"""Workspace roles and the audit log.

Workspaces can be restricted to listed members, each with a role of their
own there. The audit log records who did what in an organization; the
application may only append to it.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-04 00:10:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_PREDICATE = "organization_id = NULLIF(current_setting('footnote.tenant_id', true), '')::uuid"


def _isolate(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        f"USING ({TENANT_PREDICATE}) WITH CHECK ({TENANT_PREDICATE})"
    )


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("restricted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "workspace_members",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_code", sa.Text(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "organization_id"],
            ["workspaces.id", "workspaces.organization_id"],
            name=op.f("fk_workspace_members_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("workspace_id", "user_id", name=op.f("pk_workspace_members")),
    )
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_kind", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_label", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("target_label", sa.Text(), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.CheckConstraint(
            "actor_kind IN ('user', 'api_key', 'system')",
            name=op.f("ck_audit_events_actor_kind_known"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(
        "ix_audit_events_org_time", "audit_events", ["organization_id", "occurred_at", "id"]
    )
    _isolate("workspace_members")
    _isolate("audit_events")

    app_role = op.get_context().config.attributes["app_role"]
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON workspace_members TO {app_role}")
    # Append-only for the application: entries are never edited or removed.
    op.execute(f"GRANT SELECT, INSERT ON audit_events TO {app_role}")


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("workspace_members")
    op.drop_column("workspaces", "restricted")
