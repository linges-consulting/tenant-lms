import asyncio
import bcrypt
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import uuid
from datetime import datetime, timezone
import os
import sys
import random
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import uuid
from datetime import datetime
import os
import sys

# Add app to path
sys.path.append(os.getcwd())

from app.core.config import settings
from app.core import security
# Import the package so package __init__ registers all models in correct order
from app.models import User, Group, GroupMembership, Tenant, TenantMembership, UserToken
from app.utils.provisioning import provision_default_certificate

# Unified password for all test accounts
TEST_PASSWORD = "Password123!"


async def get_or_create_tenant(conn, id: str, name: str, primary_color: str = "#000000"):
    # Use raw SQL to avoid ORM mapper initialization ordering problems
    now = datetime.utcnow()
    await conn.execute(
        text(
            """
            INSERT INTO tenants (id, name, is_active, primary_color, secondary_color, created_at, updated_at)
            VALUES (:id, :name, true, :primary_color, :secondary_color, :created_at, :updated_at)
            ON CONFLICT (id) DO UPDATE SET 
                name = EXCLUDED.name,
                primary_color = EXCLUDED.primary_color
            """
        ),
        {
            "id": id,
            "name": name,
            "primary_color": primary_color,
            "secondary_color": "#ffffff",
            "created_at": now,
            "updated_at": now,
        },
    )
    print(f"Ensured Tenant: {name} ({primary_color})")
    return id


async def create_user_with_roles(conn, email: str, full_name: str, username: str = None, is_sysadmin: bool = False, tenant_roles: list = None):
    """
    tenant_roles: list of dicts like {"tenant_id": "...", "m": bool, "c": bool}
    By default members created for a tenant are employees. Pass "e": False
    only if you explicitly want a non-employee membership.
    """
    if not username:
        username = email.split("@")[0]

    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(TEST_PASSWORD.encode(), bcrypt.gensalt()).decode()
    now = datetime.utcnow()
    # Randomly select from predefined avatar set (avatar1-10)
    avatar_url = f"avatar{random.randint(1, 10)}"

    # Insert or update user by email
    res = await conn.execute(
        text(
            """
            INSERT INTO users (id, email, username, hashed_password, full_name, avatar_url, is_sysadmin, is_active, status, created_at, updated_at)
            VALUES (:id, :email, :username, :hashed, :full_name, :avatar_url, :is_sysadmin, :active, :status, :created_at, :updated_at)
            ON CONFLICT (email) DO UPDATE SET
              hashed_password = EXCLUDED.hashed_password,
              full_name = EXCLUDED.full_name,
              avatar_url = EXCLUDED.avatar_url,
              username = EXCLUDED.username,
              is_sysadmin = EXCLUDED.is_sysadmin,
              is_active = EXCLUDED.is_active,
              status = EXCLUDED.status
            RETURNING id
            """
        ),
        {
            "id": user_id,
            "email": email,
            "username": username,
            "hashed": hashed,
            "full_name": full_name,
            "avatar_url": avatar_url,
            "is_sysadmin": is_sysadmin,
            "active": True,
            "status": "ACTIVE",
            "created_at": now,
            "updated_at": now,
        },
    )
    row = res.first()
    if row:
        uid = row[0]
    else:
        uid = user_id
    print(f"Ensured User: {email}")

    if tenant_roles:
        for tr in tenant_roles:
            # default to employee unless explicitly set to False
            is_employee = tr.get("e", True)
            membership_id = str(uuid.uuid4())
            await conn.execute(
                text(
                    """
                    INSERT INTO tenant_memberships (id, user_id, tenant_id, is_business_manager, is_training_creator, is_employee, is_active, status, created_at, updated_at)
                    VALUES (:id, :user_id, :tenant_id, :m, :c, :e, :active, :status, :created_at, :updated_at)
                    ON CONFLICT (user_id, tenant_id) DO UPDATE SET
                      is_business_manager = EXCLUDED.is_business_manager,
                      is_training_creator = EXCLUDED.is_training_creator,
                      is_employee = EXCLUDED.is_employee,
                      is_active = EXCLUDED.is_active,
                      status = EXCLUDED.status
                    """
                ),
                {
                    "id": membership_id,
                    "user_id": uid,
                    "tenant_id": tr["tenant_id"],
                    "m": tr.get("m", False),
                    "c": tr.get("c", False),
                    "e": is_employee,
                    "active": tr.get("is_active", True),
                    "status": tr.get("status", "ACTIVE"),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            print(f"  Ensured Membership for {email} in {tr['tenant_id']}")
    return uid


async def seed():
    engine = create_async_engine(settings.ASYNC_DB_URL)

    async def clear_tables(conn):
        tables = [
            "group_memberships",
            "user_tokens",
            "tenant_memberships",
            "groups",
            "tenants",
            "users",
        ]
        # TRUNCATE preserves schema while clearing data and resetting sequences
        for t in tables:
            # check existence using to_regclass to avoid aborting transaction on missing tables
            res = await conn.execute(text("SELECT to_regclass(:name)"), {"name": t})
            exists = res.scalar()
            if exists:
                await conn.execute(text(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE;"))
                print(f"Truncated table: {t}")
            else:
                print(f"Skipping truncate for {t} (does not exist)")

    async with engine.begin() as conn:
        # Clear existing application tables (truncate) to ensure a clean seed state
        await clear_tables(conn)

        # Create Tenants
        cp = await get_or_create_tenant(conn, "tenant-cp", "CellularPoint", primary_color="#1a73e8")
        vm = await get_or_create_tenant(conn, "tenant-vm", "ValueMobile", primary_color="#d93025")

        # Provision default certificates for initial tenants
        print("Provisioning default certificates...")
        await provision_default_certificate(tenant_id=cp, tenant_name="CellularPoint", brand_color="#1a73e8")
        await provision_default_certificate(tenant_id=vm, tenant_name="ValueMobile", brand_color="#d93025")

        # -------------------------------------------------------------------------
        # 1. Global Admin (Sysadmin)
        # -------------------------------------------------------------------------
        await create_user_with_roles(conn, "admin@cpvmtraining.com", "Global Admin", username="sysadmin", is_sysadmin=True)

        # 2. Single-Org Accounts
        # CellularPoint
        await create_user_with_roles(conn, "cp-manager@lms.com", "CP Manager", username="cp_manager",
                                     tenant_roles=[{"tenant_id": cp, "m": True}])
        await create_user_with_roles(conn, "cp-creator@lms.com", "CP Creator", username="cp_creator",
                                     tenant_roles=[{"tenant_id": cp, "c": True}])
        await create_user_with_roles(conn, "cp-employee@lms.com", "CP Employee", username="cp_employee",
                                     tenant_roles=[{"tenant_id": cp, "e": True}])
        await create_user_with_roles(conn, "cp-dual@lms.com", "CP Dual", username="cp_dual",
                                     tenant_roles=[{"tenant_id": cp, "m": True, "c": True, "e": True}])
        
        # ValueMobile
        await create_user_with_roles(conn, "vm-manager@lms.com", "VM Manager", username="vm_manager",
                                     tenant_roles=[{"tenant_id": vm, "m": True}])
        await create_user_with_roles(conn, "vm-creator@lms.com", "VM Creator", username="vm_creator",
                                     tenant_roles=[{"tenant_id": vm, "c": True}])
        await create_user_with_roles(conn, "vm-employee@lms.com", "VM Employee", username="vm_employee",
                                     tenant_roles=[{"tenant_id": vm, "e": True}])
        await create_user_with_roles(conn, "vm-dual@lms.com", "VM Dual", username="vm_dual",
                                     tenant_roles=[{"tenant_id": vm, "m": True, "c": True, "e": True}])

        # 3. Multi-Org Accounts
        await create_user_with_roles(conn, "cross-m-m@lms.com", "Cross M/M", username="cross_mm",
                                     tenant_roles=[{"tenant_id": cp, "m": True}, {"tenant_id": vm, "m": True}])
        await create_user_with_roles(conn, "cross-m-c@lms.com", "Cross M/C", username="cross_mc",
                                     tenant_roles=[{"tenant_id": cp, "m": True}, {"tenant_id": vm, "c": True}])
        await create_user_with_roles(conn, "cross-m-e@lms.com", "Cross M/E", username="cross_me",
                                     tenant_roles=[{"tenant_id": cp, "m": True}, {"tenant_id": vm, "e": True}])

        # 4. Pending User (for registration testing)
        await create_user_with_roles(conn, "pending-user@lms.com", "Pending User", username="pending_user",
                                     tenant_roles=[{"tenant_id": cp, "e": True, "status": "PENDING", "is_active": False}])

    print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())
