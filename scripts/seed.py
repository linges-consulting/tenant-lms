#!/usr/bin/env python3
"""
CustomLMS seed tool.

Modes:
  admin-only  Clear all data and insert the sysadmin user only.
              Use this to reset a dev/prod environment to a clean baseline.

  mock        Clear all data and populate from seed_config.json.
              Creates tenants, users, groups, certificate templates, and trainings.

Usage (local dev — Docker must be running):
  python scripts/seed.py --mode admin-only
  python scripts/seed.py --mode mock
  python scripts/seed.py --mode mock --config scripts/seed_config.json

DB credentials are read from the project root .env file automatically.
Individual overrides (in priority order):
  --auth-db-url / --core-db-url    CLI flags (highest priority)
  AUTH_DB_URL / CORE_DB_URL        exported shell env vars
  POSTGRES_USER / POSTGRES_PASSWORD from .env (assembled into URL)
  Built-in fallback: lms_user / lms_pass @ localhost:5433

Inside Docker (services must be up):
  docker compose exec auth-service python /scripts/seed.py --mode mock \
    --auth-db-url postgresql+asyncpg://lms_user:lms_pass@postgres/auth_db \
    --core-db-url postgresql+asyncpg://lms_user:lms_pass@postgres/core_db
"""
import argparse
import asyncio
import json
import os
import random
import sys
import uuid
from datetime import datetime
from pathlib import Path

import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# .env loader — no python-dotenv dependency required
# ---------------------------------------------------------------------------

def _load_dotenv(env_path: Path) -> None:
    """Parse KEY=VALUE lines from a .env file into os.environ.
    Existing env vars take priority (shell exports win over .env)."""
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, raw_val = line.partition("=")
            key = key.strip()
            # Strip surrounding quotes if present
            val = raw_val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


# Load project root .env before anything else reads os.environ
_load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PASSWORD = "Password123!"

AUTH_TABLES = [
    "group_memberships",
    "user_tokens",
    "tenant_memberships",
    "groups",
    "tenants",
    "users",
]

CORE_TABLES = [
    "quiz_attempts",
    "certificates",
    "training_history",
    "progress",
    "enrollments",
    "lessons",
    "chapters",
    "modules",
    "trainings",
    "certificate_templates",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.utcnow()


def _ensure_asyncpg(url: str) -> str:
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _certificate_html(tenant_name: str, brand_color: str) -> str:
    """Inline landscape certificate template (mirrors provisioning.py)."""
    color = brand_color or "#1e293b"
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  @page {{ size: A4 landscape; margin: 0; }}
  body {{ margin: 0; padding: 0; font-family: 'Helvetica', 'Arial', sans-serif; color: #1e293b; }}
  .cert {{ width: 297mm; height: 210mm; padding: 20mm; box-sizing: border-box; background: #fff; position: relative; overflow: hidden; }}
  .border-outer {{ position: absolute; top: 10mm; bottom: 10mm; left: 10mm; right: 10mm; border: 2mm solid {color}; }}
  .border-inner {{ position: absolute; top: 14mm; bottom: 14mm; left: 14mm; right: 14mm; border: 0.5mm solid {color}; padding: 15mm; text-align: center; display: flex; flex-direction: column; justify-content: center; }}
  .corner {{ position: absolute; width: 30mm; height: 30mm; background: {color}; opacity: .1; }}
  .tl {{ top: 0; left: 0; border-bottom-right-radius: 100%; }}
  .br {{ bottom: 0; right: 0; border-top-left-radius: 100%; }}
  .header {{ font-size: 18pt; font-weight: bold; color: {color}; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 10mm; }}
  .title {{ font-size: 42pt; font-family: Georgia, serif; margin-bottom: 5mm; color: #0f172a; }}
  .subtitle {{ font-size: 16pt; font-style: italic; color: #64748b; margin-bottom: 20mm; }}
  .name {{ font-size: 32pt; font-weight: bold; color: {color}; border-bottom: 1mm solid #e2e8f0; display: inline-block; padding: 0 20mm 2mm 20mm; margin-bottom: 15mm; }}
  .body {{ font-size: 14pt; line-height: 1.6; margin-bottom: 10mm; }}
  .course {{ font-size: 20pt; font-weight: bold; color: #0f172a; }}
  .footer {{ margin-top: auto; display: flex; justify-content: space-between; align-items: flex-end; padding-top: 10mm; }}
  .sig {{ width: 60mm; border-top: 0.3mm solid #94a3b8; padding-top: 2mm; font-size: 10pt; color: #64748b; }}
  .meta {{ font-size: 9pt; color: #94a3b8; text-align: right; }}
</style>
</head>
<body>
<div class="cert">
  <div class="corner tl"></div>
  <div class="corner br"></div>
  <div class="border-outer"></div>
  <div class="border-inner">
    <div class="header">{{{{tenant_name}}}}</div>
    <div class="title">Certificate of Completion</div>
    <div class="subtitle">This recognition is proudly presented to</div>
    <div class="name">{{{{user_name}}}}</div>
    <div class="body">For the successful completion of<br><span class="course">"{{{{training_title}}}}"</span></div>
    <div class="footer">
      <div class="sig">Authorized Signatory<br><strong>{{{{tenant_name}}}} Learning Management</strong></div>
      <div class="meta">Issued: {{{{completion_date}}}}<br>ID: {{{{certificate_number}}}}</div>
    </div>
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

async def truncate_tables(conn, tables: list[str]) -> None:
    for t in tables:
        res = await conn.execute(text("SELECT to_regclass(:t)"), {"t": t})
        if res.scalar():
            await conn.execute(text(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE"))
            print(f"    truncated {t}")
        else:
            print(f"    skipped   {t} (does not exist)")


async def insert_tenant(conn, tenant: dict) -> None:
    now = _now()
    await conn.execute(text("""
        INSERT INTO tenants (id, name, is_active, primary_color, secondary_color, created_at, updated_at)
        VALUES (:id, :name, true, :color, '#ffffff', :now, :now)
        ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, primary_color=EXCLUDED.primary_color
    """), {"id": tenant["id"], "name": tenant["name"],
           "color": tenant.get("primary_color", "#1e293b"), "now": now})
    print(f"    tenant    {tenant['name']} ({tenant['id']})")


async def insert_user(conn, email: str, full_name: str, username: str = None,
                      is_sysadmin: bool = False, memberships: list = None,
                      password: str = DEFAULT_PASSWORD) -> str:
    username = username or email.split("@")[0]
    user_id = str(uuid.uuid4())
    now = _now()
    avatar = f"avatar{random.randint(1, 10)}"

    res = await conn.execute(text("""
        INSERT INTO users (id, email, username, hashed_password, full_name, avatar_url,
                           is_sysadmin, is_active, status, created_at, updated_at)
        VALUES (:id, :email, :username, :pwd, :name, :avatar,
                :sysadmin, true, 'ACTIVE', :now, :now)
        ON CONFLICT (email) DO UPDATE SET
          hashed_password=EXCLUDED.hashed_password, full_name=EXCLUDED.full_name,
          avatar_url=EXCLUDED.avatar_url, username=EXCLUDED.username,
          is_sysadmin=EXCLUDED.is_sysadmin, is_active=EXCLUDED.is_active, status=EXCLUDED.status
        RETURNING id
    """), {"id": user_id, "email": email, "username": username, "pwd": _hash(password),
           "name": full_name, "avatar": avatar, "sysadmin": is_sysadmin, "now": now})

    uid = (res.first() or [user_id])[0]
    print(f"    user      {email}{' (sysadmin)' if is_sysadmin else ''}")

    for m in (memberships or []):
        status = m.get("status", "ACTIVE")
        active = m.get("is_active", True)
        await conn.execute(text("""
            INSERT INTO tenant_memberships
              (id, user_id, tenant_id, is_business_manager, is_training_creator,
               is_employee, is_active, status, created_at, updated_at)
            VALUES (:id, :uid, :tid, :mgr, :creator, :emp, :active, :status, :now, :now)
            ON CONFLICT (user_id, tenant_id) DO UPDATE SET
              is_business_manager=EXCLUDED.is_business_manager,
              is_training_creator=EXCLUDED.is_training_creator,
              is_employee=EXCLUDED.is_employee,
              is_active=EXCLUDED.is_active, status=EXCLUDED.status
        """), {
            "id": str(uuid.uuid4()), "uid": uid, "tid": m["tenant_id"],
            "mgr": m.get("manager", False), "creator": m.get("creator", False),
            "emp": m.get("employee", True),
            "active": active, "status": status, "now": now,
        })

    return uid


async def insert_group(conn, group: dict, email_to_id: dict) -> None:
    gid = group.get("id", str(uuid.uuid4()))
    now = _now()
    await conn.execute(text("""
        INSERT INTO groups (id, name, tenant_id, description, created_at, updated_at)
        VALUES (:id, :name, :tid, :desc, :now, :now)
        ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, description=EXCLUDED.description
    """), {"id": gid, "name": group["name"], "tid": group["tenant_id"],
           "desc": group.get("description", ""), "now": now})

    added = 0
    for email in group.get("members", []):
        uid = email_to_id.get(email)
        if uid:
            await conn.execute(text("""
                INSERT INTO group_memberships (id, group_id, user_id, created_at, updated_at)
                VALUES (:id, :gid, :uid, :now, :now)
                ON CONFLICT DO NOTHING
            """), {"id": str(uuid.uuid4()), "gid": gid, "uid": uid, "now": now})
            added += 1
        else:
            print(f"    warning   member '{email}' not found for group '{group['name']}'")

    print(f"    group     {group['name']} ({group['tenant_id']}) — {added} members")


async def insert_certificate_template(conn, tenant: dict) -> None:
    html = _certificate_html(tenant["name"], tenant.get("primary_color", "#1e293b"))
    now = _now()
    await conn.execute(text("""
        INSERT INTO certificate_templates
          (id, tenant_id, name, html_content, is_active, is_default, created_at, updated_at)
        VALUES (:id, :tid, :name, :html, true, true, :now, :now)
        ON CONFLICT DO NOTHING
    """), {"id": str(uuid.uuid4()), "tid": tenant["id"],
           "name": "Standard Professional Certificate", "html": html, "now": now})
    print(f"    cert tpl  {tenant['name']}")


async def insert_training(conn, training: dict) -> None:
    now = _now()
    await conn.execute(text("""
        INSERT INTO trainings
          (id, tenant_id, title, category, duration, is_published,
           version, structure_type, requires_certificate, created_at, updated_at)
        VALUES (:id, :tid, :title, :cat, :dur, :pub, 1, :struct, :cert, :now, :now)
        ON CONFLICT (id) DO UPDATE SET
          title=EXCLUDED.title, category=EXCLUDED.category,
          is_published=EXCLUDED.is_published, requires_certificate=EXCLUDED.requires_certificate
    """), {
        "id": training.get("id", str(uuid.uuid4())),
        "tid": training["tenant_id"],
        "title": training["title"],
        "cat": training["category"],
        "dur": training.get("duration", "30m"),
        "pub": training.get("is_published", True),
        "struct": training.get("structure_type", "flat"),
        "cert": training.get("requires_certificate", True),
        "now": now,
    })
    print(f"    training  {training['title']}")


# ---------------------------------------------------------------------------
# Seed modes
# ---------------------------------------------------------------------------

async def seed_admin_only(config: dict, auth_url: str, core_url: str) -> None:
    admin = config["admin"]

    print("\n[auth-db] Clearing tables...")
    async with create_async_engine(auth_url).begin() as conn:
        await truncate_tables(conn, AUTH_TABLES)
        print("\n[auth-db] Creating sysadmin...")
        await insert_user(conn, admin["email"], admin["full_name"],
                          admin.get("username"), is_sysadmin=True,
                          password=admin.get("password", DEFAULT_PASSWORD))

    print("\n[core-db] Clearing tables...")
    async with create_async_engine(core_url).begin() as conn:
        await truncate_tables(conn, CORE_TABLES)

    print(f"\n✓ Admin-only seed complete.")
    print(f"  Login: {admin['email']}  /  {admin.get('password', DEFAULT_PASSWORD)}")


async def seed_mock(config: dict, auth_url: str, core_url: str) -> None:
    email_to_id: dict[str, str] = {}
    admin = config["admin"]
    tenants: list = config.get("tenants", [])
    users: list = config.get("users", [])
    groups: list = config.get("groups", [])
    trainings: list = config.get("trainings", [])

    print("\n[auth-db] Clearing tables...")
    async with create_async_engine(auth_url).begin() as conn:
        await truncate_tables(conn, AUTH_TABLES)

        print("\n[auth-db] Creating tenants...")
        for t in tenants:
            await insert_tenant(conn, t)

        print("\n[auth-db] Creating sysadmin...")
        uid = await insert_user(conn, admin["email"], admin["full_name"],
                                admin.get("username"), is_sysadmin=True,
                                password=admin.get("password", DEFAULT_PASSWORD))
        email_to_id[admin["email"]] = uid

        print("\n[auth-db] Creating users...")
        for u in users:
            uid = await insert_user(
                conn, u["email"], u["full_name"], u.get("username"),
                memberships=u.get("memberships", []),
                password=u.get("password", DEFAULT_PASSWORD),
            )
            email_to_id[u["email"]] = uid

        print("\n[auth-db] Creating groups...")
        for g in groups:
            await insert_group(conn, g, email_to_id)

    print("\n[core-db] Clearing tables...")
    async with create_async_engine(core_url).begin() as conn:
        await truncate_tables(conn, CORE_TABLES)

        print("\n[core-db] Creating certificate templates...")
        for t in tenants:
            await insert_certificate_template(conn, t)

        print("\n[core-db] Creating trainings...")
        for tr in trainings:
            await insert_training(conn, tr)

    print(f"\n✓ Mock seed complete.")
    print(f"  Tenants:   {len(tenants)}")
    print(f"  Users:     {len(users) + 1}  (including sysadmin)")
    print(f"  Groups:    {len(groups)}")
    print(f"  Trainings: {len(trainings)}")
    print(f"\n  Admin login: {admin['email']}  /  {admin.get('password', DEFAULT_PASSWORD)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CustomLMS seed tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode", choices=["admin-only", "mock"], default="admin-only",
        help="Seed mode (default: admin-only)",
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent / "seed_config.json"),
        help="Path to seed_config.json",
    )
    parser.add_argument("--auth-db-url", default=None, help="Auth DB URL")
    parser.add_argument("--core-db-url", default=None, help="Core DB URL")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    # Build default URLs from .env component vars (loaded above).
    # Priority: CLI flag > AUTH_DB_URL/CORE_DB_URL env var > assembled from POSTGRES_* vars
    pg_user = os.environ.get("POSTGRES_USER", "lms_user")
    pg_pass = os.environ.get("POSTGRES_PASSWORD", "lms_pass")
    pg_host = os.environ.get("POSTGRES_HOST", "localhost")
    pg_port = os.environ.get("POSTGRES_PORT", "5433")
    default_auth = f"postgresql+asyncpg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/auth_db"
    default_core = f"postgresql+asyncpg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/core_db"

    auth_url = _ensure_asyncpg(
        args.auth_db_url or os.environ.get("AUTH_DB_URL", default_auth)
    )
    core_url = _ensure_asyncpg(
        args.core_db_url or os.environ.get("CORE_DB_URL", default_core)
    )

    print(f"Auth DB : {auth_url}")
    print(f"Core DB : {core_url}")
    print(f"Config  : {config_path}")

    if args.mode == "admin-only":
        asyncio.run(seed_admin_only(config, auth_url, core_url))
    else:
        asyncio.run(seed_mock(config, auth_url, core_url))


if __name__ == "__main__":
    main()
