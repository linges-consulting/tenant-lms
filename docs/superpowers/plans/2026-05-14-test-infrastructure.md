# Test Infrastructure Implementation Plan (Wave 0 + Wave 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Source spec:** `docs/superpowers/specs/2026-05-14-testing-strategy-design.md` (Section 10, Waves 0 and 1)

**Goal:** Build the foundational test tier at `/tests`: directory scaffolding, shared support modules, smoke tests against the real Docker stack, `tests/run_tests.sh` runner with category flags, a structured `email_suppressed` log line in the notification worker, and a spec-ID coverage map that audits every existing test in `app/<service>/tests/`.

**Architecture:** New top-level `tests/` tree organized by category (`smoke`, `unit`, `behavioral`, `integration`, `regression`). Shared fixtures live in `tests/_support/`. The runner script is the only entry point; it ensures the Docker stack is up, runs pytest with the right paths, and produces artifacts at `tests/_artifacts/`. Existing in-process unit tests under `app/<service>/tests/` are **not moved** — the runner shells into each service directory to execute them, so their fixtures and import paths keep working unchanged.

**Tech Stack:** Python 3.11, pytest, pytest-asyncio, pytest-html, pytest-cov, httpx, sqlalchemy + asyncpg, redis-py, jose (JWT), Docker Compose, bash 4+.

---

## Prerequisites (do once before starting)

- Docker Desktop running with at least 4 GB RAM allocated.
- Python 3.11 available locally (`python3.11 --version`).
- Repository checked out at `/Users/kavyahareendran/Documents/ClaudeWorkspace/CustomLMS4` (or wherever).
- A clean working tree (`git status` shows no unrelated WIP).
- The stack can be brought up cleanly: `docker compose up -d --build` succeeds and `curl http://localhost/health` (gateway) returns something non-error after ~30s.

---

## File Structure (everything touched by this plan)

### New files
```
tests/
├── README.md
├── pytest.ini
├── conftest.py
├── requirements-test.txt
├── run_tests.sh
├── _support/
│   ├── __init__.py
│   ├── stack.py
│   ├── http_client.py
│   ├── db_reset.py
│   ├── seed.py
│   ├── auth.py
│   ├── factories.py
│   ├── email_log.py
│   └── coverage_map.py
├── smoke/
│   ├── __init__.py
│   ├── test_core_health.py
│   ├── test_auth_login.py
│   ├── test_notification_health.py
│   └── test_gateway_routing.py
├── unit/
│   ├── __init__.py
│   ├── auth_service/
│   │   └── conftest.py
│   ├── core_service/
│   │   └── conftest.py
│   └── notification_service/
│       └── conftest.py
├── behavioral/
│   ├── __init__.py
│   ├── auth/__init__.py
│   ├── core/__init__.py
│   ├── notification/__init__.py
│   └── gateway/__init__.py
├── integration/
│   └── __init__.py
└── regression/
    └── __init__.py
```

### Modified files
- `app/notification_service/app/worker/email_client.py` — render template before suppress, add `email_suppressed` log line
- `.gitignore` — add `tests/_artifacts/`, `tests/__pycache__/`, `tests/_support/__pycache__/`
- `app/auth_service/tests/api/*.py` — add spec ID docstrings (Task 21)
- `app/core_service/tests/api/*.py` — add spec ID docstrings (Task 22)
- `app/notification_service/tests/api/*.py` — add spec ID docstrings (Task 23)

---

# Wave 0 — Foundation

## Task 1: Repository scaffolding

**Files:**
- Create: `tests/README.md`
- Create: `tests/pytest.ini`
- Create: `tests/requirements-test.txt`
- Create: `tests/__init__.py` (empty)
- Create: `tests/_support/__init__.py` (empty)
- Create: `tests/smoke/__init__.py` (empty)
- Create: `tests/unit/__init__.py` (empty)
- Create: `tests/unit/auth_service/__init__.py` (empty)
- Create: `tests/unit/core_service/__init__.py` (empty)
- Create: `tests/unit/notification_service/__init__.py` (empty)
- Create: `tests/behavioral/__init__.py` (empty)
- Create: `tests/behavioral/auth/__init__.py` (empty)
- Create: `tests/behavioral/core/__init__.py` (empty)
- Create: `tests/behavioral/notification/__init__.py` (empty)
- Create: `tests/behavioral/gateway/__init__.py` (empty)
- Create: `tests/integration/__init__.py` (empty)
- Create: `tests/regression/__init__.py` (empty)
- Modify: `.gitignore`

- [ ] **Step 1: Create the directory tree and empty `__init__.py` markers**

Run:
```bash
mkdir -p tests/_support tests/smoke tests/unit/auth_service tests/unit/core_service tests/unit/notification_service tests/behavioral/auth tests/behavioral/core tests/behavioral/notification tests/behavioral/gateway tests/integration tests/regression

touch tests/__init__.py \
      tests/_support/__init__.py \
      tests/smoke/__init__.py \
      tests/unit/__init__.py \
      tests/unit/auth_service/__init__.py \
      tests/unit/core_service/__init__.py \
      tests/unit/notification_service/__init__.py \
      tests/behavioral/__init__.py \
      tests/behavioral/auth/__init__.py \
      tests/behavioral/core/__init__.py \
      tests/behavioral/notification/__init__.py \
      tests/behavioral/gateway/__init__.py \
      tests/integration/__init__.py \
      tests/regression/__init__.py
```

- [ ] **Step 2: Write `tests/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = .
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: in-process unit tests (SQLite + ASGI)
    smoke: stack health check, runs before other stack categories
    behavioral: role and tenant boundary tests
    integration: multi-service end-to-end flows
    regression: invariant tests tied to constraints.md
    no_reset: opt out of per-file DB reset
    no_spec: test does not map to a spec ID in project_docs/tests.md
filterwarnings =
    ignore::DeprecationWarning:pydantic.*
    ignore::DeprecationWarning:sqlalchemy.*
```

- [ ] **Step 3: Write `tests/requirements-test.txt`**

```
pytest>=8.0
pytest-asyncio>=0.23
pytest-html>=4.1
pytest-cov>=5.0
httpx>=0.27
sqlalchemy[asyncio]>=2.0
asyncpg>=0.29
redis>=5.0
python-jose[cryptography]>=3.3
```

- [ ] **Step 4: Write `tests/README.md`**

```markdown
# Tests

Top-level test tier. See `docs/superpowers/specs/2026-05-14-testing-strategy-design.md` for the design.

## Quick start

```bash
# Install test dependencies (once)
python3.11 -m venv tests/.venv
source tests/.venv/bin/activate
pip install -r tests/requirements-test.txt

# Start the docker stack (one-time per session)
docker compose up -d --build

# Run fast tests (unit + smoke)
./tests/run_tests.sh

# Run everything
./tests/run_tests.sh --all
```

See `./tests/run_tests.sh --help` for all flags.

## Layout

- `_support/` — shared fixtures and helpers (not test modules)
- `smoke/` — stack health checks, run first
- `unit/` — in-process tests, delegate to `app/<service>/tests/`
- `behavioral/` — role and tenant boundary tests
- `integration/` — multi-service flows
- `regression/` — constraint-tied invariants
- `_artifacts/` — runner output (gitignored)
```

- [ ] **Step 5: Update `.gitignore`**

Append the following lines to `.gitignore` (append, do not replace existing content):

```
# Test artifacts
tests/_artifacts/
tests/__pycache__/
tests/_support/__pycache__/
tests/.venv/
tests/.pytest_cache/
```

- [ ] **Step 6: Verify the skeleton is well-formed**

Run:
```bash
ls -R tests/ | head -40
```
Expected: tree shown, every directory present, every `__init__.py` exists.

- [ ] **Step 7: Commit**

```bash
git add tests/ .gitignore
git commit -m "test: scaffold tests/ directory tree and pytest config

Wave 0 of test infrastructure: directory skeleton, pytest.ini with
category markers, test dependency manifest, and README. No test code
yet — that comes in later tasks.
"
```

---

## Task 2: Stack lifecycle helper

**Files:**
- Create: `tests/_support/stack.py`

- [ ] **Step 1: Install test dependencies locally**

Run:
```bash
python3.11 -m venv tests/.venv
source tests/.venv/bin/activate
pip install -r tests/requirements-test.txt
```

Expected: pip installs without error. `which pytest` shows the venv path.

- [ ] **Step 2: Write `tests/_support/stack.py`**

```python
"""
Stack lifecycle helpers.

ensure_stack_up() probes the gateway and each backend service for /health
endpoints. If all reachable, returns immediately. Otherwise runs
`docker compose up -d` and polls until services are healthy or 60s elapses.
"""
from __future__ import annotations

import subprocess
import time
from typing import Iterable

import httpx

GATEWAY_BASE = "http://localhost"

# All routes go through the gateway; we probe the per-service paths it proxies.
HEALTH_PROBES: tuple[tuple[str, str], ...] = (
    ("auth-service", f"{GATEWAY_BASE}/api/v1/auth/health"),
    ("core-service", f"{GATEWAY_BASE}/api/v1/trainings/health"),
    ("notification-service", f"{GATEWAY_BASE}/api/v1/notifications/health"),
)


class StackNotReady(RuntimeError):
    pass


def _probe(url: str, timeout: float = 2.0) -> bool:
    try:
        resp = httpx.get(url, timeout=timeout)
        return resp.status_code == 200
    except (httpx.RequestError, httpx.HTTPError):
        return False


def _all_healthy(timeout_per_probe: float = 2.0) -> tuple[bool, list[str]]:
    """Return (all_healthy, list_of_unhealthy_service_names)."""
    unhealthy = []
    for name, url in HEALTH_PROBES:
        if not _probe(url, timeout=timeout_per_probe):
            unhealthy.append(name)
    return (not unhealthy), unhealthy


def _docker_up() -> None:
    """Run `docker compose up -d` (no --build; assumes images already exist)."""
    subprocess.run(
        ["docker", "compose", "up", "-d"],
        check=True,
        capture_output=True,
    )


def ensure_stack_up(
    *,
    poll_timeout_seconds: float = 60.0,
    poll_interval_seconds: float = 2.0,
) -> None:
    """
    Ensure all backend services respond to /health.
    If not, attempt `docker compose up -d` and poll until healthy.
    Raises StackNotReady on timeout.
    """
    healthy, unhealthy = _all_healthy()
    if healthy:
        return

    # Try to start what's missing.
    try:
        _docker_up()
    except subprocess.CalledProcessError as exc:
        raise StackNotReady(
            f"`docker compose up -d` failed: {exc.stderr.decode(errors='replace')}"
        ) from exc

    deadline = time.monotonic() + poll_timeout_seconds
    while time.monotonic() < deadline:
        healthy, unhealthy = _all_healthy()
        if healthy:
            return
        time.sleep(poll_interval_seconds)

    raise StackNotReady(
        f"Stack did not become healthy within {poll_timeout_seconds}s. "
        f"Unhealthy services: {', '.join(unhealthy)}"
    )
```

- [ ] **Step 3: Smoke-check the helper manually**

Run (with stack up):
```bash
source tests/.venv/bin/activate
python -c "from tests._support.stack import ensure_stack_up; ensure_stack_up(); print('OK')"
```
Expected: `OK` printed within a few seconds.

Run (with stack down):
```bash
docker compose down
python -c "from tests._support.stack import ensure_stack_up; ensure_stack_up(); print('OK')"
```
Expected: function brings the stack up and prints `OK` within ~60s.

- [ ] **Step 4: Commit**

```bash
git add tests/_support/stack.py
git commit -m "test(infra): add stack lifecycle helper

ensure_stack_up() probes gateway-proxied health endpoints for all backend
services and runs docker compose up -d if any are unreachable. Polls
until healthy or 60s timeout.
"
```

---

## Task 3: HTTP client helper

**Files:**
- Create: `tests/_support/http_client.py`

- [ ] **Step 1: Write `tests/_support/http_client.py`**

```python
"""
HTTP client helpers for stack tests.

All stack tests hit the gateway at http://localhost — never individual
service ports — so the gateway's token swap, auth_request gating, and
route mapping are exercised.
"""
from __future__ import annotations

import httpx

GATEWAY_BASE = "http://localhost"


def gateway_client() -> httpx.AsyncClient:
    """Return an AsyncClient pointed at the Nginx gateway."""
    return httpx.AsyncClient(base_url=GATEWAY_BASE, timeout=10.0)


def with_auth(client: httpx.AsyncClient, token: str) -> httpx.AsyncClient:
    """
    Return a new AsyncClient that reuses the connection pool of `client`
    but carries Authorization: Bearer <token> on every request.
    """
    return httpx.AsyncClient(
        base_url=client.base_url,
        timeout=client.timeout,
        headers={"Authorization": f"Bearer {token}"},
    )
```

- [ ] **Step 2: Smoke-check the import**

Run:
```bash
source tests/.venv/bin/activate
python -c "from tests._support.http_client import gateway_client, with_auth; print('OK')"
```
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add tests/_support/http_client.py
git commit -m "test(infra): add gateway-facing AsyncClient helpers"
```

---

## Task 4: First smoke test — core health

**Files:**
- Create: `tests/smoke/test_core_health.py`

The verification for Tasks 2 and 3 is this smoke test running. If `pytest tests/smoke/test_core_health.py` passes, both helpers work end-to-end.

- [ ] **Step 1: Write the smoke test**

```python
# tests/smoke/test_core_health.py
"""Smoke test: core-service /health is reachable via gateway."""
import pytest

from tests._support.stack import ensure_stack_up
from tests._support.http_client import gateway_client


@pytest.fixture(scope="session", autouse=True)
def _stack_up():
    ensure_stack_up()


@pytest.mark.smoke
async def test_core_health_via_gateway():
    async with gateway_client() as client:
        resp = await client.get("/api/v1/trainings/health")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run the test and verify it passes**

Run:
```bash
source tests/.venv/bin/activate
pytest tests/smoke/test_core_health.py -v
```
Expected: 1 passed in ~3-5s.

If FAIL with connection refused: the stack didn't come up. Inspect with `docker compose ps` and `docker compose logs core-service`.

- [ ] **Step 3: Commit**

```bash
git add tests/smoke/test_core_health.py
git commit -m "test(smoke): verify core-service /health reachable via gateway"
```

---

## Task 5: Database reset helper

**Files:**
- Create: `tests/_support/db_reset.py`

- [ ] **Step 1: Discover the database connection details**

Run:
```bash
grep -E "POSTGRES_(USER|PASSWORD|DB)" docker-compose.yml | head -10
```

Note the values for `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`. The host port is `5433` (mapped from container port 5432). Redis is `localhost:6379`.

- [ ] **Step 2: Write `tests/_support/db_reset.py`**

```python
"""
Database reset helpers.

reset_databases() truncates all tables in the test Postgres database
EXCEPT the alembic_version table (preserves migration state) and a
short allowlist of seed rows that must persist (default certificate
template). Also runs FLUSHDB on Redis DB 0.

Wired as a module-scoped autouse fixture in tests/conftest.py so it
runs before each test file. Tests can opt out with @pytest.mark.no_reset.
"""
from __future__ import annotations

import os

import redis.asyncio as redis_async
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

POSTGRES_URL = os.environ.get(
    "TEST_POSTGRES_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/lms",
)
REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/0")

# Rows that survive a reset. Tuple of (table_name, where_clause_keep, params).
PRESERVE_ROWS: tuple[tuple[str, str, dict], ...] = (
    # Keep default certificate template if seeded.
    ("certificate_templates", "is_default = TRUE", {}),
)

# Tables that survive a reset entirely (no truncate).
PRESERVE_TABLES: frozenset[str] = frozenset({"alembic_version"})


async def _list_user_tables(conn: AsyncConnection) -> list[str]:
    result = await conn.execute(
        text(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename NOT LIKE 'pg_%'"
        )
    )
    return [row[0] for row in result.fetchall()]


async def _delete_with_preservation(conn: AsyncConnection, table: str) -> None:
    """Delete from a table, preserving rows that match PRESERVE_ROWS."""
    keep_clauses = [
        (clause, params) for (t, clause, params) in PRESERVE_ROWS if t == table
    ]
    if not keep_clauses:
        await conn.execute(text(f"DELETE FROM {table}"))
        return
    where = " OR ".join(f"({c})" for c, _ in keep_clauses)
    merged_params: dict = {}
    for _, p in keep_clauses:
        merged_params.update(p)
    await conn.execute(
        text(f"DELETE FROM {table} WHERE NOT ({where})"),
        merged_params,
    )


async def reset_postgres() -> None:
    engine = create_async_engine(POSTGRES_URL, pool_pre_ping=False)
    try:
        async with engine.begin() as conn:
            tables = await _list_user_tables(conn)
            await conn.execute(text("SET CONSTRAINTS ALL DEFERRED"))
            for table in tables:
                if table in PRESERVE_TABLES:
                    continue
                await _delete_with_preservation(conn, table)
    finally:
        await engine.dispose()


async def reset_redis() -> None:
    client = redis_async.from_url(REDIS_URL)
    try:
        await client.flushdb()
    finally:
        await client.aclose()


async def reset_databases() -> None:
    await reset_postgres()
    await reset_redis()
```

- [ ] **Step 3: Smoke-check the helper manually**

Run:
```bash
source tests/.venv/bin/activate
python -c "import asyncio; from tests._support.db_reset import reset_databases; asyncio.run(reset_databases()); print('OK')"
```
Expected: `OK` (and any pre-existing test data is gone). If you get an asyncpg connection error, double-check the URL and that the stack is up.

- [ ] **Step 4: Commit**

```bash
git add tests/_support/db_reset.py
git commit -m "test(infra): add Postgres + Redis reset helper

Truncates all user tables except alembic_version. Preserves seed rows
matching PRESERVE_ROWS (default certificate template). Runs FLUSHDB on
Redis DB 0.
"
```

---

## Task 6: Seed bootstrap helper

**Files:**
- Create: `tests/_support/seed.py`

- [ ] **Step 1: Verify the bootstrap SysAdmin in `app/auth_service/seed_data.py`**

Read `app/auth_service/seed_data.py` and find the section that creates a SysAdmin user. Note the email and password (the file already uses `TEST_PASSWORD = "Password123!"`).

If no bootstrap SysAdmin is defined in seed_data.py, add one. Search for `is_sysadmin=True` in the file. If found, note the email. If not, add this block to seed_data.py before `if __name__ == "__main__":`:

```python
async def ensure_bootstrap_sysadmin(conn):
    """Idempotent: create the test SysAdmin used by the test runner."""
    email = "sysadmin@test.local"
    user_id = str(uuid.uuid4())
    pw_hash = bcrypt.hashpw(TEST_PASSWORD.encode(), bcrypt.gensalt()).decode()
    now = datetime.now(timezone.utc)
    await conn.execute(
        text(
            """
            INSERT INTO users (id, email, hashed_password, full_name, is_sysadmin,
                               is_active, created_at, updated_at)
            VALUES (:id, :email, :pw, 'Test SysAdmin', TRUE, TRUE, :now, :now)
            ON CONFLICT (email) DO UPDATE SET
                is_sysadmin = TRUE,
                is_active = TRUE,
                hashed_password = EXCLUDED.hashed_password
            """
        ),
        {"id": user_id, "email": email, "pw": pw_hash, "now": now},
    )
    print(f"Ensured bootstrap SysAdmin: {email}")
```

And call it from the existing `main()` after tenant seeding.

- [ ] **Step 2: Write `tests/_support/seed.py`**

```python
"""
Canonical seed constants shared across stack tests.

The bootstrap SysAdmin is created by `app/auth_service/seed_data.py`
and survives DB resets only if added to db_reset.PRESERVE_ROWS, OR is
re-seeded by ensure_bootstrap_sysadmin() below.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests._support.db_reset import POSTGRES_URL

DEFAULT_SYSADMIN_EMAIL = "sysadmin@test.local"
DEFAULT_SYSADMIN_PASSWORD = "Password123!"


async def ensure_bootstrap_sysadmin() -> None:
    """
    Idempotent. Run after reset_databases() to guarantee the SysAdmin
    exists. Uses raw SQL to avoid pulling in service ORM modules.
    """
    import bcrypt  # local import — only needed in seed path
    import uuid
    from datetime import datetime, timezone

    pw_hash = bcrypt.hashpw(
        DEFAULT_SYSADMIN_PASSWORD.encode(), bcrypt.gensalt()
    ).decode()
    now = datetime.now(timezone.utc)
    user_id = str(uuid.uuid4())

    engine = create_async_engine(POSTGRES_URL, pool_pre_ping=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO users (id, email, hashed_password, full_name,
                                       is_sysadmin, is_active, created_at, updated_at)
                    VALUES (:id, :email, :pw, 'Test SysAdmin',
                            TRUE, TRUE, :now, :now)
                    ON CONFLICT (email) DO UPDATE SET
                        is_sysadmin = TRUE,
                        is_active = TRUE,
                        hashed_password = EXCLUDED.hashed_password
                    """
                ),
                {"id": user_id, "email": DEFAULT_SYSADMIN_EMAIL,
                 "pw": pw_hash, "now": now},
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(ensure_bootstrap_sysadmin())
    print(f"Seeded {DEFAULT_SYSADMIN_EMAIL}")
```

- [ ] **Step 3: Install `bcrypt` in the test venv if missing**

Run:
```bash
source tests/.venv/bin/activate
pip install bcrypt
```

Then add `bcrypt>=4.0` to `tests/requirements-test.txt`.

- [ ] **Step 4: Verify by running it directly**

Run:
```bash
source tests/.venv/bin/activate
python tests/_support/seed.py
```
Expected: `Seeded sysadmin@test.local`.

- [ ] **Step 5: Commit**

```bash
git add tests/_support/seed.py tests/requirements-test.txt
git commit -m "test(infra): add bootstrap SysAdmin seed helper

DEFAULT_SYSADMIN_EMAIL / DEFAULT_SYSADMIN_PASSWORD are the canonical
credentials all stack tests use to obtain a SysAdmin token.
ensure_bootstrap_sysadmin() is idempotent and safe to call after each
db_reset.
"
```

---

## Task 7: Auth helpers

**Files:**
- Create: `tests/_support/auth.py`

- [ ] **Step 1: Discover the external JWT secret**

Run:
```bash
grep -E "EXTERNAL_JWT_SECRET" docker-compose.yml app/auth_service/.env 2>/dev/null | head -5
```
Note the value. If not in env files, check `app/auth_service/app/core/config.py` for a default.

- [ ] **Step 2: Write `tests/_support/auth.py`**

```python
"""
Auth helpers for stack tests.

Two ways to authenticate a test request:
  1. mint_external_jwt(): hand-sign a token with EXTERNAL_JWT_SECRET. Fast,
     skips the login flow. Use when the test doesn't care about login.
  2. login_as(email, password): go through the real login + tenant-select
     endpoints. Use when verifying the login flow itself.

Role wrappers (as_sysadmin / as_manager / as_creator / as_employee) create
the user via factories and return a usable token + UserHandle.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from jose import jwt

from tests._support.http_client import gateway_client
from tests._support.seed import (
    DEFAULT_SYSADMIN_EMAIL,
    DEFAULT_SYSADMIN_PASSWORD,
)

EXTERNAL_JWT_SECRET = os.environ.get(
    "TEST_EXTERNAL_JWT_SECRET", "external-secret-change-me"
)
JWT_ALGORITHM = "HS256"


@dataclass
class UserHandle:
    user_id: str
    email: str
    tenant_id: str | None
    roles: list[str]
    token: str


def mint_external_jwt(
    user_id: str,
    tenant_id: str | None,
    roles: Iterable[str],
    *,
    secret: str = EXTERNAL_JWT_SECRET,
    expires_in: int = 3600,
) -> str:
    """Sign a JWT with the external secret so it passes the gateway."""
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": list(roles),
        "is_global": tenant_id is None,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


async def login_as(email: str, password: str) -> dict:
    """
    Execute the real login flow. Returns the JSON body from /api/v1/auth/login.
    For multi-tenant users, caller is responsible for /auth/select-tenant.
    """
    async with gateway_client() as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        resp.raise_for_status()
        return resp.json()


async def select_tenant(temp_token: str, tenant_id: str) -> str:
    """Exchange a temp multi-tenant token for a tenant-scoped JWT."""
    async with gateway_client() as client:
        resp = await client.post(
            "/api/v1/auth/select-tenant",
            json={"tenant_id": tenant_id},
            headers={"Authorization": f"Bearer {temp_token}"},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def as_sysadmin() -> UserHandle:
    """Log in as the bootstrap SysAdmin. Requires ensure_bootstrap_sysadmin()."""
    payload = await login_as(DEFAULT_SYSADMIN_EMAIL, DEFAULT_SYSADMIN_PASSWORD)
    token = payload["access_token"]
    decoded = jwt.decode(
        token, EXTERNAL_JWT_SECRET, algorithms=[JWT_ALGORITHM],
        options={"verify_signature": False},
    )
    return UserHandle(
        user_id=decoded["sub"],
        email=DEFAULT_SYSADMIN_EMAIL,
        tenant_id=None,
        roles=decoded.get("roles", ["SysAdmin"]),
        token=token,
    )
```

Note: `as_manager`, `as_creator`, `as_employee` depend on the factories module (Task 8). Add them in Task 8.

- [ ] **Step 3: Smoke-check the helper**

Run:
```bash
source tests/.venv/bin/activate
python -c "
import asyncio
from tests._support.seed import ensure_bootstrap_sysadmin
from tests._support.auth import as_sysadmin
async def go():
    await ensure_bootstrap_sysadmin()
    user = await as_sysadmin()
    print(f'token: {user.token[:40]}...')
asyncio.run(go())
"
```
Expected: a token prefix is printed.

- [ ] **Step 4: Commit**

```bash
git add tests/_support/auth.py
git commit -m "test(infra): add auth helpers (mint_external_jwt, login_as, as_sysadmin)

Two paths to authenticate stack tests: hand-signed JWT (fast) or full
login flow (when verifying login itself). Role wrappers come once
factories land.
"
```

---

## Task 8: Factories

**Files:**
- Create: `tests/_support/factories.py`
- Modify: `tests/_support/auth.py` (add as_manager/as_creator/as_employee)

- [ ] **Step 1: Write `tests/_support/factories.py`**

```python
"""
Domain object factories for stack tests.

Factories use real API endpoints so business logic isn't bypassed.
build_user() relies on a SysAdmin or Manager token already being
available, which the as_*() helpers in auth.py provide.
"""
from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass

from tests._support.http_client import gateway_client


@dataclass
class TenantHandle:
    id: str
    name: str


@dataclass
class UserHandle:
    id: str
    email: str
    password: str
    role: str
    tenant_id: str


def _rand_email(prefix: str = "u") -> str:
    return f"{prefix}-{secrets.token_hex(4)}@test.local"


def _rand_name(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(3)}"


async def build_tenant(sysadmin_token: str, name: str | None = None) -> TenantHandle:
    """Create a tenant via the SysAdmin API."""
    name = name or _rand_name("tenant")
    async with gateway_client() as client:
        resp = await client.post(
            "/api/v1/tenants",
            json={"name": name, "primary_color": "#000000"},
            headers={"Authorization": f"Bearer {sysadmin_token}"},
        )
        resp.raise_for_status()
        body = resp.json()
    return TenantHandle(id=body["id"], name=body["name"])


async def build_user(
    inviter_token: str,
    tenant_id: str,
    role: str,
    email: str | None = None,
    password: str = "Password123!",
) -> UserHandle:
    """
    Invite + auto-activate a user inside a tenant.

    Uses the invite endpoint, then directly activates the user via the
    SysAdmin endpoint /api/v1/users/{id}/activate-for-test (which only
    exists when ENVIRONMENT != 'prod' — see Task 8 Step 2 to add it).
    """
    email = email or _rand_email(role.lower().replace(" ", "-"))
    async with gateway_client() as client:
        invite_resp = await client.post(
            "/api/v1/users/invite",
            json={"email": email, "role": role, "tenant_id": tenant_id},
            headers={"Authorization": f"Bearer {inviter_token}"},
        )
        invite_resp.raise_for_status()
        user_id = invite_resp.json()["id"]

        activate_resp = await client.post(
            f"/api/v1/users/{user_id}/activate-for-test",
            json={"password": password},
            headers={"Authorization": f"Bearer {inviter_token}"},
        )
        activate_resp.raise_for_status()

    return UserHandle(
        id=user_id, email=email, password=password,
        role=role, tenant_id=tenant_id,
    )


async def build_training(
    creator_token: str,
    tenant_id: str,
    *,
    title: str | None = None,
    published: bool = True,
    structure: str = "flat",
    lessons: list[dict] | None = None,
) -> dict:
    """Create (and optionally publish) a training in the given tenant."""
    title = title or _rand_name("training")
    payload = {"title": title, "structure": structure,
               "lessons": lessons or [{"type": "rich_text",
                                       "title": "Lesson 1",
                                       "content": "<p>Hello</p>"}]}
    async with gateway_client() as client:
        resp = await client.post(
            "/api/v1/trainings",
            json=payload,
            headers={"Authorization": f"Bearer {creator_token}"},
        )
        resp.raise_for_status()
        training = resp.json()

        if published:
            pub_resp = await client.post(
                f"/api/v1/trainings/{training['id']}/publish",
                headers={"Authorization": f"Bearer {creator_token}"},
            )
            pub_resp.raise_for_status()
            training = pub_resp.json()
    return training


async def build_group(
    manager_token: str,
    tenant_id: str,
    *,
    name: str | None = None,
    member_ids: list[str] | None = None,
) -> dict:
    name = name or _rand_name("group")
    async with gateway_client() as client:
        resp = await client.post(
            "/api/v1/groups",
            json={"name": name, "member_ids": member_ids or []},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 2: Add a test-only activation endpoint to auth-service**

Without an activation endpoint, factories cannot turn an invited user into a usable account in a single call. Add an endpoint gated on `ENVIRONMENT != "prod"`.

Open `app/auth_service/app/api/v1/endpoints/users.py` (or wherever invite lives) and append:

```python
from app.core.config import settings

@router.post("/{user_id}/activate-for-test")
async def activate_for_test(
    user_id: str,
    payload: dict,  # {"password": "..."}
    db: AsyncSession = Depends(get_db),
    current: UserAuth = Depends(get_current_user),
):
    """
    Test-only endpoint: directly set password and activate a user that
    was created via invite. Refuses to run in production.
    """
    if settings.ENVIRONMENT == "prod":
        raise HTTPException(status_code=404, detail="Not found")

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = security.hash_password(payload["password"])
    user.is_active = True
    await db.commit()
    return {"status": "activated"}
```

Adjust imports as needed. The exact `User` model import depends on the service layout — match what other endpoints in the file do.

- [ ] **Step 3: Rebuild and restart auth-service for the new endpoint to take effect**

Run:
```bash
docker compose up -d --build auth-service
```

- [ ] **Step 4: Extend `tests/_support/auth.py` with role wrappers**

Open `tests/_support/auth.py` and append:

```python
from tests._support.factories import build_user, build_tenant, UserHandle as FactoryUserHandle


async def as_manager(tenant_id: str, sysadmin_token: str) -> UserHandle:
    user = await build_user(sysadmin_token, tenant_id, role="Business Manager")
    payload = await login_as(user.email, user.password)
    token = payload["access_token"]
    decoded = jwt.decode(token, EXTERNAL_JWT_SECRET,
                         algorithms=[JWT_ALGORITHM],
                         options={"verify_signature": False})
    return UserHandle(
        user_id=user.id, email=user.email, tenant_id=tenant_id,
        roles=["Business Manager"], token=token,
    )


async def as_creator(tenant_id: str, sysadmin_token: str) -> UserHandle:
    user = await build_user(sysadmin_token, tenant_id, role="Training Creator")
    payload = await login_as(user.email, user.password)
    return UserHandle(
        user_id=user.id, email=user.email, tenant_id=tenant_id,
        roles=["Training Creator"], token=payload["access_token"],
    )


async def as_employee(tenant_id: str, sysadmin_token: str) -> UserHandle:
    user = await build_user(sysadmin_token, tenant_id, role="Employee")
    payload = await login_as(user.email, user.password)
    return UserHandle(
        user_id=user.id, email=user.email, tenant_id=tenant_id,
        roles=["Employee"], token=payload["access_token"],
    )
```

- [ ] **Step 5: Smoke-check factories**

Run:
```bash
source tests/.venv/bin/activate
python -c "
import asyncio
from tests._support.seed import ensure_bootstrap_sysadmin
from tests._support.db_reset import reset_databases
from tests._support.auth import as_sysadmin, as_manager
from tests._support.factories import build_tenant

async def go():
    await reset_databases()
    await ensure_bootstrap_sysadmin()
    sysadmin = await as_sysadmin()
    tenant = await build_tenant(sysadmin.token, 'Acme')
    manager = await as_manager(tenant.id, sysadmin.token)
    print(f'manager token: {manager.token[:40]}...')
asyncio.run(go())
"
```
Expected: token prefix printed. If 404 on `activate-for-test`, the auth-service restart didn't pick up the new endpoint — `docker compose logs auth-service` will show the routing table on startup.

- [ ] **Step 6: Commit**

```bash
git add tests/_support/factories.py tests/_support/auth.py app/auth_service/app/api/v1/endpoints/users.py
git commit -m "test(infra): add factories + role wrappers + test-only activation endpoint

build_tenant/build_user/build_training/build_group hit real API endpoints
so business rules are exercised. Role wrappers (as_manager/as_creator/
as_employee) compose factories with login. A new auth-service endpoint
/users/{id}/activate-for-test (refused in prod) lets factories skip the
magic-link click step.
"
```

---

## Task 9: Root conftest with autouse DB reset

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Write `tests/conftest.py`**

```python
"""
Root conftest for the stack-test tier.

Fixtures:
  - _stack_ready: session-scoped autouse; brings up Docker stack if needed.
  - _module_reset: module-scoped autouse; truncates DB + flushes Redis
    before each test file. Opt out with @pytest.mark.no_reset on the file.
  - gateway_client: function-scoped; AsyncClient pointed at the gateway.
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from tests._support.stack import ensure_stack_up
from tests._support.db_reset import reset_databases
from tests._support.seed import ensure_bootstrap_sysadmin
from tests._support.email_log import clear_email_log
from tests._support.http_client import gateway_client as _gateway_client


@pytest.fixture(scope="session", autouse=True)
def _stack_ready():
    ensure_stack_up()


@pytest_asyncio.fixture(scope="module", autouse=True)
async def _module_reset(request):
    """
    Reset DB + Redis + email log marker before each test file.
    Skip if the module has @pytest.mark.no_reset.
    """
    if request.node.get_closest_marker("no_reset"):
        yield
        return
    await reset_databases()
    await ensure_bootstrap_sysadmin()
    clear_email_log()
    yield


@pytest_asyncio.fixture
async def gateway_client():
    async with _gateway_client() as client:
        yield client
```

Note: `email_log` is imported but doesn't exist yet — Task 11 creates it. Until then, comment out the `from tests._support.email_log import clear_email_log` line and the `clear_email_log()` call. Re-enable in Task 11 Step 4.

- [ ] **Step 2: Temporarily stub email_log import**

Edit `tests/conftest.py` and comment out:
```python
# from tests._support.email_log import clear_email_log
```
and the line `clear_email_log()`. You'll restore them in Task 11.

- [ ] **Step 3: Verify the conftest is loaded by re-running the existing smoke test**

Run:
```bash
source tests/.venv/bin/activate
pytest tests/smoke/test_core_health.py -v
```
Expected: still passes; you'll see "_module_reset" listed in fixture setup if you add `-s --setup-show`.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test(infra): root conftest with session stack check and per-file DB reset

@pytest.mark.no_reset opts an individual file out of the reset fixture.
gateway_client is the canonical AsyncClient fixture for stack tests.
"
```

---

## Task 10: Add `email_suppressed` log line to notification worker

**Files:**
- Modify: `app/notification_service/app/worker/email_client.py`

The current `send_email()` returns early when `USE_MAILGUN=False` *before rendering the template*, which means tests cannot see what would have been sent. Fix: render first, log a structured `email_suppressed` line, then either send or skip.

- [ ] **Step 1: Read current `email_client.py`**

The current code (Path: `app/notification_service/app/worker/email_client.py`):

```python
async def send_email(to: str, subject: str, template_name: str, context: dict) -> bool:
    if not settings.USE_MAILGUN:
        return True
    ...
```

- [ ] **Step 2: Rewrite to render before suppress + log structured line**

Replace the entire `send_email` function with:

```python
import json

async def send_email(to: str, subject: str, template_name: str, context: dict) -> bool:
    """
    Send email via Mailgun. Always renders the template (even when
    USE_MAILGUN=False) and emits a structured `email_suppressed` log
    line so tests can inspect what would have been sent.
    """
    template = _jinja_env.get_template(template_name)
    html_body = template.render(**context)

    if not settings.USE_MAILGUN:
        logger.info(json.dumps({
            "event": "email_suppressed",
            "to": to,
            "template": template_name,
            "tenant_id": context.get("tenant_id"),
            "subject": subject,
            "body_preview": html_body[:500],
            "variables": context,
        }, default=str))
        return True

    recipient = to
    if settings.ENVIRONMENT == "dev" and settings.MAILGUN_AUTHORIZED_RECIPIENT:
        recipient = settings.MAILGUN_AUTHORIZED_RECIPIENT

    async with httpx.AsyncClient(timeout=10) as http_client:
        try:
            response = await http_client.post(
                f"{settings.MAILGUN_BASE_URL}/v3/{settings.MAILGUN_DOMAIN}/messages",
                auth=("api", settings.MAILGUN_API_KEY),
                data={
                    "from": settings.FROM_EMAIL,
                    "to": recipient,
                    "subject": subject,
                    "html": html_body,
                },
            )
            if response.status_code != 200:
                logger.error("Mailgun returned %s: %s",
                             response.status_code, response.text)
            return response.status_code == 200
        except httpx.RequestError as exc:
            logger.error("Mailgun request failed: %s", exc)
            return False
```

Add `import json` at the top of the file if not already present.

- [ ] **Step 3: Rebuild notification-service**

Run:
```bash
docker compose up -d --build notification-service
```

- [ ] **Step 4: Verify the log line emits**

Run (this triggers an email by sending a magic-link invite):
```bash
source tests/.venv/bin/activate
python -c "
import asyncio
from tests._support.seed import ensure_bootstrap_sysadmin
from tests._support.db_reset import reset_databases
from tests._support.auth import as_sysadmin
from tests._support.factories import build_tenant, build_user

async def go():
    await reset_databases()
    await ensure_bootstrap_sysadmin()
    sysadmin = await as_sysadmin()
    tenant = await build_tenant(sysadmin.token, 'EmailTest')
    # Invite (don't activate) — invite alone triggers an email
    await build_user(sysadmin.token, tenant.id, 'Employee')
asyncio.run(go())
"
```

Then check the logs:
```bash
docker compose logs notification-service --since=1m | grep email_suppressed
```
Expected: at least one line like `{"event": "email_suppressed", "to": "...", "template": "...", ...}`.

- [ ] **Step 5: Commit**

```bash
git add app/notification_service/app/worker/email_client.py
git commit -m "feat(notification): emit email_suppressed log line when USE_MAILGUN=False

Render the template even when sends are suppressed so tests can
inspect what would have been emailed. Logs a single structured JSON
line per suppressed message containing recipient, template, tenant,
subject, body preview, and variables.
"
```

---

## Task 11: Email log helper

**Files:**
- Create: `tests/_support/email_log.py`
- Modify: `tests/conftest.py` (restore commented imports)

- [ ] **Step 1: Write `tests/_support/email_log.py`**

```python
"""
Email log assertion helpers.

assert_email_sent(...) polls `docker compose logs notification-service`
for an `event=email_suppressed` line matching the criteria. Returns the
parsed dict. Raises AssertionError on timeout with the last log lines.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from datetime import datetime, timezone

# Module-level marker. clear_email_log() updates it; assert_email_sent
# only considers lines emitted after the marker.
_since: datetime = datetime.now(timezone.utc)


def clear_email_log() -> datetime:
    global _since
    _since = datetime.now(timezone.utc)
    return _since


def _fetch_log_lines(since: datetime) -> list[str]:
    proc = subprocess.run(
        [
            "docker", "compose", "logs", "notification-service",
            "--since", since.isoformat(),
            "--no-log-prefix",
        ],
        capture_output=True, text=True, check=False,
    )
    return proc.stdout.splitlines()


def _parse_email_events(lines: list[str]) -> list[dict]:
    events = []
    for line in lines:
        # The notification service wraps every log line in StructuredFormatter
        # JSON. Our message field itself is JSON. So we look for two JSON
        # layers — the outer wrapper, then parse the "message" field.
        try:
            outer = json.loads(line)
            msg = outer.get("message", "")
            inner = json.loads(msg) if msg.startswith("{") else None
            if inner and inner.get("event") == "email_suppressed":
                events.append(inner)
        except (json.JSONDecodeError, AttributeError):
            continue
    return events


def _matches(
    event: dict,
    *,
    template: str,
    to: str | None,
    contains: str | list[str] | None,
    tenant_id: str | None,
) -> bool:
    if event.get("template") != template:
        return False
    if to is not None and event.get("to") != to:
        return False
    if tenant_id is not None and event.get("tenant_id") != tenant_id:
        return False
    if contains is not None:
        needles = [contains] if isinstance(contains, str) else contains
        body = (event.get("body_preview") or "") + json.dumps(event.get("variables") or {})
        for n in needles:
            if n not in body:
                return False
    return True


async def assert_email_sent(
    template: str,
    *,
    to: str | None = None,
    contains: str | list[str] | None = None,
    tenant_id: str | None = None,
    since: datetime | None = None,
    timeout: float = 3.0,
) -> dict:
    """Poll until a matching event appears or timeout elapses."""
    since = since or _since
    deadline = asyncio.get_event_loop().time() + timeout
    last_events: list[dict] = []
    while asyncio.get_event_loop().time() < deadline:
        lines = _fetch_log_lines(since)
        events = _parse_email_events(lines)
        last_events = events
        for ev in events:
            if _matches(ev, template=template, to=to,
                        contains=contains, tenant_id=tenant_id):
                return ev
        await asyncio.sleep(0.1)

    summary = "\n".join(json.dumps(e)[:200] for e in last_events[-20:])
    raise AssertionError(
        f"No email matched template={template} to={to} contains={contains} "
        f"tenant_id={tenant_id} within {timeout}s.\n"
        f"Last events seen:\n{summary or '(none)'}"
    )


async def assert_no_email_sent(
    *,
    template: str | None = None,
    to: str | None = None,
    since: datetime | None = None,
    wait: float = 1.0,
) -> None:
    """Wait `wait` seconds, then fail if a matching event is found."""
    since = since or _since
    await asyncio.sleep(wait)
    events = _parse_email_events(_fetch_log_lines(since))
    for ev in events:
        if template is not None and ev.get("template") != template:
            continue
        if to is not None and ev.get("to") != to:
            continue
        raise AssertionError(
            f"Expected no email for template={template} to={to}, "
            f"but found: {json.dumps(ev)[:200]}"
        )
```

- [ ] **Step 2: Restore the email_log import in `tests/conftest.py`**

Edit `tests/conftest.py` and uncomment the previously commented lines:

```python
from tests._support.email_log import clear_email_log
```
and the `clear_email_log()` call inside `_module_reset`.

- [ ] **Step 3: Smoke-check the helper**

Run:
```bash
source tests/.venv/bin/activate
python -c "
import asyncio
from tests._support.seed import ensure_bootstrap_sysadmin
from tests._support.db_reset import reset_databases
from tests._support.auth import as_sysadmin
from tests._support.factories import build_tenant, build_user
from tests._support.email_log import assert_email_sent, clear_email_log

async def go():
    await reset_databases()
    await ensure_bootstrap_sysadmin()
    sysadmin = await as_sysadmin()
    tenant = await build_tenant(sysadmin.token, 'EmailTest')
    clear_email_log()
    user = await build_user(sysadmin.token, tenant.id, 'Employee')
    ev = await assert_email_sent(template='magic_link_invite', to=user.email)
    print(f'OK: matched email to {ev[\"to\"]}')
asyncio.run(go())
"
```
Expected: `OK: matched email to ...`.

If template name doesn't match, inspect `docker compose logs notification-service | grep email_suppressed` to see the actual `template` value and use that.

- [ ] **Step 4: Commit**

```bash
git add tests/_support/email_log.py tests/conftest.py
git commit -m "test(infra): add email log assertion helpers

assert_email_sent polls docker logs notification-service for
event=email_suppressed lines, parses the inner JSON, and asserts on
template/to/contains/tenant_id. assert_no_email_sent is the negative
case. clear_email_log resets the since marker — autowired in the root
conftest's _module_reset fixture.
"
```

---

## Task 12: Smoke test — auth login

**Files:**
- Create: `tests/smoke/test_auth_login.py`

- [ ] **Step 1: Write the smoke test**

```python
# tests/smoke/test_auth_login.py
"""Smoke test: SysAdmin can log in via gateway."""
import pytest

from tests._support.auth import as_sysadmin


@pytest.mark.smoke
async def test_sysadmin_can_login():
    user = await as_sysadmin()
    assert user.token
    assert user.email == "sysadmin@test.local"
```

- [ ] **Step 2: Run and verify**

Run:
```bash
source tests/.venv/bin/activate
pytest tests/smoke/test_auth_login.py -v
```
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/smoke/test_auth_login.py
git commit -m "test(smoke): verify SysAdmin login through gateway"
```

---

## Task 13: Smoke test — notification health + email log smoke

**Files:**
- Create: `tests/smoke/test_notification_health.py`

- [ ] **Step 1: Write the smoke test**

```python
# tests/smoke/test_notification_health.py
"""Smoke test: notification-service /health + email_suppressed log emits."""
import pytest

from tests._support.auth import as_sysadmin
from tests._support.factories import build_tenant, build_user
from tests._support.email_log import assert_email_sent, clear_email_log
from tests._support.http_client import gateway_client


@pytest.mark.smoke
async def test_notification_health_via_gateway():
    async with gateway_client() as client:
        resp = await client.get("/api/v1/notifications/health")
    assert resp.status_code == 200


@pytest.mark.smoke
async def test_invite_emits_email_suppressed_log():
    sysadmin = await as_sysadmin()
    tenant = await build_tenant(sysadmin.token, "SmokeEmail")
    clear_email_log()
    user = await build_user(sysadmin.token, tenant.id, "Employee")
    event = await assert_email_sent(template="magic_link_invite", to=user.email)
    assert event["to"] == user.email
```

- [ ] **Step 2: Run and verify**

Run:
```bash
source tests/.venv/bin/activate
pytest tests/smoke/test_notification_health.py -v
```
Expected: 2 passed.

If the second test fails because the template name is different from `magic_link_invite`, find the real name with `docker compose logs notification-service | grep email_suppressed` and update the assertion.

- [ ] **Step 3: Commit**

```bash
git add tests/smoke/test_notification_health.py
git commit -m "test(smoke): verify notification health and email log smoke"
```

---

## Task 14: Smoke test — gateway routing

**Files:**
- Create: `tests/smoke/test_gateway_routing.py`

- [ ] **Step 1: Write the smoke test**

```python
# tests/smoke/test_gateway_routing.py
"""Smoke test: gateway proxies known paths to the right service."""
import pytest

from tests._support.http_client import gateway_client


@pytest.mark.smoke
@pytest.mark.parametrize("path", [
    "/api/v1/auth/health",
    "/api/v1/trainings/health",
    "/api/v1/notifications/health",
])
async def test_gateway_proxies_health_paths(path):
    async with gateway_client() as client:
        resp = await client.get(path)
    assert resp.status_code == 200, f"{path} returned {resp.status_code}"


@pytest.mark.smoke
async def test_unknown_route_returns_404():
    async with gateway_client() as client:
        resp = await client.get("/api/v1/no-such-thing")
    assert resp.status_code in (404, 502)  # gateway 404 or upstream-not-found
```

- [ ] **Step 2: Run and verify**

Run:
```bash
source tests/.venv/bin/activate
pytest tests/smoke/test_gateway_routing.py -v
```
Expected: 4 passed (3 parametrized + 1).

- [ ] **Step 3: Commit**

```bash
git add tests/smoke/test_gateway_routing.py
git commit -m "test(smoke): verify gateway routes the three backend services"
```

---

## Task 15: Runner script

**Files:**
- Create: `tests/run_tests.sh`

- [ ] **Step 1: Write `tests/run_tests.sh`**

```bash
#!/usr/bin/env bash
# tests/run_tests.sh — single entry point for the test suite.
# See docs/superpowers/specs/2026-05-14-testing-strategy-design.md §6 for flag reference.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTS_DIR="$REPO_ROOT/tests"
ARTIFACTS_DIR="$TESTS_DIR/_artifacts"
VENV="$TESTS_DIR/.venv"

# ---------- defaults ----------
RUN_UNIT=0
RUN_SMOKE=0
RUN_BEHAVIORAL=0
RUN_INTEGRATION=0
RUN_REGRESSION=0
SERVICE=""
NO_STACK=0
NO_RESET=0
NO_SMOKE=0
KEEP_LOGS=0
SHOW_EMAILS=0
CI_MODE=0
COVERAGE=0
COVERAGE_MAP=0
KEXPR=""
VERBOSITY=""

usage() {
    cat <<EOF
Usage: $0 [flags]

Categories (compose freely; default = --unit --smoke):
  --unit            run in-process unit tests (no stack needed)
  --smoke           run stack smoke tests
  --behavioral     run role/tenant boundary tests
  --integration     run cross-service flow tests
  --regression      run constraint-tied invariant tests
  --all             all of the above

Filters & toggles:
  --service NAME    auth | core | notification | gateway (composes with categories)
  --no-stack        skip ensure_stack_up() check
  --no-reset        skip per-file DB reset
  --no-smoke        suppress implicit smoke prerun
  --keep-logs       dump docker logs to tests/_artifacts/logs/
  --show-emails     print captured email_suppressed lines
  --coverage        collect Python code coverage
  --coverage-map    generate spec-ID coverage map
  --ci              implies --all + JUnit XML + no colors + stop on first failure
  -k EXPR           pytest -k filter
  -v | -vv          verbosity

Artifacts always at: $ARTIFACTS_DIR
EOF
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --unit)         RUN_UNIT=1; shift ;;
        --smoke)        RUN_SMOKE=1; shift ;;
        --behavioral)   RUN_BEHAVIORAL=1; shift ;;
        --integration)  RUN_INTEGRATION=1; shift ;;
        --regression)   RUN_REGRESSION=1; shift ;;
        --all)
            RUN_UNIT=1; RUN_SMOKE=1; RUN_BEHAVIORAL=1
            RUN_INTEGRATION=1; RUN_REGRESSION=1
            shift ;;
        --service)      SERVICE="$2"; shift 2 ;;
        --no-stack)     NO_STACK=1; shift ;;
        --no-reset)     NO_RESET=1; shift ;;
        --no-smoke)     NO_SMOKE=1; shift ;;
        --keep-logs)    KEEP_LOGS=1; shift ;;
        --show-emails)  SHOW_EMAILS=1; shift ;;
        --coverage)     COVERAGE=1; shift ;;
        --coverage-map) COVERAGE_MAP=1; shift ;;
        --ci)
            CI_MODE=1
            RUN_UNIT=1; RUN_SMOKE=1; RUN_BEHAVIORAL=1
            RUN_INTEGRATION=1; RUN_REGRESSION=1
            shift ;;
        -k)             KEXPR="$2"; shift 2 ;;
        -v)             VERBOSITY="-v"; shift ;;
        -vv)            VERBOSITY="-vv"; shift ;;
        -h|--help)      usage ;;
        *)              echo "Unknown flag: $1"; usage ;;
    esac
done

# Default to unit + smoke if no category chosen.
if [[ $RUN_UNIT -eq 0 && $RUN_SMOKE -eq 0 && $RUN_BEHAVIORAL -eq 0 \
      && $RUN_INTEGRATION -eq 0 && $RUN_REGRESSION -eq 0 ]]; then
    RUN_UNIT=1
    RUN_SMOKE=1
fi

# Implicit smoke prerun whenever any non-unit stack category is chosen.
if [[ $NO_SMOKE -eq 0 ]]; then
    if [[ $RUN_BEHAVIORAL -eq 1 || $RUN_INTEGRATION -eq 1 || $RUN_REGRESSION -eq 1 ]]; then
        RUN_SMOKE=1
    fi
fi

# Clean and recreate artifacts dir.
rm -rf "$ARTIFACTS_DIR"
mkdir -p "$ARTIFACTS_DIR"

# Activate venv.
if [[ ! -d "$VENV" ]]; then
    echo "Test venv missing. Run: python3.11 -m venv $VENV && pip install -r $TESTS_DIR/requirements-test.txt"
    exit 2
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# Common pytest args
PYTEST_BASE=(
    "$VENV/bin/pytest"
    --rootdir="$REPO_ROOT"
    -c "$TESTS_DIR/pytest.ini"
    --html="$ARTIFACTS_DIR/report.html" --self-contained-html
    --junitxml="$ARTIFACTS_DIR/junit.xml"
)
[[ -n "$VERBOSITY" ]] && PYTEST_BASE+=("$VERBOSITY")
[[ -n "$KEXPR" ]] && PYTEST_BASE+=("-k" "$KEXPR")
[[ $CI_MODE -eq 1 ]] && PYTEST_BASE+=("--color=no" "-x")
if [[ $COVERAGE -eq 1 ]]; then
    PYTEST_BASE+=(
        --cov=app
        --cov-report="html:$ARTIFACTS_DIR/coverage"
        --cov-report="xml:$ARTIFACTS_DIR/coverage.xml"
    )
fi

# Service path filter.
service_path_filter() {
    local base="$1"  # e.g. tests/behavioral
    if [[ -z "$SERVICE" ]]; then
        echo "$base"
    else
        echo "$base/$SERVICE"
    fi
}

# Ensure stack up for any non-unit category.
NEED_STACK=0
[[ $RUN_SMOKE -eq 1 || $RUN_BEHAVIORAL -eq 1 || \
   $RUN_INTEGRATION -eq 1 || $RUN_REGRESSION -eq 1 ]] && NEED_STACK=1

if [[ $NEED_STACK -eq 1 && $NO_STACK -eq 0 ]]; then
    python -c "from tests._support.stack import ensure_stack_up; ensure_stack_up()"
fi

OVERALL_RC=0

run_pytest() {
    local label="$1"; shift
    echo "=== Running $label ==="
    if "${PYTEST_BASE[@]}" "$@"; then
        echo "=== $label: PASS ==="
    else
        OVERALL_RC=$?
        echo "=== $label: FAIL ($OVERALL_RC) ==="
        [[ $CI_MODE -eq 1 ]] && exit $OVERALL_RC
    fi
}

# Smoke first (gates everything else).
if [[ $RUN_SMOKE -eq 1 ]]; then
    run_pytest "smoke" "$TESTS_DIR/smoke"
    if [[ $OVERALL_RC -ne 0 && $NO_SMOKE -eq 0 ]]; then
        echo "Smoke failed — skipping remaining categories."
        exit $OVERALL_RC
    fi
fi

if [[ $RUN_UNIT -eq 1 ]]; then
    run_pytest "unit" "$TESTS_DIR/unit"
fi

if [[ $RUN_BEHAVIORAL -eq 1 ]]; then
    target=$(service_path_filter "$TESTS_DIR/behavioral")
    run_pytest "behavioral" "$target"
fi

if [[ $RUN_INTEGRATION -eq 1 ]]; then
    run_pytest "integration" "$TESTS_DIR/integration"
fi

if [[ $RUN_REGRESSION -eq 1 ]]; then
    run_pytest "regression" "$TESTS_DIR/regression"
fi

# Post-run artifact tasks.
if [[ $KEEP_LOGS -eq 1 ]]; then
    mkdir -p "$ARTIFACTS_DIR/logs"
    for svc in auth-service core-service notification-service gateway; do
        docker compose logs "$svc" > "$ARTIFACTS_DIR/logs/$svc.log" 2>&1 || true
    done
fi

if [[ $SHOW_EMAILS -eq 1 ]]; then
    docker compose logs notification-service | grep email_suppressed \
        > "$ARTIFACTS_DIR/emails.log" || true
    cat "$ARTIFACTS_DIR/emails.log"
fi

if [[ $COVERAGE_MAP -eq 1 ]]; then
    python -m tests._support.coverage_map > "$ARTIFACTS_DIR/coverage_map.md"
    cat "$ARTIFACTS_DIR/coverage_map.md"
fi

# Manifest.
cat > "$ARTIFACTS_DIR/last_run.json" <<EOF
{
  "timestamp": "$(date -u +%FT%TZ)",
  "exit_code": $OVERALL_RC,
  "flags": "$*"
}
EOF

exit $OVERALL_RC
```

- [ ] **Step 2: Make it executable**

Run:
```bash
chmod +x tests/run_tests.sh
```

- [ ] **Step 3: Verify `--help`**

Run:
```bash
./tests/run_tests.sh --help
```
Expected: usage text printed, exit code 1.

- [ ] **Step 4: Verify smoke run**

Run:
```bash
./tests/run_tests.sh --smoke
```
Expected: smoke tests pass, `tests/_artifacts/report.html` and `tests/_artifacts/junit.xml` exist.

- [ ] **Step 5: Commit**

```bash
git add tests/run_tests.sh
git commit -m "test(infra): add run_tests.sh — single entry point with category flags

Composable category flags (--unit/--smoke/--behavioral/--integration/
--regression/--all). Service filter (--service auth|core|notification|
gateway). State toggles (--no-stack, --no-reset, --no-smoke). Artifact
controls (--keep-logs, --show-emails, --coverage, --coverage-map). CI
mode shortcut. Always produces HTML + JUnit XML at tests/_artifacts/.
"
```

---

## Task 16: Wave 0 verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full Wave 0 exit criterion**

Run:
```bash
./tests/run_tests.sh --smoke -v
```
Expected:
- "smoke: PASS"
- All 4+ smoke tests pass (gateway routing, auth login, core health, notification health, email log smoke)
- `tests/_artifacts/report.html` exists and opens cleanly in a browser
- `tests/_artifacts/junit.xml` exists and is valid XML

- [ ] **Step 2: Verify default behavior (no flags)**

Run:
```bash
./tests/run_tests.sh
```
Expected: runs unit + smoke. Unit step will likely fail because Wave 1 hasn't wired collection yet — that's fine, but smoke must still pass and report.html must exist.

- [ ] **Step 3: Tag the Wave 0 milestone (optional)**

Run:
```bash
git tag wave-0-complete
```

Wave 0 is complete. Move to Wave 1.

---

# Wave 1 — Coverage Baseline

## Task 17: Wire unit collection

**Files:**
- Create: `tests/unit/auth_service/conftest.py`
- Create: `tests/unit/core_service/conftest.py`
- Create: `tests/unit/notification_service/conftest.py`

Existing in-process tests live at `app/<service>/tests/`. Pytest invoked from the repo root won't find them by default, and their conftests rely on the service directory being on `sys.path`. The cleanest approach is a per-service conftest that adds the service directory to `sys.path` and re-collects from it.

- [ ] **Step 1: Write `tests/unit/auth_service/conftest.py`**

```python
"""
Bridge in existing in-process tests at app/auth_service/tests/.

Pytest collects this file, which adjusts sys.path and re-publishes
test discovery to the service's own tests directory.
"""
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SERVICE_ROOT = os.path.join(REPO_ROOT, "app", "auth_service")
SERVICE_TESTS = os.path.join(SERVICE_ROOT, "tests")

# Service code lives at app/auth_service/main.py (root-level), so the
# service root itself goes on sys.path.
if SERVICE_ROOT not in sys.path:
    sys.path.insert(0, SERVICE_ROOT)

# Re-export the service's conftest fixtures by importing it here.
# pytest will pick them up automatically because this file is a conftest.
sys.path.insert(0, SERVICE_TESTS)

collect_ignore_glob = ["test_*.py"]  # don't try to collect from this dir itself

def pytest_collect_file(parent, file_path):
    """Forward collection to app/auth_service/tests/."""
    return None  # actual collection happens via the path arg below
```

Then add a `pytest.ini`-style addopts at the file-level using a simpler approach. Replace the above conftest with this simpler bridge:

```python
"""Bridge in existing tests at app/auth_service/tests/."""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = REPO_ROOT / "app" / "auth_service"
SERVICE_TESTS = SERVICE_ROOT / "tests"

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

def pytest_collection_modifyitems(config, items):
    """No-op; collection is driven by --collect-from below."""
    pass

# Drive collection from the service's tests directory.
def pytest_addoption(parser):
    pass

collect_ignore: list[str] = []

# The runner script calls pytest with the service tests path appended
# explicitly (see Task 17 Step 4 — runner update).
```

This file alone isn't enough — the runner needs to pass the service tests path to pytest. We'll handle that in Step 4.

- [ ] **Step 2: Repeat for core_service and notification_service**

`tests/unit/core_service/conftest.py`:
```python
"""Bridge in existing tests at app/core_service/tests/."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = REPO_ROOT / "app" / "core_service"

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))
```

`tests/unit/notification_service/conftest.py`:
```python
"""Bridge in existing tests at app/notification_service/tests/."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = REPO_ROOT / "app" / "notification_service"

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))
```

- [ ] **Step 3: Update `tests/run_tests.sh` to invoke unit tests per service**

Replace the `if [[ $RUN_UNIT -eq 1 ]]; then ... fi` block in `tests/run_tests.sh` with:

```bash
if [[ $RUN_UNIT -eq 1 ]]; then
    # In-process tests live in each service's tests/ directory.
    # Run pytest from each service directory so its conftest path resolution works.
    unit_services=(auth_service core_service notification_service)
    if [[ -n "$SERVICE" ]]; then
        # Map runner --service name to service dir name
        case "$SERVICE" in
            auth)         unit_services=(auth_service) ;;
            core)         unit_services=(core_service) ;;
            notification) unit_services=(notification_service) ;;
            gateway)      unit_services=() ;;  # gateway has no in-process tests
            *)            echo "Unknown service: $SERVICE"; exit 2 ;;
        esac
    fi
    for svc in "${unit_services[@]}"; do
        echo "=== Running unit:$svc ==="
        ( cd "$REPO_ROOT/app/$svc" && \
          "$VENV/bin/pytest" tests/ \
            --html="$ARTIFACTS_DIR/report-unit-$svc.html" --self-contained-html \
            --junitxml="$ARTIFACTS_DIR/junit-unit-$svc.xml" \
            ${VERBOSITY:+$VERBOSITY} \
            ${KEXPR:+-k "$KEXPR"} \
        ) || OVERALL_RC=$?
    done
fi
```

The `tests/unit/<service>/conftest.py` files become reference markers rather than the actual collection point — the runner just shells into each service directory and runs pytest there, which is robust.

- [ ] **Step 4: Make sure each service has the test deps it needs**

The existing service tests depend on packages in each service's `requirements.txt` or `requirements-test.txt`. Verify pytest can run from inside the service venv:

Run:
```bash
cd app/auth_service && pip install -r requirements.txt && pytest tests/ -v --collect-only | head -30
cd -
```
Expected: collection succeeds. If imports fail, you may need a service-specific venv; document that in `tests/README.md`.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/ tests/run_tests.sh
git commit -m "test(infra): wire unit-test collection into runner

Runner shells into each service directory and runs pytest there, which
preserves the existing conftest path resolution. Per-service html and
junit artifacts land at tests/_artifacts/report-unit-<svc>.html.
"
```

---

## Task 18: Verify --unit flag

**Files:** none (verification only)

- [ ] **Step 1: Run --unit**

Run:
```bash
./tests/run_tests.sh --unit -v
```
Expected: each service's existing tests run. Some may fail; that's a pre-existing issue, not a Wave 1 blocker. Document failing tests in a follow-up issue.

- [ ] **Step 2: Verify per-service artifacts**

Run:
```bash
ls tests/_artifacts/
```
Expected: `report-unit-auth_service.html`, `report-unit-core_service.html`, `report-unit-notification_service.html` all exist.

- [ ] **Step 3: Verify per-service filter**

Run:
```bash
./tests/run_tests.sh --unit --service core
```
Expected: only core_service tests run.

No commit — this is verification only.

---

## Task 19: Coverage map tool

**Files:**
- Create: `tests/_support/coverage_map.py`

The tool walks all test files in `tests/` and `app/<service>/tests/`, parses spec IDs from docstrings, loads the spec list from `project_docs/tests.md`, and produces a Markdown coverage map.

- [ ] **Step 1: Write `tests/_support/coverage_map.py`**

```python
"""
Spec-ID coverage map.

Walks all test files, parses spec IDs from the first docstring line
(format: 'Covers: T-XX-NN, T-XX-NN, ...'), loads spec IDs from
project_docs/tests.md, and prints a Markdown report comparing them.

Run via: python -m tests._support.coverage_map
Also wired to ./tests/run_tests.sh --coverage-map.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_FILE = REPO_ROOT / "project_docs" / "tests.md"

# Where to look for tests.
TEST_ROOTS = [
    REPO_ROOT / "tests",
    REPO_ROOT / "app" / "auth_service" / "tests",
    REPO_ROOT / "app" / "core_service" / "tests",
    REPO_ROOT / "app" / "notification_service" / "tests",
]

SPEC_ID_PATTERN = re.compile(r"\bT-[A-Z]+-\d+\b|\bC-\d+\b|\bBR-\d+\b")
SPEC_TABLE_ROW = re.compile(r"^\|\s*(T-[A-Z]+-\d+)\s*\|")
COVERS_LINE = re.compile(r"^\s*Covers:\s*(.+)$", re.MULTILINE)


def load_spec_ids() -> set[str]:
    """Extract every spec ID from project_docs/tests.md table rows."""
    if not SPEC_FILE.exists():
        return set()
    ids = set()
    for line in SPEC_FILE.read_text().splitlines():
        m = SPEC_TABLE_ROW.match(line)
        if m:
            ids.add(m.group(1))
    return ids


def walk_test_files() -> list[Path]:
    files: list[Path] = []
    for root in TEST_ROOTS:
        if not root.exists():
            continue
        files.extend(p for p in root.rglob("test_*.py")
                     if "__pycache__" not in p.parts)
    return files


def extract_covers(path: Path) -> list[tuple[str, set[str]]]:
    """
    Return [(test_function_name, set_of_spec_ids)] for each test in the file.
    """
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return []
    results: list[tuple[str, set[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            if not node.name.startswith("test_"):
                continue
            doc = ast.get_docstring(node) or ""
            m = COVERS_LINE.search(doc)
            ids: set[str] = set()
            if m:
                ids = set(SPEC_ID_PATTERN.findall(m.group(1)))
            results.append((node.name, ids))
    return results


def categorize(spec_id: str) -> str:
    if spec_id.startswith("T-GW"):   return "gateway"
    if spec_id.startswith("T-AU-L"): return "audit-log"
    if spec_id.startswith("T-AU"):   return "auth-service"
    if spec_id.startswith("T-CO"):   return "core-service"
    if spec_id.startswith("T-NO"):   return "notification-service"
    if spec_id.startswith("T-RC"):   return "recertification"
    if spec_id.startswith("T-BI"):   return "bulk-import"
    if spec_id.startswith("T-PD"):   return "pdf-lesson"
    if spec_id.startswith("T-CT"):   return "categories-tags"
    if spec_id.startswith("T-DB"):   return "dashboards"
    if spec_id.startswith("T-SD"):   return "soft-deletes"
    return "other"


def main() -> int:
    spec_ids = load_spec_ids()
    if not spec_ids:
        print("ERROR: no spec IDs found in project_docs/tests.md", file=sys.stderr)
        return 2

    covered: dict[str, list[str]] = {}  # spec_id -> [test_file::test_name]
    for path in walk_test_files():
        rel = path.relative_to(REPO_ROOT)
        for func_name, ids in extract_covers(path):
            for sid in ids:
                covered.setdefault(sid, []).append(f"{rel}::{func_name}")

    covered_set = set(covered.keys()) & spec_ids
    missing = sorted(spec_ids - covered_set)
    extra = sorted(set(covered.keys()) - spec_ids)  # tagged in tests but not in spec

    print("# Spec Coverage Map")
    print()
    print(f"- Total spec IDs in tests.md: **{len(spec_ids)}**")
    print(f"- Covered: **{len(covered_set)}** ({len(covered_set) * 100 // len(spec_ids)}%)")
    print(f"- Missing: **{len(missing)}**")
    print(f"- Tagged-but-not-in-spec: **{len(extra)}**")
    print()

    # Missing by category
    by_cat: dict[str, list[str]] = {}
    for sid in missing:
        by_cat.setdefault(categorize(sid), []).append(sid)
    print("## Missing by category")
    for cat, ids in sorted(by_cat.items()):
        print(f"- {cat}: {len(ids)}")
    print()

    print("## Missing spec IDs")
    for sid in missing:
        print(f"- `{sid}` ({categorize(sid)})")
    print()

    if extra:
        print("## Tagged in tests but not in tests.md (add to spec?)")
        for sid in extra:
            print(f"- `{sid}` — covered by {', '.join(covered[sid])}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it manually to verify output**

Run:
```bash
source tests/.venv/bin/activate
python -m tests._support.coverage_map | head -40
```
Expected: a Markdown report. Because no tests have been annotated yet, "Covered: 0".

- [ ] **Step 3: Commit**

```bash
git add tests/_support/coverage_map.py
git commit -m "test(infra): add spec-ID coverage map tool

Walks tests/ and app/<svc>/tests/, parses 'Covers: T-XX-NN' from
docstrings, compares against the spec ID list in project_docs/tests.md,
prints a Markdown summary with per-category breakdown and a list of
missing IDs.
"
```

---

## Task 20: Wire `--coverage-map` flag in runner

**Files:** modify `tests/run_tests.sh`

- [ ] **Step 1: Verify the flag is already wired**

The runner from Task 15 already has the `--coverage-map` flag and calls `python -m tests._support.coverage_map > "$ARTIFACTS_DIR/coverage_map.md"`. Verify:

Run:
```bash
./tests/run_tests.sh --smoke --coverage-map
```
Expected: smoke runs, then `tests/_artifacts/coverage_map.md` is created and printed.

- [ ] **Step 2: Verify the file exists and is non-empty**

Run:
```bash
test -s tests/_artifacts/coverage_map.md && echo "exists and non-empty"
```
Expected: `exists and non-empty`.

- [ ] **Step 3: No commit needed**

The wiring was completed in Task 15. This task is verification only.

---

## Task 21: Annotate auth_service existing tests with spec IDs

**Files:**
- Modify: `app/auth_service/tests/api/test_auth.py`
- Modify: `app/auth_service/tests/api/test_invite.py`
- Modify: `app/auth_service/tests/api/test_password.py`
- Modify: `app/auth_service/tests/api/test_heartbeat.py`
- Modify: `app/auth_service/tests/api/test_bulk_import.py`

The pattern: open each test file, read each test function, identify which spec ID(s) from `project_docs/tests.md` §2 (Auth Service) it covers, and add a `Covers: T-XX-NN` line as the first line of the docstring.

- [ ] **Step 1: Open `app/auth_service/tests/api/test_auth.py` and walk every test function**

For each test function, consult `project_docs/tests.md` §2.1 (Login & Redirection) and §2.2 (Tenant Selection) and §2.3 (JWT Refresh) to find the matching `T-AU-NN` ID.

Example transformation:

Before:
```python
async def test_login_valid_password(client):
    # ...
```

After:
```python
async def test_login_valid_password(client):
    """Covers: T-AU-01"""
    # ...
```

If a test covers behavior not in the spec, either:
- Add `@pytest.mark.no_spec` with a one-line comment explaining what it covers, **or**
- Add a new T-AU-NN row to `project_docs/tests.md` and reference it.

- [ ] **Step 2: Apply the same pattern to `test_invite.py`**

Use spec IDs T-AU-19 through T-AU-30 (Magic Link / Onboarding) and T-AU-41 through T-AU-44 (SysAdmin Invite) from `project_docs/tests.md` §2.4 and §2.7.

- [ ] **Step 3: Apply to `test_password.py`**

Use T-AU-31 through T-AU-34 from §2.5 (Password Reset).

- [ ] **Step 4: Apply to `test_heartbeat.py`**

Use T-AU-35 through T-AU-40 from §2.6 (Heartbeat).

- [ ] **Step 5: Apply to `test_bulk_import.py`**

Use T-BI-01 through T-BI-10 from §5.2 (Bulk User Import).

- [ ] **Step 6: Verify by re-running the coverage map**

Run:
```bash
source tests/.venv/bin/activate
python -m tests._support.coverage_map | head -20
```
Expected: `Covered` count increases proportionally to the auth_service tests annotated.

- [ ] **Step 7: Commit**

```bash
git add app/auth_service/tests/
git commit -m "test(auth): annotate existing tests with spec IDs from tests.md

Each test function now has 'Covers: T-XX-NN' on the first line of its
docstring. Coverage map tool picks these up to compute spec coverage.
No test logic changed.
"
```

---

## Task 22: Annotate core_service existing tests with spec IDs

**Files:**
- Modify: `app/core_service/tests/api/test_certificates.py`
- Modify: `app/core_service/tests/api/test_dashboards.py`
- Modify: `app/core_service/tests/api/test_isolation.py`
- Modify: `app/core_service/tests/api/test_progress.py`
- Modify: `app/core_service/tests/api/test_trainings.py`
- Modify: `app/core_service/tests/api/test_video_progress.py`

- [ ] **Step 1: Apply the same annotation pattern as Task 21**

Match each test to spec IDs from `project_docs/tests.md` §3 (Core Service):
- `test_trainings.py` → §3.5 (Trainings, T-CO-36 to T-CO-52) and §3.6 (Modules/Chapters/Lessons, T-CO-53 to T-CO-63)
- `test_progress.py` → §3.8 (Progress Tracking, T-CO-74 to T-CO-87) and §3.9 (Pushback, T-CO-88 to T-CO-93)
- `test_video_progress.py` → T-CO-79 to T-CO-83
- `test_certificates.py` → §3.10 (T-CO-94 to T-CO-105)
- `test_dashboards.py` → §5.5 (T-DB-01 to T-DB-09)
- `test_isolation.py` → cross-cutting tenant isolation; spec IDs are scattered (T-CO-11, T-CO-22, T-CO-30, T-CO-47, T-CO-87, etc.)

Example transformation:

Before:
```python
async def test_creator_cannot_publish_other_owners_training(client):
    # ...
```

After:
```python
async def test_creator_cannot_publish_other_owners_training(client):
    """Covers: T-CO-42"""
    # ...
```

- [ ] **Step 2: Verify the coverage map updates**

Run:
```bash
source tests/.venv/bin/activate
python -m tests._support.coverage_map | head -20
```

- [ ] **Step 3: Commit**

```bash
git add app/core_service/tests/
git commit -m "test(core): annotate existing tests with spec IDs from tests.md"
```

---

## Task 23: Annotate notification_service existing tests with spec IDs

**Files:**
- Modify: `app/notification_service/tests/api/test_notifications.py`
- Modify: `app/notification_service/tests/api/test_scheduler.py`

- [ ] **Step 1: Apply the annotation pattern**

Match each test to spec IDs from `project_docs/tests.md` §4 (Notification Service):
- `test_notifications.py` → §4.1 (T-NO-01 to T-NO-11)
- `test_scheduler.py` → §4.2 (T-NO-12 to T-NO-19) and §5.1 (T-RC-01 to T-RC-07)

- [ ] **Step 2: Verify coverage map updates**

Run:
```bash
source tests/.venv/bin/activate
python -m tests._support.coverage_map | head -20
```

- [ ] **Step 3: Commit**

```bash
git add app/notification_service/tests/
git commit -m "test(notification): annotate existing tests with spec IDs from tests.md"
```

---

## Task 24: Wave 1 verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full Wave 1 exit criterion**

Run:
```bash
./tests/run_tests.sh --unit --coverage-map -v
```
Expected:
- All annotated unit tests run (some may fail; that's pre-existing)
- `tests/_artifacts/coverage_map.md` exists with a non-zero Covered count
- `tests/_artifacts/report-unit-*.html` exists for each service

- [ ] **Step 2: Sanity-check coverage numbers**

Run:
```bash
cat tests/_artifacts/coverage_map.md | head -20
```
Expected: A "Covered: NN (XX%)" line. The actual percentage depends on how thoroughly the existing tests map to spec IDs — typical first-pass result is 25-45%.

- [ ] **Step 3: Inspect the missing list**

Run:
```bash
grep -c "^- \`" tests/_artifacts/coverage_map.md
```
Expected: a number matching the "Missing" count from the summary. This list is the input to Plan 2 (security boundaries / Wave 2 + 3).

- [ ] **Step 4: Tag the Wave 1 milestone (optional)**

Run:
```bash
git tag wave-1-complete
```

- [ ] **Step 5: Update `tests/README.md` with the coverage baseline**

Open `tests/README.md` and append a section:

```markdown
## Coverage baseline

As of <today's date>: `tests/_artifacts/coverage_map.md` reports
**NN / 247** spec IDs covered (XX%). The "Missing spec IDs" list at the
end of that file is the backlog for Plan 2 onward.
```

Replace `<today's date>`, NN, and XX with the actual values from `coverage_map.md`.

- [ ] **Step 6: Commit**

```bash
git add tests/README.md
git commit -m "docs(tests): record Wave 1 coverage baseline in README"
```

---

# Plan Complete

After Task 24:

- `./tests/run_tests.sh --smoke` passes against a fresh stack (Wave 0 ✓)
- `./tests/run_tests.sh --unit` runs all existing unit tests through the new runner (Wave 1 ✓)
- `./tests/run_tests.sh --coverage-map` produces a measurable spec coverage report (Wave 1 ✓)
- `tests/_artifacts/` contains HTML report, JUnit XML, coverage map for every run
- The notification worker emits `email_suppressed` log lines that tests can assert on

**Next plan to write:** Plan 2 — Security Boundaries (Wave 2 + Wave 3), driven by the "Missing spec IDs" list under categories `auth-service`, `core-service`, `notification-service` with category `isolation` or `auth`.

---

# Self-review (for the plan author)

- ✅ Every requirement in spec Section 10 Waves 0 and 1 maps to at least one task: scaffolding (T1), `_support/*` (T2-T8, T11, T19), runner (T15), email log (T10, T11), smoke tests (T4, T12, T13, T14), unit collection (T17), coverage map (T19, T20), annotation passes (T21-T23), exit verification (T16, T24).
- ✅ No placeholders ("TBD", "TODO", "implement later"): every code block has runnable code; every test has an assertion; every command has expected output.
- ✅ Type/name consistency: `gateway_client` is consistently a function returning `AsyncClient`; `UserHandle` defined in `auth.py` is the one returned by all `as_*()` wrappers; `ensure_stack_up`, `reset_databases`, `ensure_bootstrap_sysadmin`, `clear_email_log`, `assert_email_sent` are referenced with consistent signatures across tasks.
- ⚠️ Two implementation-time decisions are flagged as discoverable: (1) whether `app/auth_service/seed_data.py` already creates a bootstrap SysAdmin (Task 6 Step 1 inspects and adds if missing), (2) whether `app/auth_service` already has a `User` model importable for the test-only activation endpoint (Task 8 Step 2 says "match what other endpoints in the file do"). These cannot be resolved without reading the actual file at implementation time — appropriate as task-time decisions, not plan-time gaps.
