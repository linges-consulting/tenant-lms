"""make training category not null

Revision ID: 0665db3ee96f
Revises: a7a622543aab
Create Date: 2026-05-12 19:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0665db3ee96f'
down_revision: Union[str, Sequence[str], None] = 'a7a622543aab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # First, update any NULL values to a default
    op.execute("UPDATE trainings SET category = 'Uncategorized' WHERE category IS NULL")

    # Then alter the column to be NOT NULL
    op.alter_column('trainings', 'category',
               existing_type=sa.String(),
               nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('trainings', 'category',
               existing_type=sa.String(),
               nullable=True)
