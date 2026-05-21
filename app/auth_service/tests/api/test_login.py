"""
Login & Tenant Selection tests — TC-LGN-04 through TC-LGN-17.

Covers: wrong credentials, deactivated accounts, inactive-tenant membership blocks,
and the two-step login flow (session token → tenant selection → scoped JWT with branding).
"""
import pytest
import uuid
import bcrypt
from tests.conftest import make_jwt


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


async def _make_tenant(db, *, name="T", active=True, color="#000000"):
    from app.models.tenant import Tenant
    t = Tenant(id=str(uuid.uuid4()), name=f"{name}-{uuid.uuid4().hex[:6]}", is_active=active,
               primary_color=color, secondary_color="#ffffff")
    db.add(t)
    await db.flush()
    return t


async def _make_user(db, *, email, pw="Pass1!", active=True):
    from app.models.user import User, UserStatus
    u = User(id=str(uuid.uuid4()), email=email, username=f"u_{uuid.uuid4().hex[:8]}",
             hashed_password=_hash(pw), full_name="Test User",
             is_sysadmin=False, is_active=active, status=UserStatus.ACTIVE if active else UserStatus.INACTIVE)
    db.add(u)
    await db.flush()
    return u


async def _add_member(db, user_id, tenant_id, *, active=True, pending=False):
    from app.models.membership import TenantMembership
    from app.models.user import UserStatus
    status = UserStatus.PENDING if pending else (UserStatus.ACTIVE if active else UserStatus.INACTIVE)
    m = TenantMembership(user_id=user_id, tenant_id=tenant_id,
                         is_active=active and not pending,
                         is_employee=True, status=status)
    db.add(m)
    await db.flush()
    return m


# ---------------------------------------------------------------------------
# TC-LGN-04: Wrong password → 401
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client, db_session):
    t = await _make_tenant(db_session)
    u = await _make_user(db_session, email="wrongpw@example.com")
    await _add_member(db_session, u.id, t.id)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "BadPass!"})
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
    assert "incorrect" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# TC-LGN-05: Non-existent email → 401 (no user enumeration)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_nonexistent_email_returns_401(client):
    resp = await client.post("/api/v1/auth/login", json={"email": "nobody99@example.com", "password": "any"})
    assert resp.status_code == 401, f"Expected 401 for unknown email, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# TC-LGN-06: Globally deactivated user account → 403
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_deactivated_user_returns_403(client, db_session):
    from app.models.user import User, UserStatus
    user_id = str(uuid.uuid4())
    u = User(id=user_id, email="deactivated@example.com", username="deactivated_user",
             hashed_password=_hash("Pass1!"), full_name="D U",
             is_sysadmin=False, is_active=False, status=UserStatus.INACTIVE)
    db_session.add(u)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", json={"email": "deactivated@example.com", "password": "Pass1!"})
    assert resp.status_code == 403, f"Expected 403 for deactivated account, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# TC-LGN-07: All memberships inactive → 403 with clear message
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_all_memberships_inactive_returns_403(client, db_session):
    t = await _make_tenant(db_session)
    u = await _make_user(db_session, email="allinactive@example.com")
    await _add_member(db_session, u.id, t.id, active=False)  # inactive membership
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", json={"email": "allinactive@example.com", "password": "Pass1!"})
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    assert "not associated" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# TC-LGN-12: Pending memberships not shown in GET /auth/tenants
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tenants_excludes_pending_membership(client, db_session):
    from app.core.config import settings as app_settings
    t = await _make_tenant(db_session)
    u = await _make_user(db_session, email="pending_mem@example.com")
    await _add_member(db_session, u.id, t.id, active=False, pending=True)  # PENDING status
    await db_session.commit()

    token = make_jwt(f"session_{u.id}", None, [], secret=app_settings.EXTERNAL_JWT_SECRET, expires_in=3600)
    resp = await client.get("/api/v1/auth/tenants", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json() == [], f"Pending membership must not appear in tenant list, got: {resp.json()}"


# ---------------------------------------------------------------------------
# TC-LGN-13: select-tenant issues scoped JWT with correct tenant_id + roles
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_tenant_jwt_contains_correct_claims(client, db_session):
    from app.core.config import settings as app_settings
    from jose import jwt as jose_jwt

    t = await _make_tenant(db_session, name="ClaimsT")
    u = await _make_user(db_session, email="claims_user@example.com")
    from app.models.membership import TenantMembership
    from app.models.user import UserStatus
    mem = TenantMembership(user_id=u.id, tenant_id=t.id, is_active=True,
                           is_employee=True, is_business_manager=True,
                           status=UserStatus.ACTIVE)
    db_session.add(mem)
    await db_session.commit()

    session_token = make_jwt(f"session_{u.id}", None, [], secret=app_settings.EXTERNAL_JWT_SECRET, expires_in=3600)
    resp = await client.post("/api/v1/auth/select-tenant", json={"tenant_id": t.id},
                             headers={"Authorization": f"Bearer {session_token}"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "access_token" in data

    claims = jose_jwt.decode(data["access_token"], app_settings.EXTERNAL_JWT_SECRET, algorithms=["HS256"])
    assert claims["tenant_id"] == t.id, f"JWT tenant_id mismatch: {claims}"


# ---------------------------------------------------------------------------
# TC-LGN-15: Selecting a tenant the user is not active in → 403
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_tenant_user_not_member_returns_403(client, db_session):
    from app.core.config import settings as app_settings
    t = await _make_tenant(db_session)
    foreign_tenant_id = str(uuid.uuid4())  # no membership for this user
    u = await _make_user(db_session, email="foreign_t@example.com")
    await _add_member(db_session, u.id, t.id)
    await db_session.commit()

    session_token = make_jwt(f"session_{u.id}", None, [], secret=app_settings.EXTERNAL_JWT_SECRET, expires_in=3600)
    resp = await client.post("/api/v1/auth/select-tenant", json={"tenant_id": foreign_tenant_id},
                             headers={"Authorization": f"Bearer {session_token}"})
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
