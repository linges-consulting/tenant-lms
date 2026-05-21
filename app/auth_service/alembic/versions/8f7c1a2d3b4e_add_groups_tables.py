"""Add groups and group_memberships tables

Revision ID: 8f7c1a2d3b4e
Revises: 7c9e4f2a5b1d
Create Date: 2026-03-03 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f7c1a2d3b4e'
down_revision: Union[str, Sequence[str], None] = '7c9e4f2a5b1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create groups and group_memberships tables."""
    # Create groups table
    op.create_table(
        'groups',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uix_tenant_group_name'),
    )
    op.create_index(op.f('ix_groups_tenant_id'), 'groups', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_groups_name'), 'groups', ['name'], unique=False)

    # Create group_memberships table
    op.create_table(
        'group_memberships',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('group_id', 'user_id', name='uix_group_user'),
    )
    op.create_index(op.f('ix_group_memberships_group_id'), 'group_memberships', ['group_id'], unique=False)
    op.create_index(op.f('ix_group_memberships_user_id'), 'group_memberships', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema - remove groups and group_memberships tables."""
    op.drop_index(op.f('ix_group_memberships_user_id'), table_name='group_memberships')
    op.drop_index(op.f('ix_group_memberships_group_id'), table_name='group_memberships')
    op.drop_table('group_memberships')

    op.drop_index(op.f('ix_groups_name'), table_name='groups')
    op.drop_index(op.f('ix_groups_tenant_id'), table_name='groups')
    op.drop_table('groups')
