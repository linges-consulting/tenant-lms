"""unique chapter sequence_order per training

Merges the two existing heads and:

1. Backfills duplicate `chapters.sequence_order` values so each live chapter
   has a unique value within its training. The frontend used to compute
   sequence_order per-module/per-orphan-bucket, so two chapters in different
   modules could land on the same number — which broke the previous-chapter
   gating check in `complete_chapter` (it picks one row non-deterministically).

2. Adds a partial UNIQUE index on (training_id, sequence_order) where
   deleted_at IS NULL so the duplicate state can't recur.

Revision ID: c2f3a4b5d6e7
Revises: b1c2d3e4f5a6, e1f2a3b4c5d6
Create Date: 2026-05-20 23:35:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2f3a4b5d6e7'
down_revision: Union[str, Sequence[str], None] = ('b1c2d3e4f5a6', 'e1f2a3b4c5d6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Backfill — renumber chapters per training so sequence_order is unique.
    # Done in Python rather than SQL so it works on both Postgres (prod) and
    # SQLite (tests) without dialect-specific UPDATE..FROM / window syntax.
    training_ids = [
        row[0]
        for row in conn.execute(sa.text(
            "SELECT DISTINCT training_id FROM chapters WHERE deleted_at IS NULL"
        )).fetchall()
    ]

    for tid in training_ids:
        rows = conn.execute(
            sa.text(
                "SELECT id FROM chapters "
                "WHERE training_id = :tid AND deleted_at IS NULL "
                "ORDER BY sequence_order, id"
            ),
            {"tid": tid},
        ).fetchall()

        # Two-phase rewrite to avoid colliding with the partial unique index we
        # are about to add (and any existing constraint hooked off sequence_order).
        # Phase 1: move every row to a high, distinct value.
        for i, (cid,) in enumerate(rows, start=1):
            conn.execute(
                sa.text("UPDATE chapters SET sequence_order = :seq WHERE id = :cid"),
                {"seq": 1_000_000 + i, "cid": cid},
            )
        # Phase 2: assign the final 1..N ordering.
        for i, (cid,) in enumerate(rows, start=1):
            conn.execute(
                sa.text("UPDATE chapters SET sequence_order = :seq WHERE id = :cid"),
                {"seq": i, "cid": cid},
            )

    # 2. Partial unique index — covers Postgres (prod) and SQLite (tests).
    op.create_index(
        'uq_chapters_training_seq_live',
        'chapters',
        ['training_id', 'sequence_order'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
        sqlite_where=sa.text('deleted_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_chapters_training_seq_live', table_name='chapters')
    # The backfill itself is not reversed — historical duplicate state is not
    # something we'd want to re-introduce, and the original values are lost.
