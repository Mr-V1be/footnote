"""Plans, the usage ledger, invoices and payment notifications.

The ledger is append-only for the application: usage is never edited, only
booked. A version's character count lets a DOCX be counted in pages.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-04 00:30:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("subscriptions", "usage_ledger", "invoices", "payment_events")
TENANT_PREDICATE = "organization_id = NULLIF(current_setting('snoska.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.add_column("document_versions", sa.Column("character_count", sa.Integer(), nullable=True))
    op.create_table(
        "subscriptions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("plan_code", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("pending_plan_code", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("organization_id", name=op.f("pk_subscriptions")),
    )
    op.create_table(
        "usage_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reference", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_usage_ledger_quantity_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_ledger")),
    )
    op.create_index(
        "ix_usage_ledger_period", "usage_ledger", ["organization_id", "period_start", "metric"]
    )
    op.execute("CREATE SEQUENCE invoice_number_seq")
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Text(), nullable=False),
        sa.Column("plan_code", sa.Text(), nullable=False),
        sa.Column("amount_kopecks", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_id", sa.Text(), nullable=True),
        sa.Column("payment_url", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('open', 'paid', 'void')", name=op.f("ck_invoices_status_known")
        ),
        sa.CheckConstraint("amount_kopecks >= 0", name=op.f("ck_invoices_amount_non_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoices")),
        sa.UniqueConstraint("number", name=op.f("uq_invoices_number")),
    )
    op.create_table(
        "payment_events",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("provider", "event_id", name=op.f("pk_payment_events")),
    )
    app_role = op.get_context().config.attributes["app_role"]
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({TENANT_PREDICATE}) WITH CHECK ({TENANT_PREDICATE})"
        )
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON subscriptions TO {app_role}")
    op.execute(f"GRANT SELECT, INSERT ON usage_ledger TO {app_role}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON invoices TO {app_role}")
    op.execute(f"GRANT SELECT, INSERT ON payment_events TO {app_role}")
    op.execute(f"GRANT USAGE ON SEQUENCE invoice_number_seq TO {app_role}")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute("DROP SEQUENCE IF EXISTS invoice_number_seq")
    op.drop_column("document_versions", "character_count")
