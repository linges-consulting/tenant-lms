#!/usr/bin/env python3
"""
LMS Database Management Script
================================
Single source-of-truth for database wipe and seeding.
Focuses on cross-service database initialization.

Note: Runs correctly inside the 'auth-service' container.
Always delegate migrations to individual services (e.g. 'docker compose exec service alembic upgrade head')
before running this script with --seed.

Usage
-----
  python3 reset_database.py --clear-db       # WIPE all microservice databases
  python3 reset_database.py --seed           # SEED all microservice databases
  python3 reset_database.py --seed --sysadmin-only  # SEED ONLY sysadmin user
  python3 reset_database.py --clear-db --seed --yes  # Full RESET + SEED

Flags
-----
  --clear-db       Drop and recreate the public schema (destructive!)
  --seed           Insert fixture/seed data from seed_data.json
  --sysadmin-only  When seeding, only create the global sysadmin user (skips tenants/trainings)
  --yes / -y       Skip the interactive confirmation prompt
"""

import asyncio
import os
import random
import sys
import uuid
import json
from datetime import datetime
from pathlib import Path

import argparse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncConnection

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
DB_USER     = os.getenv("POSTGRES_USER", "lms_user")
DB_PASS     = os.getenv("POSTGRES_PASSWORD", "lms_pass")

def _resolve_docker_host() -> bool:
    try:
        import socket
        socket.gethostbyname("postgres")
        return True
    except OSError:
        return False

IN_DOCKER = _resolve_docker_host()
DB_HOST   = "postgres" if IN_DOCKER else "localhost"
DB_PORT   = "5432"     if IN_DOCKER else "5433"

SERVICES = {
    "auth":         f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/auth_db",
    "core":         f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/core_db",
    "notification": f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/notification_db",
}

# Override from env if present
for s in SERVICES:
    # Check both {SERVICE}_DATABASE_URL and {SERVICE}_DB_URL
    # For notification, also allow NOTIF_DB_URL
    names = [f"{s.upper()}_DATABASE_URL", f"{s.upper()}_DB_URL"]
    if s == "notification":
        names.append("NOTIF_DB_URL")
    
    for name in names:
        val = os.getenv(name)
        if val:
            SERVICES[s] = val
            break

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_password_hash(password: str) -> str:
    try:
        from passlib.context import CryptContext
        ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return ctx.hash(password)
    except ImportError:
        return password

def load_seed_data():
    seed_file = Path(__file__).parent / "seed_data.json"
    if not seed_file.exists():
        print(f"❌ seed_data.json not found at {seed_file}")
        return None
    try:
        with open(seed_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading seed_data.json: {e}")
        return None

async def _check_tables_exist(conn: AsyncConnection, tables: list) -> bool:
    """Check if all listed tables exist in the public schema."""
    for table in tables:
        result = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t)"
        ), {"t": table})
        if not result.scalar():
            return False
    return True

# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

async def clear_database(conn: AsyncConnection, service: str) -> None:
    print(f"  [CLEAR] Wiping {service} schema...")
    await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
    await conn.execute(text("CREATE SCHEMA public"))
    await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    await conn.execute(text(f"GRANT ALL ON SCHEMA public TO {DB_USER}"))
    await conn.commit()
    print(f"  ✓  {service} wiped.")

async def seed_auth(conn: AsyncConnection, data: dict, sysadmin_only: bool = False) -> None:
    print(f"[AUTH] Seeding{' (SYSADMIN ONLY)' if sysadmin_only else ''}...")
    
    # Pre-check tables
    required_tables = ["users"] if sysadmin_only else ["users", "tenants", "tenant_memberships"]
    if not await _check_tables_exist(conn, required_tables):
        print(f"  ⚠️  Skipping Auth seed: Required tables {required_tables} missing. Run migrations first!")
        return

    hashed = get_password_hash("Password123!")
    now = datetime.utcnow()

    # Tenants
    if not sysadmin_only:
        for tenant in data.get("tenants", []):
            await conn.execute(text(
                "INSERT INTO tenants (id, name, is_active, primary_color, secondary_color, created_at, updated_at) "
                "VALUES (:id, :name, true, :pc, :sc, :now, :now) ON CONFLICT (id) DO NOTHING"
            ), {
                "id": tenant["id"],
                "name": tenant["name"],
                "pc": tenant["primary_color"],
                "sc": tenant["secondary_color"],
                "now": now
            })

    # Users and memberships
    for user_data in data.get("users", []):
        email = user_data["email"]
        is_sysadmin = user_data.get("is_sysadmin", False)

        if sysadmin_only and not is_sysadmin:
            continue
        
        # Add User
        uid = str(uuid.uuid4())
        username = user_data.get("username") or email.split("@")[0]
        full_name = user_data.get("full_name") or user_data.get("name")
        avatar = f"avatar{random.randint(1, 10)}"
        
        await conn.execute(text(
            "INSERT INTO users (id, email, username, hashed_password, full_name, avatar_url, "
            "is_sysadmin, is_active, theme_preference, status, created_at, updated_at) "
            "VALUES (:id, :e, :u, :pw, :n, :avatar, :sys, :active, :theme, :status, :now, :now) "
            "ON CONFLICT (email) DO UPDATE SET "
            "hashed_password = EXCLUDED.hashed_password, "
            "username = EXCLUDED.username, "
            "full_name = EXCLUDED.full_name, "
            "is_sysadmin = EXCLUDED.is_sysadmin, "
            "is_active = EXCLUDED.is_active, "
            "status = EXCLUDED.status, "
            "updated_at = EXCLUDED.updated_at"
        ), {
            "id": uid,
            "e": email,
            "u": username,
            "pw": hashed,
            "n": full_name,
            "avatar": avatar,
            "sys": is_sysadmin,
            "active": user_data.get("is_active", True),
            "theme": user_data.get("theme_preference", "system"),
            "status": user_data.get("status", "ACTIVE" if user_data.get("is_active", True) else "DEACTIVATED"),
            "now": now
        })

        # Get UID if it already existed
        res = await conn.execute(text("SELECT id FROM users WHERE email = :e"), {"e": email})
        uid = res.scalar()

        # Handle Membership
        tenant_id = user_data.get("tenant_id")
        if tenant_id:
            roles = user_data.get("roles", "e")
            mid = str(uuid.uuid4())
            await conn.execute(text(
                "INSERT INTO tenant_memberships "
                "(id, user_id, tenant_id, is_business_manager, is_training_creator, is_employee, "
                "is_active, status, created_at, updated_at) "
                "VALUES (:id, :uid, :tid, :m, :c, :e, :active, :status, :now, :now) "
                "ON CONFLICT (user_id, tenant_id) DO UPDATE SET "
                "is_business_manager = EXCLUDED.is_business_manager, "
                "is_training_creator = EXCLUDED.is_training_creator, "
                "is_employee = EXCLUDED.is_employee, "
                "is_active = EXCLUDED.is_active, "
                "status = EXCLUDED.status, "
                "updated_at = EXCLUDED.updated_at"
            ), {
                "id": mid,
                "uid": uid,
                "tid": tenant_id,
                "m": "m" in roles,
                "c": "c" in roles,
                "e": "e" in roles or not roles,
                "active": user_data.get("is_active", True),
                "status": "ACTIVE" if user_data.get("is_active", True) else "DEACTIVATED",
                "now": now
            })

    print("  ✓  Auth data seeded.")

async def seed_core(conn: AsyncConnection, data: dict) -> None:
    print("[CORE] Seeding...")
    
    # Pre-check tables
    if not await _check_tables_exist(conn, ["trainings"]):
        print("  ⚠️  Skipping Core seed: 'trainings' table missing. Run migrations first!")
        return

    now = datetime.utcnow()
    for training in data.get("trainings", []):
        await conn.execute(text(
            "INSERT INTO trainings (id, tenant_id, title, category, duration, "
            "is_published, is_active, version, requires_certificate, created_at, updated_at) "
            "VALUES (:id, :tenant, :title, :cat, :dur, true, true, 1, true, :now, :now) "
            "ON CONFLICT (id) DO UPDATE SET "
            "title = EXCLUDED.title, "
            "category = EXCLUDED.category, "
            "duration = EXCLUDED.duration, "
            "updated_at = EXCLUDED.updated_at"
        ), {
            "id": training["id"],
            "tenant": training["tenant_id"],
            "title": training["title"],
            "cat": training["category"],
            "dur": training["duration"],
            "now": now
        })
    print("  ✓  Core data seeded.")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear-db", action="store_true")
    parser.add_argument("--seed",     action="store_true")
    parser.add_argument("--sysadmin-only", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true")
    args = parser.parse_args()

    if (args.clear_db or args.seed) and not args.yes:
        confirm = input("⚠️  Destructive operation. Type 'yes' to proceed: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            return

    if args.clear_db:
        print("\n━━━ Clearing Databases ━━━")
        for service, url in SERVICES.items():
            engine = create_async_engine(url)
            async with engine.begin() as conn:
                await clear_database(conn, service)
            await engine.dispose()

    if args.seed:
        data = load_seed_data()
        if not data:
            print("❌ Seeding failed: No data loaded.")
            sys.exit(1)

        print("\n━━━ Seeding Databases ━━━")
        auth_engine  = create_async_engine(SERVICES["auth"])
        async with auth_engine.begin() as conn:
            await seed_auth(conn, data, sysadmin_only=args.sysadmin_only)
        
        if not args.sysadmin_only:
            core_engine  = create_async_engine(SERVICES["core"])
            async with core_engine.begin() as conn:
                await seed_core(conn, data)
            await core_engine.dispose()

        await auth_engine.dispose()
        print("\n✅ Seeding complete (admin@cpvmtraining.com / Password123!)")

if __name__ == "__main__":
    asyncio.run(main())
