"""Rename userstatus enum values to uppercase

Revision ID: a1b2c3d4e5f6
Revises: 4f4c47ed3ecc
Create Date: 2026-03-07 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '4f4c47ed3ecc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename userstatus enum values from lowercase to uppercase (idempotent)."""
    # Only rename if the lowercase label still exists (safe on both old and new DBs)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid
                       WHERE t.typname = 'userstatus' AND e.enumlabel = 'pending') THEN
                ALTER TYPE userstatus RENAME VALUE 'pending' TO 'PENDING';
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid
                       WHERE t.typname = 'userstatus' AND e.enumlabel = 'active') THEN
                ALTER TYPE userstatus RENAME VALUE 'active' TO 'ACTIVE';
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid
                       WHERE t.typname = 'userstatus' AND e.enumlabel = 'deactivated') THEN
                ALTER TYPE userstatus RENAME VALUE 'deactivated' TO 'DEACTIVATED';
            END IF;
        END $$;
    """)

    # Update any existing rows that may still have lowercase values
    op.execute("UPDATE users SET status = 'PENDING' WHERE status::text = 'pending'")
    op.execute("UPDATE users SET status = 'ACTIVE' WHERE status::text = 'active'")
    op.execute("UPDATE users SET status = 'DEACTIVATED' WHERE status::text = 'deactivated'")

    op.execute("UPDATE tenant_memberships SET status = 'PENDING' WHERE status::text = 'pending'")
    op.execute("UPDATE tenant_memberships SET status = 'ACTIVE' WHERE status::text = 'active'")
    op.execute("UPDATE tenant_memberships SET status = 'DEACTIVATED' WHERE status::text = 'deactivated'")

    # Update server defaults
    op.alter_column('users', 'status', server_default='PENDING')
    op.alter_column('tenant_memberships', 'status', server_default='ACTIVE')


def downgrade() -> None:
    """Rename userstatus enum values back to lowercase."""
    op.execute("ALTER TYPE userstatus RENAME VALUE 'PENDING' TO 'pending'")
    op.execute("ALTER TYPE userstatus RENAME VALUE 'ACTIVE' TO 'active'")
    op.execute("ALTER TYPE userstatus RENAME VALUE 'DEACTIVATED' TO 'deactivated'")

    op.execute("UPDATE users SET status = 'pending' WHERE status::text = 'PENDING'")
    op.execute("UPDATE users SET status = 'active' WHERE status::text = 'ACTIVE'")
    op.execute("UPDATE users SET status = 'deactivated' WHERE status::text = 'DEACTIVATED'")

    op.execute("UPDATE tenant_memberships SET status = 'pending' WHERE status::text = 'PENDING'")
    op.execute("UPDATE tenant_memberships SET status = 'active' WHERE status::text = 'ACTIVE'")
    op.execute("UPDATE tenant_memberships SET status = 'deactivated' WHERE status::text = 'DEACTIVATED'")

    op.alter_column('users', 'status', server_default='pending')
    op.alter_column('tenant_memberships', 'status', server_default='active')
