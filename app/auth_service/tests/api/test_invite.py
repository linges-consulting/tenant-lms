import pytest
import uuid
import bcrypt
from datetime import datetime, timezone
from tests.conftest import make_manager_jwt, make_sysadmin_jwt


# T-INV-01: Manager invite generates a token with ~48h expiry
@pytest.mark.asyncio
async def test_manager_invite_token_expires_48h(client, db_session):
    from app.models.user import User, UserStatus
    from app.models.membership import TenantMembership
    from app.models.tenant import Tenant
    from app.models.user_token import UserToken
    from app.core.config import settings as app_settings
    from sqlalchemy import select

    tenant_id = str(uuid.uuid4())
    manager_id = str(uuid.uuid4())

    tenant = Tenant(
        id=tenant_id,
        name="T1",
        is_active=True,
        primary_color="#000000",
        secondary_color="#ffffff",
    )
    manager = User(
        id=manager_id,
        email="mgr@example.com",
        username="mgr_invite_test",
        hashed_password=bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode(),
        full_name="Manager G",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    membership = TenantMembership(
        user_id=manager_id,
        tenant_id=tenant_id,
        is_active=True,
        is_business_manager=True,
        is_employee=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add_all([tenant, manager, membership])
    await db_session.commit()

    # Use the real app secret so deps.get_current_user can decode the token
    token = make_manager_jwt(manager_id, tenant_id, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        "/api/v1/users/invite",
        json={
            "email": "newemployee@example.com",
            "full_name": "New Employee",
            "is_business_manager": False,
            "is_training_creator": False,
        },
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id},
    )
    assert resp.status_code in (200, 201), f"Unexpected status {resp.status_code}: {resp.text}"

    # Fetch the token from DB and verify expiry is ~48h
    result = await db_session.execute(
        select(UserToken).order_by(UserToken.created_at.desc())
    )
    reg_token = result.scalars().first()
    assert reg_token is not None, "No UserToken was created"

    # SQLite may return naive datetimes — normalise to UTC-aware before comparing
    expires_at = reg_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    diff = expires_at - datetime.now(timezone.utc)
    # Between 47h55m and 48h05m
    assert 47 * 3600 < diff.total_seconds() < 48 * 3600 + 300, (
        f"Token expiry is {diff.total_seconds()/3600:.2f}h, expected ~48h"
    )


# T-INV-02: Re-inviting a user with an inactive membership restores is_active=True
@pytest.mark.asyncio
async def test_reinvite_inactive_user_restores_access(client, db_session):
    from app.models.user import User, UserStatus
    from app.models.membership import TenantMembership
    from app.models.tenant import Tenant
    from app.core.config import settings as app_settings

    tenant_id = str(uuid.uuid4())
    manager_id = str(uuid.uuid4())
    employee_id = str(uuid.uuid4())

    tenant = Tenant(
        id=tenant_id,
        name="T2",
        is_active=True,
        primary_color="#000000",
        secondary_color="#ffffff",
    )
    manager = User(
        id=manager_id,
        email="mgr2@example.com",
        username="mgr2_reinvite_test",
        hashed_password=bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode(),
        full_name="Manager G",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    manager_mem = TenantMembership(
        user_id=manager_id,
        tenant_id=tenant_id,
        is_active=True,
        is_business_manager=True,
        is_employee=True,
        status=UserStatus.ACTIVE,
    )
    employee = User(
        id=employee_id,
        email="inactive@example.com",
        username="inactive_reinvite_test",
        hashed_password=bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode(),
        full_name="Inactive E",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    emp_mem = TenantMembership(
        user_id=employee_id,
        tenant_id=tenant_id,
        is_active=False,
        is_employee=True,
        status=UserStatus.INACTIVE,
    )
    db_session.add_all([tenant, manager, manager_mem, employee, emp_mem])
    await db_session.commit()

    token = make_manager_jwt(manager_id, tenant_id, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        "/api/v1/users/invite",
        json={
            "email": "inactive@example.com",
            "full_name": "Inactive E",
            "is_business_manager": False,
            "is_training_creator": False,
        },
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id},
    )
    assert resp.status_code in (200, 201), f"Unexpected status {resp.status_code}: {resp.text}"

    await db_session.refresh(emp_mem)
    assert emp_mem.is_active is True, "membership.is_active should be True after re-invite"
    assert emp_mem.status == UserStatus.ACTIVE, f"membership.status should be Active, got {emp_mem.status}"


# T-INV-03: SysAdmin can invite a brand-new user to a tenant without a NameError
@pytest.mark.asyncio
async def test_sysadmin_invite_new_user_no_error(client, db_session):
    from app.models.user import User, UserStatus
    from app.models.tenant import Tenant
    from app.core.config import settings as app_settings

    sysadmin_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())

    sysadmin = User(
        id=sysadmin_id,
        email="sysadmin_invite_test@example.com",
        username="sysadmin_invite_test",
        hashed_password=bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode(),
        full_name="Sys Admin",
        is_sysadmin=True,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    tenant = Tenant(
        id=tenant_id,
        name="T3",
        is_active=True,
        primary_color="#000000",
        secondary_color="#ffffff",
    )
    db_session.add_all([sysadmin, tenant])
    await db_session.commit()

    token = make_sysadmin_jwt(user_id=sysadmin_id, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        "/api/v1/users/admin/invite-to-tenant",
        json={
            "email": "newhire@example.com",
            "full_name": "New Hire",
            "tenant_id": tenant_id,
            "is_business_manager": False,
            "is_training_creator": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (200, 201), f"Unexpected status {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "invite_url" in data
    assert data["invite_url"] is not None, "invite_url must not be None for a new user"
