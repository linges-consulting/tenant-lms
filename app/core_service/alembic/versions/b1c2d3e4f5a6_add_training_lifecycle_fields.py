"""add_training_lifecycle_fields

Revision ID: b1c2d3e4f5a6
Revises: 0665db3ee96f
Create Date: 2026-05-14 15:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = '0665db3ee96f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trainings', sa.Column('is_ready', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('chapters', sa.Column('completion_mode', sa.String(length=20), nullable=False, server_default='can_continue'))
    op.create_table(
        'training_categories',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_training_categories_tenant_name'),
    )
    op.create_index('ix_training_categories_tenant_id', 'training_categories', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_training_categories_tenant_id', table_name='training_categories')
    op.drop_table('training_categories')
    op.drop_column('chapters', 'completion_mode')
    op.drop_column('trainings', 'is_ready')
