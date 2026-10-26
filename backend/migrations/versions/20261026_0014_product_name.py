"""The product's name in the database: the tenant setting and the channels.

Row-level security reads the tenant from the transaction-local setting
``footnote.tenant_id``, and the triggers notify ``footnote_outbox`` and
``footnote_check_runs``. A database created under the product's former name
(``snoska``) has the former names in its policies and notifying functions;
this revision rewrites them. A database created by the current revisions
already has the new names, and nothing changes there.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-26 06:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class Names(NamedTuple):
    tenant_setting: str
    outbox_channel: str
    check_runs_channel: str


CURRENT = Names("footnote.tenant_id", "footnote_outbox", "footnote_check_runs")
FORMER = Names("snoska.tenant_id", "snoska_outbox", "snoska_check_runs")


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _rewrite_policies(old: str, new: str) -> None:
    """Every policy of the schema that reads the tenant setting by its old
    name reads it by the new one; the rest of each expression is kept as
    PostgreSQL stores it."""
    bind = op.get_bind()
    quote = bind.dialect.identifier_preparer.quote
    old_literal, new_literal = _literal(old), _literal(new)
    policies = bind.execute(
        sa.text(
            "SELECT tablename, policyname, qual, with_check FROM pg_policies "
            "WHERE schemaname = current_schema() "
            "AND (strpos(qual, :old) > 0 OR strpos(with_check, :old) > 0)"
        ),
        {"old": old_literal},
    ).all()
    for table, policy, using, check in policies:
        clauses = []
        if using is not None:
            clauses.append(f"USING ({using.replace(old_literal, new_literal)})")
        if check is not None:
            clauses.append(f"WITH CHECK ({check.replace(old_literal, new_literal)})")
        op.execute(f"ALTER POLICY {quote(policy)} ON {quote(table)} {' '.join(clauses)}")


def _notify_functions(names: Names) -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION notify_outbox() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM pg_notify({_literal(names.outbox_channel)}, '');
            RETURN NULL;
        END
        $$
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION notify_check_run() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM pg_notify(
                {_literal(names.check_runs_channel)},
                json_build_object('organization_id', NEW.organization_id, 'run_id', NEW.id)::text
            );
            RETURN NULL;
        END
        $$
        """
    )


def upgrade() -> None:
    _rewrite_policies(FORMER.tenant_setting, CURRENT.tenant_setting)
    _notify_functions(CURRENT)


def downgrade() -> None:
    _rewrite_policies(CURRENT.tenant_setting, FORMER.tenant_setting)
    _notify_functions(FORMER)
