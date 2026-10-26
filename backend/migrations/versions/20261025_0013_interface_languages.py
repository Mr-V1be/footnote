"""Interface languages: texts kept in every language, and a person's language.

What a finding, a check result, an answer's footnote or an act's name tells
a reader becomes a JSON object of wordings by language code. Rows written
before keep their Russian wording under "ru", the source language; the other
languages appear when the checks run again (`footnote checks recheck`) and the
acts are synced (`footnote corpus sync`). A person's interface language, as
last seen by the API, is kept for the mail sent to them.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-25 12:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE = "ru"
TEXT_COLUMNS = (
    ("legal_acts", "short_title"),
    ("legal_acts", "title"),
    ("check_results", "cited_citation"),
    ("findings", "title"),
    ("findings", "recommendation"),
    ("findings", "norm_citation"),
)


def _to_wordings(table: str, column: str) -> None:
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN {column} TYPE jsonb "
        f"USING CASE WHEN {column} IS NULL THEN NULL "
        f"ELSE jsonb_build_object('{SOURCE}', {column}) END"
    )


def _to_text(table: str, column: str) -> None:
    op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE text USING {column} ->> '{SOURCE}'")


def upgrade() -> None:
    for table, column in TEXT_COLUMNS:
        _to_wordings(table, column)
    # A model's explanation ({"text": "…"}) and an answer's footnote citations.
    op.execute(
        "UPDATE findings SET detail = jsonb_build_object('text', "
        f"jsonb_build_object('{SOURCE}', detail ->> 'text')) "
        "WHERE jsonb_typeof(detail -> 'text') = 'string'"
    )
    op.execute(
        "UPDATE conversation_turns SET citations = ("
        "SELECT jsonb_agg(item || jsonb_build_object('citation', "
        f"jsonb_build_object('{SOURCE}', item ->> 'citation')) ORDER BY position) "
        "FROM jsonb_array_elements(citations) WITH ORDINALITY AS items(item, position)) "
        "WHERE jsonb_array_length(citations) > 0"
    )
    op.create_check_constraint(
        op.f("ck_legal_acts_names_in_source_language"),
        "legal_acts",
        f"short_title ? '{SOURCE}' AND title ? '{SOURCE}'",
    )
    op.create_check_constraint(
        op.f("ck_findings_texts_in_source_language"),
        "findings",
        f"title ? '{SOURCE}' AND recommendation ? '{SOURCE}' AND norm_citation ? '{SOURCE}'",
    )
    op.add_column("user_profiles", sa.Column("locale", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_user_profiles_locale_is_a_language_code"),
        "user_profiles",
        "locale ~ '^[a-z]{2,3}$'",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_user_profiles_locale_is_a_language_code"), "user_profiles")
    op.drop_column("user_profiles", "locale")
    op.drop_constraint(op.f("ck_findings_texts_in_source_language"), "findings")
    op.drop_constraint(op.f("ck_legal_acts_names_in_source_language"), "legal_acts")
    op.execute(
        "UPDATE conversation_turns SET citations = ("
        "SELECT jsonb_agg(item || jsonb_build_object('citation', "
        f"item -> 'citation' ->> '{SOURCE}') ORDER BY position) "
        "FROM jsonb_array_elements(citations) WITH ORDINALITY AS items(item, position)) "
        "WHERE jsonb_array_length(citations) > 0"
    )
    op.execute(
        "UPDATE findings SET detail = jsonb_build_object('text', "
        f"detail -> 'text' ->> '{SOURCE}') "
        "WHERE jsonb_typeof(detail -> 'text') = 'object'"
    )
    for table, column in TEXT_COLUMNS:
        _to_text(table, column)
