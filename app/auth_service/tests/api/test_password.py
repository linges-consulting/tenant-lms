import pytest
import uuid
from datetime import datetime, timezone, timedelta
from tests.conftest import make_sysadmin_jwt, make_manager_jwt


# BR-504: Admins must NOT be able to manually set passwords via an admin endpoint
@pytest.mark.asyncio
async def test_admin_cannot_reset_password(client):
    token = make_sysadmin_jwt()
    user_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/users/{user_id}/reset-password",
        json={"new_password": "NewPass1!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404  # endpoint must not exist


@pytest.mark.asyncio
async def test_forgot_password_valid_email(client, db_session):
    from app.models.user import User, UserStatus
    from app.core.security import get_password_hash

    user = User(
        id=str(uuid.uuid4()),
        email="forgot@example.com",
        username="forgotuser",
        hashed_password=get_password_hash("Pass1!xxx"),
        full_name="Forgot Guy",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/forgot-password", json={"email": "forgot@example.com"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_returns_200(client):
    resp = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 200  # no enumeration


@pytest.mark.asyncio
async def test_reset_password_valid_token(client, db_session):
    from app.models.user import User, UserStatus
    from app.models.password_reset import PasswordResetToken
    from app.core.security import get_password_hash
    from datetime import datetime, timezone, timedelta

    user_id = str(uuid.uuid4())
    token_value = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="reset@example.com",
        username="resetuser",
        hashed_password=get_password_hash("OldPass1!"),
        full_name="Reset User",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()

    reset_token = PasswordResetToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token=token_value,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_used=False,
    )
    db_session.add(reset_token)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/reset-password", json={
        "token": token_value, "new_password": "NewSecure1!"
    })
    assert resp.status_code == 200

    # Verify old password no longer works (TC-PWD-05)
    login_resp = await client.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": "OldPass1!"})
    assert login_resp.status_code == 401


# ---------------------------------------------------------------------------
# TC-PWD-03: Reset token is single-use — second attempt rejected with 400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_token_single_use(client, db_session):
    from app.models.user import User, UserStatus
    from app.models.password_reset import PasswordResetToken
    from app.core.security import get_password_hash

    user_id = str(uuid.uuid4())
    token_value = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="singleuse@example.com",
        username="singleuse_user",
        hashed_password=get_password_hash("Old1!"),
        full_name="Single Use",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()

    token = PasswordResetToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token=token_value,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_used=False,
    )
    db_session.add(token)
    await db_session.commit()

    # First use — succeeds
    r1 = await client.post("/api/v1/auth/reset-password", json={"token": token_value, "new_password": "New1!xxxx"})
    assert r1.status_code == 200, f"First reset failed: {r1.text}"

    # Second use — rejected
    r2 = await client.post("/api/v1/auth/reset-password", json={"token": token_value, "new_password": "Another1!"})
    assert r2.status_code == 400, f"Expected 400 on second use, got {r2.status_code}: {r2.text}"


# ---------------------------------------------------------------------------
# TC-PWD-04: Expired reset token → 400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_expired_token_returns_400(client, db_session):
    from app.models.user import User, UserStatus
    from app.models.password_reset import PasswordResetToken
    from app.core.security import get_password_hash

    user_id = str(uuid.uuid4())
    token_value = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="expiredtoken@example.com",
        username="expiredtoken_user",
        hashed_password=get_password_hash("Old1!"),
        full_name="Expired Token",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()

    expired_token = PasswordResetToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token=token_value,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # expired
        is_used=False,
    )
    db_session.add(expired_token)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/reset-password", json={"token": token_value, "new_password": "New1!xxxx"})
    assert resp.status_code == 400, f"Expected 400 for expired token, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# TC-PWD-09: User can change password with correct current password
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_change_password_success(client, db_session):
    import bcrypt
    from app.models.user import User, UserStatus
    from app.models.membership import TenantMembership
    from app.models.tenant import Tenant
    from app.core.config import settings as app_settings
    from tests.conftest import make_jwt

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    tenant = Tenant(id=tenant_id, name=f"PwdT-{tenant_id[:6]}", is_active=True,
                    primary_color="#000", secondary_color="#fff")
    user = User(id=user_id, email="changepw@example.com", username="changepw_user",
                hashed_password=bcrypt.hashpw(b"Current1!", bcrypt.gensalt()).decode(),
                full_name="Change PW", is_sysadmin=False, is_active=True, status=UserStatus.ACTIVE)
    mem = TenantMembership(user_id=user_id, tenant_id=tenant_id, is_active=True,
                           is_employee=True, status=UserStatus.ACTIVE)
    db_session.add_all([tenant, user, mem])
    await db_session.commit()

    token = make_jwt(user_id, tenant_id, ["Employee"], secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.patch("/api/v1/users/me/password",
                              json={"old_password": "Current1!", "new_password": "NewPass1!"},
                              headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    # Confirm old password no longer works
    login = await client.post("/api/v1/auth/login", json={"email": "changepw@example.com", "password": "Current1!"})
    assert login.status_code == 401


# ---------------------------------------------------------------------------
# TC-PWD-10: Wrong current password rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_change_password_wrong_current_returns_400(client, db_session):
    import bcrypt
    from app.models.user import User, UserStatus
    from app.models.membership import TenantMembership
    from app.models.tenant import Tenant
    from app.core.config import settings as app_settings
    from tests.conftest import make_jwt

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    tenant = Tenant(id=tenant_id, name=f"PwdT2-{tenant_id[:6]}", is_active=True,
                    primary_color="#000", secondary_color="#fff")
    user = User(id=user_id, email="wrongcurrent@example.com", username="wrongcurrent_user",
                hashed_password=bcrypt.hashpw(b"Correct1!", bcrypt.gensalt()).decode(),
                full_name="Wrong Current", is_sysadmin=False, is_active=True, status=UserStatus.ACTIVE)
    mem = TenantMembership(user_id=user_id, tenant_id=tenant_id, is_active=True,
                           is_employee=True, status=UserStatus.ACTIVE)
    db_session.add_all([tenant, user, mem])
    await db_session.commit()

    token = make_jwt(user_id, tenant_id, ["Employee"], secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.patch("/api/v1/users/me/password",
                              json={"old_password": "WrongPass1!", "new_password": "New1!xxxx"},
                              headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in (400, 401), f"Expected 400/401 for wrong current password, got {resp.status_code}: {resp.text}"
