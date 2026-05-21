"""
Registration completion & invitation lifecycle tests — TC-REG-04 through TC-REG-16.

Covers: Magic Link token validity, single-use enforcement, token expiry,
email mismatch, username uniqueness at completion, and re-invitation flows.

Note: The auth service uses a single register/complete endpoint that validates
UserToken records (magic-link tokens). All these tests seed that table directly.
"""
import pytest
import uuid
import bcrypt
from datetime import datetime, timezone, timedelta


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


async def _make_user_with_pending_token(db, *, email, token_value, expired=False, used=False):
    """Create an invited (pending) user + UserToken and return user_id."""
    from app.models.user import User, UserStatus
    from app.models.user_token import UserToken

    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        email=email,
        username=None,
        hashed_password=None,
        full_name="Pending User",
        is_sysadmin=False,
        is_active=False,
        status=UserStatus.PENDING,
    )
    db.add(user)
    await db.flush()

    expires_at = (
        datetime.now(timezone.utc) - timedelta(hours=1) if expired
        else datetime.now(timezone.utc) + timedelta(hours=48)
    )
    token = UserToken(
        id=str(uuid.uuid4()),
        user_id=uid,
        token=token_value,
        expires_at=expires_at,
        is_used=used,
    )
    db.add(token)
    return uid


# ---------------------------------------------------------------------------
# TC-REG-03: Valid unused token → registration completes successfully
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_complete_valid_token(client, db_session):
    token_value = str(uuid.uuid4())
    await _make_user_with_pending_token(db_session, email="valid_reg@example.com", token_value=token_value)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/register/complete", json={
        "token": token_value,
        "email": "valid_reg@example.com",
        "username": "newuser_reg",
        "password": "Secure1!pass",
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["username"] == "newuser_reg"


# ---------------------------------------------------------------------------
# TC-REG-04: Email mismatch rejected (BR-101)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_complete_email_mismatch_rejected(client, db_session):
    token_value = str(uuid.uuid4())
    await _make_user_with_pending_token(db_session, email="correct@example.com", token_value=token_value)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/register/complete", json={
        "token": token_value,
        "email": "wrong@example.com",  # different from token's email
        "username": "mismatch_user",
        "password": "Secure1!pass",
    })
    assert resp.status_code == 400, f"Expected 400 for email mismatch, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# TC-REG-05: Expired token → 400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_complete_expired_token_returns_400(client, db_session):
    token_value = str(uuid.uuid4())
    await _make_user_with_pending_token(db_session, email="expired_inv@example.com",
                                        token_value=token_value, expired=True)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/register/complete", json={
        "token": token_value,
        "email": "expired_inv@example.com",
        "username": "exp_user",
        "password": "Secure1!pass",
    })
    assert resp.status_code == 400, f"Expected 400 for expired token, got {resp.status_code}: {resp.text}"
    assert "expired" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# TC-REG-06: Already-used token → 400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_complete_used_token_returns_400(client, db_session):
    token_value = str(uuid.uuid4())
    await _make_user_with_pending_token(db_session, email="used_inv@example.com",
                                        token_value=token_value, used=True)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/register/complete", json={
        "token": token_value,
        "email": "used_inv@example.com",
        "username": "used_user",
        "password": "Secure1!pass",
    })
    assert resp.status_code == 400, f"Expected 400 for used token, got {resp.status_code}: {resp.text}"
    assert "already been used" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# TC-REG-07: Username must be globally unique at registration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_complete_taken_username_returns_409(client, db_session):
    from app.models.user import User, UserStatus

    # Pre-existing user with the target username
    existing_id = str(uuid.uuid4())
    existing = User(
        id=existing_id,
        email="existing_user@example.com",
        username="takenusername",
        hashed_password=_hash("Pass1!"),
        full_name="Existing",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(existing)

    token_value = str(uuid.uuid4())
    await _make_user_with_pending_token(db_session, email="new_user_taken@example.com", token_value=token_value)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/register/complete", json={
        "token": token_value,
        "email": "new_user_taken@example.com",
        "username": "takenusername",  # already in use
        "password": "Secure1!pass",
    })
    assert resp.status_code == 409, f"Expected 409 for taken username, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# TC-REG-06 (second-use): Token is single-use — completing once, then trying again fails
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_complete_token_single_use(client, db_session):
    token_value = str(uuid.uuid4())
    await _make_user_with_pending_token(db_session, email="singleuse_reg@example.com", token_value=token_value)
    await db_session.commit()

    # First completion
    r1 = await client.post("/api/v1/auth/register/complete", json={
        "token": token_value,
        "email": "singleuse_reg@example.com",
        "username": "singleuse_reg_user",
        "password": "Secure1!pass",
    })
    assert r1.status_code == 200, f"First completion failed: {r1.text}"

    # Second attempt with same token — must fail
    r2 = await client.post("/api/v1/auth/register/complete", json={
        "token": token_value,
        "email": "singleuse_reg@example.com",
        "username": "singleuse_reg_user2",
        "password": "Secure2!pass",
    })
    assert r2.status_code == 400, f"Expected 400 on second use, got {r2.status_code}: {r2.text}"
    assert "already been used" in r2.json()["detail"].lower()


# ---------------------------------------------------------------------------
# TC-REG-12: Re-invite inactive user → membership is_active=True, no password reset
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reinvite_inactive_restores_without_password_reset(client, db_session):
    """
    Re-inviting a user who is inactive in a tenant should restore their membership
    to Active. Unlike a new invite, no Magic Link is needed (they already have a password).
    Verified via the membership is_active flag after calling invite.
    """
    from app.models.user import User, UserStatus
    from app.models.membership import TenantMembership
    from app.models.tenant import Tenant
    from app.core.config import settings as app_settings
    from tests.conftest import make_manager_jwt

    tenant_id = str(uuid.uuid4())
    mgr_id = str(uuid.uuid4())
    emp_id = str(uuid.uuid4())

    tenant = Tenant(id=tenant_id, name=f"ReInvT-{tenant_id[:6]}", is_active=True,
                    primary_color="#000000", secondary_color="#ffffff")
    mgr = User(id=mgr_id, email=f"mgr_reinv_{mgr_id[:6]}@example.com", username=f"mgr_{mgr_id[:6]}",
               hashed_password=_hash("Pass1!"), full_name="Mgr",
               is_sysadmin=False, is_active=True, status=UserStatus.ACTIVE)
    emp = User(id=emp_id, email="reinv_emp@example.com", username=f"reinv_{emp_id[:6]}",
               hashed_password=_hash("Pass1!"), full_name="Emp",
               is_sysadmin=False, is_active=True, status=UserStatus.ACTIVE)
    mgr_mem = TenantMembership(user_id=mgr_id, tenant_id=tenant_id, is_active=True,
                               is_employee=True, is_business_manager=True, status=UserStatus.ACTIVE)
    emp_mem = TenantMembership(user_id=emp_id, tenant_id=tenant_id, is_active=False,
                               is_employee=True, status=UserStatus.INACTIVE)
    db_session.add_all([tenant, mgr, emp, mgr_mem, emp_mem])
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tenant_id, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post("/api/v1/users/invite",
                             json={"email": "reinv_emp@example.com", "full_name": "Emp",
                                   "is_business_manager": False, "is_training_creator": False},
                             headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id})
    assert resp.status_code in (200, 201), f"Re-invite failed: {resp.status_code}: {resp.text}"

    await db_session.refresh(emp_mem)
    assert emp_mem.is_active is True, "Membership should be reactivated after re-invite"
