# Auth Service Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all auth service correctness bugs and missing features: token expiry consistency (48h), inactive user re-invite, login email normalization, tenant listing filter, self-service password reset, heartbeat endpoint, and bulk CSV import. Remove the illegal admin password-reset endpoint. Write the full T-AU-* test suite.

**Architecture:** All changes are inside `app/auth_service/`. Each bug is isolated to a single endpoint or function. Tests live in `app/auth_service/tests/` using pytest + httpx AsyncClient against a real in-memory SQLite or test Postgres DB. The test conftest creates the DB schema and tears down after each test.

**Tech Stack:** FastAPI, SQLAlchemy (async), pytest, httpx, alembic, Mailgun (mocked in tests with `USE_MAILGUN=False`)

**Run all tests:** `docker compose exec auth-service pytest tests/ -v`
**Run one file:** `docker compose exec auth-service pytest tests/api/test_auth.py -v`

---

## File Map

| File | Action |
|---|---|
| `app/auth_service/tests/conftest.py` | Create — DB setup, JWT helpers, test client factory |
| `app/auth_service/tests/api/test_auth.py` | Create — T-AU-01 to T-AU-17 (login, tenant select, JWT, refresh) |
| `app/auth_service/tests/api/test_invite.py` | Create — T-AU-18 to T-AU-30 (invite, magic link, re-invite, token expiry) |
| `app/auth_service/tests/api/test_password.py` | Create — T-AU-31 to T-AU-34 (self-service forgot-password, reset) |
| `app/auth_service/tests/api/test_heartbeat.py` | Create — T-AU-35 to T-AU-37 (heartbeat, new_token header) |
| `app/auth_service/tests/api/test_bulk_import.py` | Create — T-BI-01 to T-BI-10 |
| `app/auth_service/app/api/v1/endpoints/auth.py` | Modify — login email normalization, zero-membership block, branding in select-tenant response |
| `app/auth_service/app/api/v1/endpoints/users.py` | Modify — fix all invite expiry to 48h, fix re-invite is_active, remove admin reset endpoint, fix NameError in admin_invite_to_tenant, fix manager self-exclusion, add bulk import endpoint |
| `app/auth_service/app/api/v1/endpoints/heartbeat.py` | Create — `POST /auth/heartbeat` |
| `app/auth_service/app/api/v1/endpoints/password_reset.py` | Create — `POST /auth/forgot-password`, `POST /auth/reset-password` |
| `app/auth_service/app/api/v1/api.py` | Modify — register heartbeat and password_reset routers |
| `app/auth_service/app/models/membership.py` | Modify — rename `DEACTIVATED` → `Inactive` in `UserStatus` enum |
| `app/auth_service/alembic/versions/` | Create — migration for UserStatus enum rename |

---

### Task 1: Set up test infrastructure

**Files:**
- Create: `app/auth_service/tests/__init__.py`
- Create: `app/auth_service/tests/api/__init__.py`
- Create: `app/auth_service/tests/conftest.py`

- [ ] **Step 1: Create `tests/conftest.py`**

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone
import jwt
import uuid

from main import app
from app.db.session import get_db
from app.models.base import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_EXTERNAL_JWT_SECRET = "test-external-secret"
TEST_INTERNAL_JWT_SECRET = "test-internal-secret"

@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()

def make_jwt(user_id: str, tenant_id: str | None, roles: list[str], secret: str = TEST_EXTERNAL_JWT_SECRET, expires_in: int = 3600) -> str:
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": roles,
        "is_global": tenant_id is None,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def make_sysadmin_jwt(user_id: str | None = None, secret: str = TEST_EXTERNAL_JWT_SECRET) -> str:
    return make_jwt(user_id or str(uuid.uuid4()), None, ["SysAdmin"], secret)

def make_manager_jwt(user_id: str, tenant_id: str, secret: str = TEST_EXTERNAL_JWT_SECRET) -> str:
    return make_jwt(user_id, tenant_id, ["Business Manager"], secret)
```

- [ ] **Step 2: Install test dependencies in `requirements.txt`**

Ensure these are in `app/auth_service/requirements.txt`:
```
pytest==7.4.3
pytest-asyncio==0.23.5
httpx==0.26.0
aiosqlite==0.19.0
pytest-cov==4.1.0
```

- [ ] **Step 3: Verify conftest loads without import errors**

```bash
docker compose exec auth-service pytest tests/conftest.py --collect-only 2>&1 | head -20
```

Expected: no import errors.

- [ ] **Step 4: Commit**

```bash
git add app/auth_service/tests/
git commit -m "test: add auth service test infrastructure and conftest"
```

---

### Task 2: Fix login email normalization and zero-membership block

**Files:**
- Modify: `app/auth_service/app/api/v1/endpoints/auth.py`

- [ ] **Step 1: Write the failing tests**

Create `app/auth_service/tests/api/test_auth.py`:

```python
import pytest
from tests.conftest import make_jwt
import uuid

# T-AU-08: Login normalizes email to lowercase
@pytest.mark.asyncio
async def test_login_case_insensitive(client, db_session):
    # Register a user with lowercase email via direct DB insert
    from app.models.user import User
    import bcrypt
    user = User(
        id=str(uuid.uuid4()),
        email="user@example.com",
        username="testuser",
        password_hash=bcrypt.hashpw(b"Password1!", bcrypt.gensalt()).decode(),
        first_name="Test",
        last_name="User",
        is_sysadmin=False,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", json={
        "email": "User@EXAMPLE.COM", "password": "Password1!"
    })
    assert resp.status_code == 200

# T-AU-XX: User with zero tenant memberships is blocked at login
@pytest.mark.asyncio
async def test_login_no_memberships_blocked(client, db_session):
    from app.models.user import User
    import bcrypt
    user = User(
        id=str(uuid.uuid4()),
        email="orphan@example.com",
        username="orphan",
        password_hash=bcrypt.hashpw(b"Password1!", bcrypt.gensalt()).decode(),
        first_name="Orphan",
        last_name="User",
        is_sysadmin=False,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", json={
        "email": "orphan@example.com", "password": "Password1!"
    })
    assert resp.status_code == 403
    assert "not associated" in resp.json()["detail"].lower()
```

- [ ] **Step 2: Run to confirm failure**

```bash
docker compose exec auth-service pytest tests/api/test_auth.py -v 2>&1 | tail -20
```

Expected: both tests fail.

- [ ] **Step 3: Fix login endpoint in `auth.py`**

Find the login handler. Locate where `credentials.email` is compared to `User.email`. Add `.lower()` to both sides:

```python
# Before (example):
result = await db.execute(select(User).where(User.email == credentials.email))

# After:
result = await db.execute(
    select(User).where(User.email == credentials.email.lower().strip())
)
```

Also add the zero-membership block. Find the section that checks for inactive memberships and add a check above it:

```python
# After fetching the user and verifying password, before issuing token:
if not user.is_sysadmin:
    memberships = user.memberships  # or query if lazy loaded
    if not memberships:
        raise HTTPException(
            status_code=403,
            detail="Your account is not associated with any active organizations. Contact your administrator."
        )
    if all(not m.is_active for m in memberships):
        raise HTTPException(
            status_code=403,
            detail="Your account is not associated with any active organizations. Contact your administrator."
        )
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
docker compose exec auth-service pytest tests/api/test_auth.py -v 2>&1 | tail -10
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/auth_service/app/api/v1/endpoints/auth.py app/auth_service/tests/api/test_auth.py
git commit -m "fix: normalize login email, block zero-membership users (T-AU-08)"
```

---

### Task 3: Fix GET /auth/tenants membership filter and POST /auth/select-tenant branding response

**Files:**
- Modify: `app/auth_service/app/api/v1/endpoints/auth.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/api/test_auth.py`:

```python
# T-AU-09: GET /auth/tenants excludes tenants where membership is inactive
@pytest.mark.asyncio
async def test_tenants_excludes_inactive_membership(client, db_session):
    from app.models.user import User, TenantMembership, Tenant
    import bcrypt, uuid
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    tenant = Tenant(id=tenant_id, name="Active Tenant", slug="active-tenant", is_active=True, primary_color="#000", secondary_color="#fff")
    user = User(id=user_id, email="mem@example.com", username="mem", password_hash=bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode(), first_name="A", last_name="B", is_sysadmin=False, is_active=True)
    membership = TenantMembership(user_id=user_id, tenant_id=tenant_id, is_active=False, status="Inactive", is_employee=True)
    db_session.add_all([tenant, user, membership])
    await db_session.commit()

    token = make_jwt(user_id, None, [])
    resp = await client.get("/api/v1/auth/tenants", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0  # inactive membership — tenant must not appear

# T-AU-11: POST /auth/select-tenant returns branding alongside the JWT
@pytest.mark.asyncio
async def test_select_tenant_returns_branding(client, db_session):
    from app.models.user import User, TenantMembership, Tenant
    import bcrypt, uuid
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    tenant = Tenant(id=tenant_id, name="Brand Tenant", slug="brand-tenant", is_active=True, primary_color="#FF5733", secondary_color="#C0C0C0")
    user = User(id=user_id, email="brand@example.com", username="brand", password_hash=bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode(), first_name="A", last_name="B", is_sysadmin=False, is_active=True)
    membership = TenantMembership(user_id=user_id, tenant_id=tenant_id, is_active=True, status="Active", is_employee=True)
    db_session.add_all([tenant, user, membership])
    await db_session.commit()

    token = make_jwt(user_id, None, [])
    resp = await client.post("/api/v1/auth/select-tenant", json={"tenant_id": tenant_id}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["branding"]["primary_color"] == "#FF5733"
    assert data["branding"]["tenant_name"] == "Brand Tenant"
```

- [ ] **Step 2: Run to confirm failure**

```bash
docker compose exec auth-service pytest tests/api/test_auth.py::test_tenants_excludes_inactive_membership tests/api/test_auth.py::test_select_tenant_returns_branding -v
```

Expected: both fail.

- [ ] **Step 3: Fix `GET /auth/tenants` to filter by `TenantMembership.is_active`**

In `auth.py`, find the `GET /auth/tenants` handler and add `TenantMembership.is_active == True` to the join condition or where clause:

```python
# Before (example):
.join(TenantMembership, TenantMembership.tenant_id == Tenant.id)
.where(TenantMembership.user_id == current_user.id)

# After:
.join(TenantMembership, TenantMembership.tenant_id == Tenant.id)
.where(
    TenantMembership.user_id == current_user.id,
    TenantMembership.is_active == True,
    Tenant.is_active == True,
)
```

- [ ] **Step 4: Fix `POST /auth/select-tenant` response to include branding**

Update the response schema or return value to include branding:

```python
# In the select-tenant handler, after issuing the token, also fetch tenant:
tenant_row = await db.get(Tenant, tenant_id)

return {
    "access_token": access_token,
    "token_type": "bearer",
    "branding": {
        "tenant_id": tenant_id,
        "tenant_name": tenant_row.name,
        "primary_color": tenant_row.primary_color,
        "secondary_color": tenant_row.secondary_color,
        "logo_url": tenant_row.logo_url if hasattr(tenant_row, "logo_url") else None,
    }
}
```

Update the Pydantic response schema (`Token` or similar) to include `branding: dict | None = None`.

- [ ] **Step 5: Run tests to confirm pass**

```bash
docker compose exec auth-service pytest tests/api/test_auth.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/auth_service/app/api/v1/endpoints/auth.py
git commit -m "fix: filter tenants by membership.is_active, return branding in select-tenant (T-AU-09, T-AU-11)"
```

---

### Task 4: Fix all invite token expiry to 48 hours

**Files:**
- Modify: `app/auth_service/app/api/v1/endpoints/users.py`

- [ ] **Step 1: Write failing test**

Create `app/auth_service/tests/api/test_invite.py`:

```python
import pytest
from datetime import datetime, timezone
from tests.conftest import make_manager_jwt, make_sysadmin_jwt
import uuid

# T-AU-18: Manager invite token expires in exactly 48 hours
@pytest.mark.asyncio
async def test_manager_invite_token_expires_48h(client, db_session):
    from app.models.user import User, Tenant, TenantMembership
    import bcrypt
    tenant_id = str(uuid.uuid4())
    manager_id = str(uuid.uuid4())
    tenant = Tenant(id=tenant_id, name="T1", slug="t1", is_active=True, primary_color="#000", secondary_color="#fff")
    manager = User(id=manager_id, email="mgr@example.com", username="mgr", password_hash=bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode(), first_name="M", last_name="G", is_sysadmin=False, is_active=True)
    membership = TenantMembership(user_id=manager_id, tenant_id=tenant_id, is_active=True, status="Active", is_business_manager=True, is_employee=True)
    db_session.add_all([tenant, manager, membership])
    await db_session.commit()

    token = make_manager_jwt(manager_id, tenant_id)
    resp = await client.post("/api/v1/users/invite", json={
        "email": "newemployee@example.com",
        "first_name": "New",
        "last_name": "Employee",
        "is_business_manager": False,
        "is_training_creator": False,
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201

    # Fetch the token from DB and check its expiry
    from app.models.user import RegistrationToken
    from sqlalchemy import select
    result = await db_session.execute(select(RegistrationToken).order_by(RegistrationToken.created_at.desc()))
    reg_token = result.scalars().first()
    assert reg_token is not None
    diff = reg_token.expires_at - datetime.now(timezone.utc)
    # Should be between 47h55m and 48h05m
    assert 47 * 3600 < diff.total_seconds() < 48 * 3600 + 300
```

- [ ] **Step 2: Run to confirm failure**

```bash
docker compose exec auth-service pytest tests/api/test_invite.py::test_manager_invite_token_expires_48h -v
```

Expected: fails (token is 24h, not 48h).

- [ ] **Step 3: Fix all invite expiry in `users.py`**

Search for all occurrences of `timedelta(hours=24)` and `timedelta(days=7)` and `timedelta(hours=72)` used as invite token expiry. Replace each with `timedelta(hours=48)`:

```bash
grep -n "timedelta" app/auth_service/app/api/v1/endpoints/users.py
```

For each invite path (line numbers will vary):
```python
# Find lines like:
expires = datetime.now(timezone.utc) + timedelta(hours=24)
# or:
expires = datetime.now(timezone.utc) + timedelta(days=7)

# Replace with:
expires = datetime.now(timezone.utc) + timedelta(hours=48)
```

The paths to fix are:
- `invite_user` (Business Manager invite) — currently 24h
- `create_user` (SysAdmin creates user in tenant) — currently 7 days  
- `regenerate_registration_token` — currently 7 days
- Tenant creation initial manager invite — currently 72h
- (Keep `invite_sysadmin` at 48h if it uses a different policy, or align to 48h)

- [ ] **Step 4: Run test to confirm pass**

```bash
docker compose exec auth-service pytest tests/api/test_invite.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/auth_service/app/api/v1/endpoints/users.py app/auth_service/tests/api/test_invite.py
git commit -m "fix: standardize all invite token expiry to 48h (BR-103)"
```

---

### Task 5: Fix re-invite of inactive user — set is_active=True

**Files:**
- Modify: `app/auth_service/app/api/v1/endpoints/users.py`

- [ ] **Step 1: Write failing test**

Add to `tests/api/test_invite.py`:

```python
# T-AU-XX (BR-103a): Re-invite of inactive user restores is_active and status
@pytest.mark.asyncio
async def test_reinvite_inactive_user_restores_access(client, db_session):
    from app.models.user import User, Tenant, TenantMembership
    import bcrypt
    tenant_id = str(uuid.uuid4())
    manager_id = str(uuid.uuid4())
    employee_id = str(uuid.uuid4())
    tenant = Tenant(id=tenant_id, name="T2", slug="t2", is_active=True, primary_color="#000", secondary_color="#fff")
    manager = User(id=manager_id, email="mgr2@example.com", username="mgr2", password_hash=bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode(), first_name="M", last_name="G", is_sysadmin=False, is_active=True)
    manager_mem = TenantMembership(user_id=manager_id, tenant_id=tenant_id, is_active=True, status="Active", is_business_manager=True, is_employee=True)
    employee = User(id=employee_id, email="inactive@example.com", username="inactive", password_hash=bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode(), first_name="I", last_name="E", is_sysadmin=False, is_active=True)
    emp_mem = TenantMembership(user_id=employee_id, tenant_id=tenant_id, is_active=False, status="Inactive", is_employee=True)
    db_session.add_all([tenant, manager, manager_mem, employee, emp_mem])
    await db_session.commit()

    token = make_manager_jwt(manager_id, tenant_id)
    resp = await client.post("/api/v1/users/invite", json={
        "email": "inactive@example.com",
        "first_name": "I",
        "last_name": "E",
        "is_business_manager": False,
        "is_training_creator": False,
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in (200, 201)

    # Verify membership is now active
    await db_session.refresh(emp_mem)
    assert emp_mem.is_active == True
    assert emp_mem.status == "Active"
```

- [ ] **Step 2: Run to confirm failure**

```bash
docker compose exec auth-service pytest tests/api/test_invite.py::test_reinvite_inactive_user_restores_access -v
```

- [ ] **Step 3: Fix the re-invite logic in `users.py`**

Find the `invite_user` function. Locate the block that handles an existing user with an inactive membership. It currently updates `membership.status` but not `membership.is_active`. Add the missing update:

```python
# In the existing-user re-invite branch:
if existing_membership and not existing_membership.is_active:
    existing_membership.is_active = True          # THIS LINE IS MISSING — add it
    existing_membership.status = "Active"
    existing_membership.is_business_manager = invite_data.is_business_manager
    existing_membership.is_training_creator = invite_data.is_training_creator
    await db.commit()
    # publish EMPLOYEE_REACTIVATED event
    return {"message": "User reactivated and access restored"}
```

- [ ] **Step 4: Run test to confirm pass**

```bash
docker compose exec auth-service pytest tests/api/test_invite.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/auth_service/app/api/v1/endpoints/users.py
git commit -m "fix: re-invite of inactive user now sets membership.is_active=True (BR-103a)"
```

---

### Task 6: Fix NameError in admin invite, remove illegal admin password reset

**Files:**
- Modify: `app/auth_service/app/api/v1/endpoints/users.py`

- [ ] **Step 1: Fix NameError in `admin_invite_to_tenant` (around line 1330)**

Find the `admin_invite_to_tenant` function. Locate where `invite_url` is used but not defined. Add the missing construction:

```python
# After generating token_str and expires:
token_str = str(uuid.uuid4())  # or however it's currently generated
expires = datetime.now(timezone.utc) + timedelta(hours=48)

# Add this missing line:
invite_url = f"{settings.FRONTEND_URL}/signup?token={token_str}"

# Then the rest of the function uses invite_url correctly
```

- [ ] **Step 2: Write a test that exercises admin invite to confirm no 500**

Add to `tests/api/test_invite.py`:

```python
# T-AU-28: SysAdmin can invite a new user to a specific tenant without 500
@pytest.mark.asyncio
async def test_sysadmin_invite_new_user_no_error(client, db_session):
    from app.models.user import Tenant
    tenant_id = str(uuid.uuid4())
    tenant = Tenant(id=tenant_id, name="T3", slug="t3", is_active=True, primary_color="#000", secondary_color="#fff")
    db_session.add(tenant)
    await db_session.commit()

    token = make_sysadmin_jwt()
    resp = await client.post("/api/v1/users/admin/invite-to-tenant", json={
        "email": "newhire@example.com",
        "first_name": "New",
        "last_name": "Hire",
        "tenant_id": tenant_id,
        "is_business_manager": False,
        "is_training_creator": False,
    }, headers={"Authorization": f"Bearer {token}"})
    # Must not be 500
    assert resp.status_code in (200, 201)
```

- [ ] **Step 3: Remove `POST /users/{user_id}/reset-password` endpoint (violates BR-504)**

Find the `reset_user_password` function (~line 1140) and delete it entirely, along with its route decorator. Also remove it from any `__all__` or router registration if present.

- [ ] **Step 4: Write a test confirming admin reset is rejected**

Add to `tests/api/test_password.py`:

```python
import pytest
from tests.conftest import make_sysadmin_jwt
import uuid

# T-AU-34: Admin cannot reset a user's password via API (BR-504)
@pytest.mark.asyncio
async def test_admin_cannot_reset_password(client):
    token = make_sysadmin_jwt()
    user_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/users/{user_id}/reset-password",
        json={"new_password": "NewPass1!"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404  # endpoint does not exist
```

- [ ] **Step 5: Run tests**

```bash
docker compose exec auth-service pytest tests/api/test_invite.py tests/api/test_password.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/auth_service/app/api/v1/endpoints/users.py app/auth_service/tests/api/test_password.py
git commit -m "fix: patch admin_invite NameError, remove illegal admin password reset (BR-504)"
```

---

### Task 7: Add self-service password reset

**Files:**
- Create: `app/auth_service/app/api/v1/endpoints/password_reset.py`
- Modify: `app/auth_service/app/api/v1/api.py`
- Modify: `app/auth_service/app/models/user.py` (or wherever PasswordResetToken model should live)

- [ ] **Step 1: Write failing tests**

In `app/auth_service/tests/api/test_password.py`:

```python
# T-AU-31: POST /auth/forgot-password accepts valid email
@pytest.mark.asyncio
async def test_forgot_password_valid_email(client, db_session):
    from app.models.user import User
    import bcrypt, uuid
    user = User(id=str(uuid.uuid4()), email="forgot@example.com", username="forgot", password_hash=bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode(), first_name="F", last_name="G", is_sysadmin=False, is_active=True)
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/forgot-password", json={"email": "forgot@example.com"})
    assert resp.status_code == 200

# T-AU-32: POST /auth/forgot-password returns 200 even for unknown email (no enumeration)
@pytest.mark.asyncio
async def test_forgot_password_unknown_email_returns_200(client):
    resp = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 200

# T-AU-33: POST /auth/reset-password with valid token changes password
@pytest.mark.asyncio
async def test_reset_password_valid_token(client, db_session):
    from app.models.user import User, PasswordResetToken
    import bcrypt, uuid
    from datetime import datetime, timezone, timedelta
    user_id = str(uuid.uuid4())
    user = User(id=user_id, email="reset@example.com", username="reset", password_hash=bcrypt.hashpw(b"OldPass1!", bcrypt.gensalt()).decode(), first_name="R", last_name="S", is_sysadmin=False, is_active=True)
    token_value = str(uuid.uuid4())
    reset_token = PasswordResetToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token=token_value,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_used=False,
    )
    db_session.add_all([user, reset_token])
    await db_session.commit()

    resp = await client.post("/api/v1/auth/reset-password", json={
        "token": token_value, "new_password": "NewSecure1!"
    })
    assert resp.status_code == 200

    # Verify old password no longer works
    login_resp = await client.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": "OldPass1!"})
    assert login_resp.status_code == 401
```

- [ ] **Step 2: Run to confirm all three fail**

```bash
docker compose exec auth-service pytest tests/api/test_password.py -v 2>&1 | tail -20
```

- [ ] **Step 3: Create `PasswordResetToken` model** (add to existing user models file or its own file)

```python
# In app/models/password_reset.py (or add to user.py):
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default="now()")
```

- [ ] **Step 4: Generate and apply migration**

```bash
docker compose exec auth-service alembic revision --autogenerate -m "add password_reset_tokens table"
docker compose exec auth-service alembic upgrade head
```

- [ ] **Step 5: Create `password_reset.py` endpoint**

```python
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone, timedelta
import uuid, bcrypt

from app.db.session import get_db
from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.core.config import settings
# Import your email sending utility (USE_MAILGUN=False in dev suppresses sends)
from app.utils.email import send_password_reset_email

router = APIRouter()

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email.lower().strip()))
    user = result.scalars().first()
    if user:
        token_value = str(uuid.uuid4())
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        reset_token = PasswordResetToken(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token=token_value,
            expires_at=expires,
            is_used=False,
        )
        db.add(reset_token)
        await db.commit()
        await send_password_reset_email(user.email, token_value)
    # Always return 200 to prevent email enumeration
    return {"message": "If that email is registered, a reset link has been sent."}

@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token == req.token,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
    )
    reset_token = result.scalars().first()
    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    user = await db.get(User, reset_token.user_id)
    if not user:
        raise HTTPException(status_code=404)

    user.password_hash = bcrypt.hashpw(req.new_password.encode(), bcrypt.gensalt()).decode()
    reset_token.is_used = True
    await db.commit()
    return {"message": "Password updated successfully."}
```

- [ ] **Step 6: Register router in `api.py`**

```python
from app.api.v1.endpoints import auth, users, tenants, groups, assignments, media, password_reset

api_router.include_router(password_reset.router, prefix="/auth", tags=["password-reset"])
```

- [ ] **Step 7: Run tests**

```bash
docker compose exec auth-service pytest tests/api/test_password.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 8: Commit**

```bash
git add app/auth_service/app/api/v1/endpoints/password_reset.py app/auth_service/app/api/v1/api.py app/auth_service/app/models/ app/auth_service/alembic/versions/
git commit -m "feat: add self-service password reset (forgot-password + reset-password) (T-AU-31-33)"
```

---

### Task 8: Add heartbeat endpoint

**Files:**
- Create: `app/auth_service/app/api/v1/endpoints/heartbeat.py`
- Modify: `app/auth_service/app/api/v1/api.py`
- Create: `app/auth_service/tests/api/test_heartbeat.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest
from tests.conftest import make_jwt
from datetime import datetime, timezone, timedelta
import jwt as pyjwt, uuid

# T-AU-35: POST /auth/heartbeat returns 200 with valid training-scope JWT
@pytest.mark.asyncio
async def test_heartbeat_valid_token(client):
    user_id = str(uuid.uuid4())
    token = make_jwt(user_id, "tenant-1", ["Employee"])
    resp = await client.post("/api/v1/auth/heartbeat", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

# T-AU-36: Heartbeat returns new_token header when JWT expires within 10 minutes
@pytest.mark.asyncio
async def test_heartbeat_returns_new_token_when_near_expiry(client):
    user_id = str(uuid.uuid4())
    # Token that expires in 5 minutes
    from tests.conftest import TEST_EXTERNAL_JWT_SECRET
    token = make_jwt(user_id, "tenant-1", ["Employee"], expires_in=300)
    resp = await client.post("/api/v1/auth/heartbeat", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "new_token" in resp.headers

# T-AU-37: Heartbeat rejects expired token
@pytest.mark.asyncio
async def test_heartbeat_rejects_expired_token(client):
    from tests.conftest import TEST_EXTERNAL_JWT_SECRET
    payload = {
        "sub": str(uuid.uuid4()),
        "tenant_id": "t1",
        "roles": ["Employee"],
        "exp": datetime.now(timezone.utc) - timedelta(seconds=60),
    }
    token = pyjwt.encode(payload, TEST_EXTERNAL_JWT_SECRET, algorithm="HS256")
    resp = await client.post("/api/v1/auth/heartbeat", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
```

- [ ] **Step 2: Run to confirm failure**

```bash
docker compose exec auth-service pytest tests/api/test_heartbeat.py -v 2>&1 | tail -15
```

- [ ] **Step 3: Create `heartbeat.py`**

```python
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
import jwt as pyjwt

from app.db.session import get_db
from app.core.config import settings
from app.core.deps import get_current_user

router = APIRouter()

NEAR_EXPIRY_SECONDS = 600  # 10 minutes

@router.post("/heartbeat")
async def heartbeat(response: Response, current_user=Depends(get_current_user)):
    payload = current_user.token_payload  # assumes get_current_user attaches decoded payload
    exp = payload.get("exp")
    if exp:
        remaining = exp - datetime.now(timezone.utc).timestamp()
        if remaining <= NEAR_EXPIRY_SECONDS:
            new_payload = {k: v for k, v in payload.items() if k != "exp"}
            new_payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=60)
            new_token = pyjwt.encode(new_payload, settings.EXTERNAL_JWT_SECRET, algorithm="HS256")
            response.headers["new_token"] = new_token
    return {"status": "ok"}
```

Note: `get_current_user` must attach `token_payload` to the returned user object. Inspect `app/core/deps.py` and modify `get_current_user` to store the decoded payload on the user or return it in a wrapper object if needed.

- [ ] **Step 4: Register router in `api.py`**

```python
from app.api.v1.endpoints import heartbeat

api_router.include_router(heartbeat.router, prefix="/auth", tags=["heartbeat"])
```

- [ ] **Step 5: Run tests**

```bash
docker compose exec auth-service pytest tests/api/test_heartbeat.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/auth_service/app/api/v1/endpoints/heartbeat.py app/auth_service/app/api/v1/api.py app/auth_service/tests/api/test_heartbeat.py
git commit -m "feat: add POST /auth/heartbeat with near-expiry new_token refresh (T-AU-35-37)"
```

---

### Task 9: Fix UserStatus enum — DEACTIVATED → Inactive

**Files:**
- Modify: `app/auth_service/app/models/user.py` (or wherever `UserStatus` is defined)
- Create: migration

- [ ] **Step 1: Find and rename the enum value**

```bash
grep -rn "DEACTIVATED\|Deactivated\|deactivated" app/auth_service/app/
```

In the model file, rename the enum value:
```python
# Before:
class UserStatus(str, enum.Enum):
    PENDING = "Pending"
    ACTIVE = "Active"
    DEACTIVATED = "Deactivated"

# After:
class UserStatus(str, enum.Enum):
    PENDING = "Pending"
    ACTIVE = "Active"
    INACTIVE = "Inactive"
```

- [ ] **Step 2: Find all usages of `UserStatus.DEACTIVATED` and replace with `UserStatus.INACTIVE`**

```bash
grep -rn "UserStatus.DEACTIVATED\|status.*DEACTIVATED\|status.*Deactivated" app/auth_service/app/
```

Replace each occurrence. Also update any string literals `"Deactivated"` → `"Inactive"` in comparison expressions.

- [ ] **Step 3: Generate and apply migration if using PostgreSQL enum type**

```bash
docker compose exec auth-service alembic revision --autogenerate -m "rename UserStatus DEACTIVATED to Inactive"
docker compose exec auth-service alembic upgrade head
```

If the enum is stored as VARCHAR (not a PostgreSQL native ENUM), no migration may be needed — just update existing data:
```sql
UPDATE tenant_memberships SET status = 'Inactive' WHERE status = 'Deactivated';
```

- [ ] **Step 4: Run full auth test suite**

```bash
docker compose exec auth-service pytest tests/ -v
```

- [ ] **Step 5: Commit**

```bash
git add app/auth_service/app/ app/auth_service/alembic/
git commit -m "fix: rename UserStatus.DEACTIVATED to Inactive to match spec (BR-202)"
```

---

### Task 10: Add Bulk CSV Import

**Files:**
- Modify: `app/auth_service/app/api/v1/endpoints/users.py`
- Create: `app/auth_service/tests/api/test_bulk_import.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest, io, csv
from tests.conftest import make_sysadmin_jwt
import uuid

def make_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["email", "first_name", "last_name", "is_business_manager", "is_training_creator"])
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode()

# T-BI-01: SysAdmin can upload a CSV and get a result report
@pytest.mark.asyncio
async def test_bulk_import_returns_report(client, db_session):
    from app.models.user import Tenant
    tenant_id = str(uuid.uuid4())
    tenant = Tenant(id=tenant_id, name="BulkT", slug="bulk-t", is_active=True, primary_color="#000", secondary_color="#fff")
    db_session.add(tenant)
    await db_session.commit()

    token = make_sysadmin_jwt()
    csv_data = make_csv([
        {"email": "a@example.com", "first_name": "A", "last_name": "A", "is_business_manager": "false", "is_training_creator": "false"},
        {"email": "b@example.com", "first_name": "B", "last_name": "B", "is_business_manager": "false", "is_training_creator": "false"},
    ])
    resp = await client.post(
        f"/api/v1/users/bulk-import?tenant_id={tenant_id}",
        files={"file": ("users.csv", csv_data, "text/csv")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "successes" in data
    assert "failures" in data
    assert len(data["successes"]) == 2

# T-BI-02: Non-sysadmin cannot access bulk import
@pytest.mark.asyncio
async def test_bulk_import_requires_sysadmin(client, db_session):
    from tests.conftest import make_manager_jwt
    import uuid
    token = make_manager_jwt(str(uuid.uuid4()), str(uuid.uuid4()))
    csv_data = make_csv([{"email": "x@example.com", "first_name": "X", "last_name": "X", "is_business_manager": "false", "is_training_creator": "false"}])
    resp = await client.post(
        f"/api/v1/users/bulk-import?tenant_id={str(uuid.uuid4())}",
        files={"file": ("users.csv", csv_data, "text/csv")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403

# T-BI-03: Invalid rows appear in failures, valid rows in successes (partial success)
@pytest.mark.asyncio
async def test_bulk_import_partial_success(client, db_session):
    from app.models.user import Tenant
    tenant_id = str(uuid.uuid4())
    tenant = Tenant(id=tenant_id, name="BulkT2", slug="bulk-t2", is_active=True, primary_color="#000", secondary_color="#fff")
    db_session.add(tenant)
    await db_session.commit()

    token = make_sysadmin_jwt()
    csv_data = make_csv([
        {"email": "good@example.com", "first_name": "Good", "last_name": "User", "is_business_manager": "false", "is_training_creator": "false"},
        {"email": "not-an-email", "first_name": "", "last_name": "", "is_business_manager": "false", "is_training_creator": "false"},
    ])
    resp = await client.post(
        f"/api/v1/users/bulk-import?tenant_id={tenant_id}",
        files={"file": ("users.csv", csv_data, "text/csv")},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["successes"]) == 1
    assert len(data["failures"]) == 1
    assert "invalid email" in data["failures"][0]["reason"].lower()
```

- [ ] **Step 2: Run to confirm all fail**

```bash
docker compose exec auth-service pytest tests/api/test_bulk_import.py -v 2>&1 | tail -20
```

- [ ] **Step 3: Add bulk import endpoint to `users.py`**

```python
import csv, io
from fastapi import UploadFile, File, Query as QueryParam
from pydantic import EmailStr, ValidationError as PydanticValidationError

@router.post("/bulk-import")
async def bulk_import_users(
    tenant_id: str = QueryParam(...),
    file: UploadFile = File(...),
    current_user=Depends(get_sysadmin),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="Tenant not found")

    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))

    successes = []
    failures = []
    required_fields = {"email", "first_name", "last_name"}

    for i, row in enumerate(reader, start=2):
        missing = required_fields - set(row.keys())
        if missing:
            failures.append({"row": i, "email": row.get("email", ""), "reason": f"Missing columns: {missing}"})
            continue

        email = row["email"].strip().lower()
        first_name = row["first_name"].strip()
        last_name = row["last_name"].strip()
        is_bm = row.get("is_business_manager", "false").lower() == "true"
        is_tc = row.get("is_training_creator", "false").lower() == "true"

        # Basic email validation
        import re
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            failures.append({"row": i, "email": email, "reason": "Invalid email format"})
            continue
        if not first_name or not last_name:
            failures.append({"row": i, "email": email, "reason": "first_name and last_name are required"})
            continue

        # Reuse invite logic: check if user exists, auto-link or create
        try:
            result = await _process_single_invite(db, email, first_name, last_name, tenant_id, is_bm, is_tc)
            successes.append({"row": i, "email": email, "result": result})
        except Exception as e:
            failures.append({"row": i, "email": email, "reason": str(e)})

    return {"successes": successes, "failures": failures, "total_rows": len(successes) + len(failures)}
```

The `_process_single_invite` helper should contain the same logic as the existing `invite_user` handler — check if user exists, auto-link if active, create magic link if new. Extract this shared logic into a private `async def _process_single_invite(db, email, first_name, last_name, tenant_id, is_bm, is_tc) -> str` function that returns a status string.

- [ ] **Step 4: Run tests**

```bash
docker compose exec auth-service pytest tests/api/test_bulk_import.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/auth_service/app/api/v1/endpoints/users.py app/auth_service/tests/api/test_bulk_import.py
git commit -m "feat: add SysAdmin bulk CSV user import with partial-success report (T-BI-01-T-BI-10)"
```

---

### Task 11: Fix manager self-exclusion and run full test suite

**Files:**
- Modify: `app/auth_service/app/api/v1/endpoints/users.py` (`list_tenant_users`)

- [ ] **Step 1: Write test**

Add to `tests/api/test_auth.py`:

```python
# T-AU-XX (BR-501): Manager is excluded from their own user list
@pytest.mark.asyncio
async def test_manager_excluded_from_own_user_list(client, db_session):
    from app.models.user import User, Tenant, TenantMembership
    import bcrypt, uuid
    tenant_id = str(uuid.uuid4())
    manager_id = str(uuid.uuid4())
    employee_id = str(uuid.uuid4())
    tenant = Tenant(id=tenant_id, name="T4", slug="t4", is_active=True, primary_color="#000", secondary_color="#fff")
    manager = User(id=manager_id, email="self@example.com", username="self", password_hash=bcrypt.hashpw(b"P1!", bcrypt.gensalt()).decode(), first_name="M", last_name="G", is_sysadmin=False, is_active=True)
    employee = User(id=employee_id, email="emp@example.com", username="emp", password_hash=bcrypt.hashpw(b"P1!", bcrypt.gensalt()).decode(), first_name="E", last_name="P", is_sysadmin=False, is_active=True)
    mgr_mem = TenantMembership(user_id=manager_id, tenant_id=tenant_id, is_active=True, status="Active", is_business_manager=True, is_employee=True)
    emp_mem = TenantMembership(user_id=employee_id, tenant_id=tenant_id, is_active=True, status="Active", is_employee=True)
    db_session.add_all([tenant, manager, employee, mgr_mem, emp_mem])
    await db_session.commit()

    token = make_manager_jwt(manager_id, tenant_id)
    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    user_ids = [u["id"] for u in resp.json()]
    assert manager_id not in user_ids
    assert employee_id in user_ids
```

- [ ] **Step 2: Fix `list_tenant_users` in `users.py`**

Add an exclusion filter for the current user:

```python
# In list_tenant_users, add to the where clause:
.where(
    TenantMembership.tenant_id == current_tenant_id,
    User.id != current_user.id,  # exclude the requesting manager
)
```

- [ ] **Step 3: Run the full test suite**

```bash
docker compose exec auth-service pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: all tests pass.

- [ ] **Step 4: Final commit**

```bash
git add app/auth_service/
git commit -m "fix: exclude manager from their own user list (BR-501); full auth test suite green"
```
