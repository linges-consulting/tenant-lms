"""rename_userstatus_DEACTIVATED_to_INACTIVE

Revision ID: 5a9fba37f31b
Revises: 8ef155527b59
Create Date: 2026-05-12 22:02:01.250038

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '5a9fba37f31b'
down_revision: Union[str, Sequence[str], None] = '8ef155527b59'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename UserStatus enum value DEACTIVATED → INACTIVE.

    Strategy (avoids the ADD VALUE / commit requirement):
    1. Drop server defaults that reference the enum type.
    2. Change column type to VARCHAR temporarily.
    3. Update DEACTIVATED rows to INACTIVE.
    4. Drop the old enum type.
    5. Create a new enum type with INACTIVE instead of DEACTIVATED.
    6. Cast columns back to the new enum type and restore defaults.
    """
    conn = op.get_bind()

    # Step 1: Drop server defaults (they depend on the enum type)
    conn.execute(text("ALTER TABLE users ALTER COLUMN status DROP DEFAULT"))
    conn.execute(text("ALTER TABLE tenant_memberships ALTER COLUMN status DROP DEFAULT"))

    # Step 2: Convert status columns to plain text
    conn.execute(text(
        "ALTER TABLE users "
        "ALTER COLUMN status TYPE VARCHAR(50) "
        "USING status::text"
    ))
    conn.execute(text(
        "ALTER TABLE tenant_memberships "
        "ALTER COLUMN status TYPE VARCHAR(50) "
        "USING status::text"
    ))

    # Step 3: Update the string values
    conn.execute(text("UPDATE users SET status = 'INACTIVE' WHERE status = 'DEACTIVATED'"))
    conn.execute(text("UPDATE tenant_memberships SET status = 'INACTIVE' WHERE status = 'DEACTIVATED'"))

    # Step 4: Drop the old enum type (no dependents now)
    conn.execute(text("DROP TYPE userstatus"))

    # Step 5: Create the new enum type with INACTIVE
    conn.execute(text("CREATE TYPE userstatus AS ENUM ('PENDING', 'ACTIVE', 'INACTIVE')"))

    # Step 6: Cast columns back to the new enum type and restore defaults
    conn.execute(text(
        "ALTER TABLE users "
        "ALTER COLUMN status TYPE userstatus "
        "USING status::userstatus"
    ))
    conn.execute(text("ALTER TABLE users ALTER COLUMN status SET DEFAULT 'PENDING'"))

    conn.execute(text(
        "ALTER TABLE tenant_memberships "
        "ALTER COLUMN status TYPE userstatus "
        "USING status::userstatus"
    ))
    conn.execute(text("ALTER TABLE tenant_memberships ALTER COLUMN status SET DEFAULT 'ACTIVE'"))


def downgrade() -> None:
    """Rename UserStatus enum value INACTIVE → DEACTIVATED (reverse)."""
    conn = op.get_bind()

    conn.execute(text("ALTER TABLE users ALTER COLUMN status DROP DEFAULT"))
    conn.execute(text("ALTER TABLE tenant_memberships ALTER COLUMN status DROP DEFAULT"))

    conn.execute(text(
        "ALTER TABLE users "
        "ALTER COLUMN status TYPE VARCHAR(50) "
        "USING status::text"
    ))
    conn.execute(text(
        "ALTER TABLE tenant_memberships "
        "ALTER COLUMN status TYPE VARCHAR(50) "
        "USING status::text"
    ))

    conn.execute(text("UPDATE users SET status = 'DEACTIVATED' WHERE status = 'INACTIVE'"))
    conn.execute(text("UPDATE tenant_memberships SET status = 'DEACTIVATED' WHERE status = 'INACTIVE'"))

    conn.execute(text("DROP TYPE userstatus"))
    conn.execute(text("CREATE TYPE userstatus AS ENUM ('PENDING', 'ACTIVE', 'DEACTIVATED')"))

    conn.execute(text(
        "ALTER TABLE users "
        "ALTER COLUMN status TYPE userstatus "
        "USING status::userstatus"
    ))
    conn.execute(text("ALTER TABLE users ALTER COLUMN status SET DEFAULT 'PENDING'"))

    conn.execute(text(
        "ALTER TABLE tenant_memberships "
        "ALTER COLUMN status TYPE userstatus "
        "USING status::userstatus"
    ))
    conn.execute(text("ALTER TABLE tenant_memberships ALTER COLUMN status SET DEFAULT 'ACTIVE'"))
