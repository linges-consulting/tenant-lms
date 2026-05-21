"""add_template_id_to_trainings

Revision ID: 4f2d5e6a7b8c
Revises: f3e4d5c6b7a8
Create Date: 2026-03-30 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f2d5e6a7b8c'
down_revision: Union[str, Sequence[str], None] = 'f3e4d5c6b7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add template_id column to trainings table
    op.add_column('trainings', sa.Column('template_id', sa.String(), nullable=True))
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_trainings_template_id_certificate_templates',
        'trainings', 'certificate_templates',
        ['template_id'], ['id']
    )
    
    # Create index
    op.create_index(op.f('ix_trainings_template_id'), 'trainings', ['template_id'], unique=False)


def downgrade() -> None:
    # Drop index
    op.drop_index(op.f('ix_trainings_template_id'), table_name='trainings')
    
    # Drop foreign key constraint
    op.drop_constraint('fk_trainings_template_id_certificate_templates', 'trainings', type_='foreignkey')
    
    # Drop column
    op.drop_column('trainings', 'template_id')
