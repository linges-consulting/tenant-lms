"""Add status enum to users table

Revision ID: 9d2e5f8c1a3b
Revises: 8f7c1a2d3b4e
Create Date: 2026-03-04 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d2e5f8c1a3b'
down_revision: Union[str, Sequence[str], None] = '8f7c1a2d3b4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add status column to users table."""
    # Create enum type
    status_enum = sa.Enum('PENDING', 'ACTIVE', 'DEACTIVATED', name='userstatus')
    status_enum.create(op.get_bind(), checkfirst=True)
    
    # Add column with default 'PENDING'
    op.add_column('users', sa.Column('status', status_enum, nullable=False, server_default='PENDING'))


def downgrade() -> None:
    """Downgrade schema - remove status column from users table."""
    op.drop_column('users', 'status')
    
    # Drop enum type
    status_enum = sa.Enum('PENDING', 'ACTIVE', 'DEACTIVATED', name='userstatus')
    status_enum.drop(op.get_bind(), checkfirst=True)
