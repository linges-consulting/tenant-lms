"""Add username to users table

Revision ID: 612233d9490b
Revises: 3b8b19ad9a70
Create Date: 2026-03-02 22:53:44.188581

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '612233d9490b'
down_revision: Union[str, Sequence[str], None] = '3b8b19ad9a70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Only add the `username` column and index to `users` (avoid recreating tables)
    op.add_column('users', sa.Column('username', sa.String(), nullable=True))
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    # Note: other table creation is handled in the initial migration


def downgrade() -> None:
    """Downgrade schema."""
    # Remove username column and its index
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_column('users', 'username')
