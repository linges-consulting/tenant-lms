"""add_certificate_id_to_enrollments

Revision ID: f4a5b6c7d8e9
Revises: 4f2d5e6a7b8c
Create Date: 2026-04-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, Sequence[str], None] = '4f2d5e6a7b8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add certificate_id column to enrollments table
    op.add_column('enrollments', sa.Column('certificate_id', sa.String(), nullable=True))
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_enrollments_certificate_id_certificates',
        'enrollments', 'certificates',
        ['certificate_id'], ['id']
    )
    
    # Create index
    op.create_index(op.f('ix_enrollments_certificate_id'), 'enrollments', ['certificate_id'], unique=False)


def downgrade() -> None:
    # Drop index
    op.drop_index(op.f('ix_enrollments_certificate_id'), table_name='enrollments')
    
    # Drop foreign key constraint
    op.drop_constraint('fk_enrollments_certificate_id_certificates', 'enrollments', type_='foreignkey')
    
    # Drop column
    op.drop_column('enrollments', 'certificate_id')
