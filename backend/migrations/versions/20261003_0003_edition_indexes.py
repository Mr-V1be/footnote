"""Edition indexes: readiness of an edition for search, per embedding space.

Embedding spaces come from configuration now (model and vector size of the
external embedding API) and are registered with their index by
``footnote corpus reindex``. An edition is served as soon as it is ingested;
it is searchable in a space once all its passages are embedded there.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-03 00:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "edition_indexes",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("space_code", sa.Text(), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["corpus_editions.id"],
            name=op.f("fk_edition_indexes_edition_id_corpus_editions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space_code"],
            ["embedding_spaces.code"],
            name=op.f("fk_edition_indexes_space_code_embedding_spaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("edition_id", "space_code", name=op.f("pk_edition_indexes")),
    )
    # Editions activated under the old rule were activated only once fully
    # embedded in the space of that time: they are indexed there.
    op.execute(
        """
        INSERT INTO edition_indexes (edition_id, space_code, ready_at)
        SELECT e.id, s.code, coalesce(e.activated_at, e.retrieved_at)
        FROM corpus_editions e CROSS JOIN embedding_spaces s
        WHERE e.status = 'active'
          AND NOT EXISTS (
              SELECT 1 FROM norm_units u
              WHERE u.edition_id = e.id AND u.embedding_sha256 IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM norm_embeddings n
                    WHERE n.space_code = s.code AND n.content_sha256 = u.embedding_sha256
                )
          )
        """
    )
    # The first migration seeded a space for a local model; spaces are now
    # registered from configuration. Where it holds no vectors, it goes.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM norm_embeddings WHERE space_code = 'bge-m3') THEN
                DROP INDEX IF EXISTS ix_norm_embeddings_bge_m3_hnsw;
                DELETE FROM edition_indexes WHERE space_code = 'bge-m3';
                DELETE FROM embedding_spaces WHERE code = 'bge-m3';
            END IF;
        END
        $$
        """
    )
    app_role = op.get_context().config.attributes["app_role"]
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON edition_indexes TO {app_role}")


def downgrade() -> None:
    op.drop_table("edition_indexes")
