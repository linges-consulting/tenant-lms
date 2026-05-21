"""add is_default to certificate_templates

Revision ID: e1f2a3b4c5d6
Revises: a7a622543aab
Create Date: 2026-05-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'a7a622543aab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'certificate_templates',
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false')
    )
    op.create_index('ix_certificate_templates_is_default', 'certificate_templates', ['is_default'])


def downgrade() -> None:
    op.drop_index('ix_certificate_templates_is_default', table_name='certificate_templates')
    op.drop_column('certificate_templates', 'is_default')
