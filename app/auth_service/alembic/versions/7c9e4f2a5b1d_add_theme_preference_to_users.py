"""Add theme_preference to users table

Revision ID: 7c9e4f2a5b1d
Revises: 612233d9490b
Create Date: 2026-03-03 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c9e4f2a5b1d'
down_revision: Union[str, Sequence[str], None] = '612233d9490b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add theme_preference column to users table."""
    op.add_column('users', sa.Column('theme_preference', sa.String(), nullable=False, server_default='system'))


def downgrade() -> None:
    """Downgrade schema - remove theme_preference column from users table."""
    op.drop_column('users', 'theme_preference')
