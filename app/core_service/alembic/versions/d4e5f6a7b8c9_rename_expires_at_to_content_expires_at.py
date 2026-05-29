"""rename trainings.expires_at to content_expires_at

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-29 12:00:00.000000

Separates training-level content expiry (creator-set, drives auto-archive)
from assignment-level due_date (manager-set, per-user deadline). The training
column is renamed for clarity; the assignments column already uses due_date.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('trainings', 'expires_at', new_column_name='content_expires_at')


def downgrade() -> None:
    op.alter_column('trainings', 'content_expires_at', new_column_name='expires_at')
