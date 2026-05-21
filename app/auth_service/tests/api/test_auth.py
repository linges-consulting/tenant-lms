import pytest
import uuid
import bcrypt
from tests.conftest import make_jwt, make_manager_jwt


# T-AU-08: Login normalizes email to lowercase
@pytest.mark.asyncio
async def test_login_case_insensitive(client, db_session):
    from app.models.user import User, UserStatus
    from app.models.membership import TenantMembership
    from app.models.tenant import Tenant

    tenant_id = str(uuid.uuid4())
    tenant = Tenant(
        id=tenant_id,
        name="Test Tenant",
        is_active=True,
    )
    db_session.add(tenant)

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="user@example.com",
        username="testuser_case",
        hashed_password=bcrypt.hashpw(b"Password1!", bcrypt.gensalt()).decode(),
        full_name="Test User",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.flush()

    membership = TenantMembership(
        user_id=user_id,
        tenant_id=tenant_id,
        is_active=True,
        is_employee=True,
    )
    db_session.add(membership)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", json={
        "email": "User@EXAMPLE.COM", "password": "Password1!"
    })
    # Email normalization means the user should be found — must not return 401 ("user not found")
    assert resp.status_code != 401, (
        f"Expected non-401 (email normalization failed), got {resp.status_code}: {resp.text}"
    )
    # Should succeed with 200 since user has an active membership
    assert resp.status_code == 200, (
        f"Expected 200 for valid user with active membership, got {resp.status_code}: {resp.text}"
    )


# T-AU-XX: User with zero tenant memberships is blocked at login
@pytest.mark.asyncio
async def test_login_no_memberships_blocked(client, db_session):
    from app.models.user import User, UserStatus

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="orphan@example.com",
        username="orphan_user",
        hashed_password=bcrypt.hashpw(b"Password1!", bcrypt.gensalt()).decode(),
        full_name="Orphan User",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", json={
        "email": "orphan@example.com", "password": "Password1!"
    })
    assert resp.status_code == 403, (
        f"Expected 403 for user with no memberships, got {resp.status_code}: {resp.text}"
    )
    assert "not associated" in resp.json()["detail"].lower(), (
        f"Expected 'not associated' in detail, got: {resp.json()['detail']}"
    )


# Sanity: SysAdmin with no memberships can still log in
@pytest.mark.asyncio
async def test_login_sysadmin_no_memberships_allowed(client, db_session):
    from app.models.user import User, UserStatus

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="sysadmin@example.com",
        username="sysadmin_user",
        hashed_password=bcrypt.hashpw(b"Password1!", bcrypt.gensalt()).decode(),
        full_name="Sys Admin",
        is_sysadmin=True,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", json={
        "email": "sysadmin@example.com", "password": "Password1!"
    })
    # SysAdmins are exempt from membership check
    assert resp.status_code == 200, (
        f"Expected 200 for SysAdmin with no memberships, got {resp.status_code}: {resp.text}"
    )


# T-AU-09: GET /auth/tenants must exclude inactive memberships
@pytest.mark.asyncio
async def test_tenants_excludes_inactive_membership(client, db_session):
    from app.models.user import User, UserStatus
    from app.models.membership import TenantMembership
    from app.models.tenant import Tenant

    tenant_id = str(uuid.uuid4())
    tenant = Tenant(
        id=tenant_id,
        name="Inactive Membership Tenant",
        is_active=True,
        primary_color="#123456",
        secondary_color="#654321",
    )
    db_session.add(tenant)

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="inactive_member@example.com",
        username="inactive_member_user",
        hashed_password=bcrypt.hashpw(b"Password1!", bcrypt.gensalt()).decode(),
        full_name="Inactive Member",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.flush()

    membership = TenantMembership(
        user_id=user_id,
        tenant_id=tenant_id,
        is_active=False,  # inactive membership — must not appear in tenant list
        is_employee=True,
    )
    db_session.add(membership)
    await db_session.commit()

    # Use a session token (no tenant_id) to call GET /auth/tenants
    # Use the real settings secret so the app can decode the token
    from app.core.config import settings as app_settings
    token = make_jwt(f"session_{user_id}", None, [], secret=app_settings.EXTERNAL_JWT_SECRET, expires_in=3600)
    resp = await client.get(
        "/api/v1/auth/tenants",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert data == [], (
        f"Expected empty list (inactive membership must not appear), got: {data}"
    )


# T-AU-11: POST /auth/select-tenant must return branding in response
@pytest.mark.asyncio
async def test_select_tenant_returns_branding(client, db_session):
    from app.models.user import User, UserStatus
    from app.models.membership import TenantMembership
    from app.models.tenant import Tenant

    tenant_id = str(uuid.uuid4())
    tenant = Tenant(
        id=tenant_id,
        name="Brand Tenant",
        is_active=True,
        primary_color="#FF5733",
        secondary_color="#C0C0C0",
    )
    db_session.add(tenant)

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="brand_user@example.com",
        username="brand_tenant_user",
        hashed_password=bcrypt.hashpw(b"Password1!", bcrypt.gensalt()).decode(),
        full_name="Brand User",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.flush()

    membership = TenantMembership(
        user_id=user_id,
        tenant_id=tenant_id,
        is_active=True,
        is_employee=True,
    )
    db_session.add(membership)
    await db_session.commit()

    # Use a session token to call POST /auth/select-tenant
    # Use the real settings secret so the app can decode the token
    from app.core.config import settings as app_settings
    token = make_jwt(f"session_{user_id}", None, [], secret=app_settings.EXTERNAL_JWT_SECRET, expires_in=3600)
    resp = await client.post(
        "/api/v1/auth/select-tenant",
        json={"tenant_id": tenant_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert "access_token" in data, f"Expected 'access_token' in response, got: {data}"
    assert "branding" in data, f"Expected 'branding' in response, got: {data}"
    branding = data["branding"]
    assert branding["primary_color"] == "#FF5733", (
        f"Expected primary_color '#FF5733', got: {branding.get('primary_color')}"
    )
    assert branding["tenant_name"] == "Brand Tenant", (
        f"Expected tenant_name 'Brand Tenant', got: {branding.get('tenant_name')}"
    )


# BR-501: GET /users must exclude the requesting manager from the list
@pytest.mark.asyncio
async def test_manager_excluded_from_own_user_list(client, db_session):
    from app.models.user import User, UserStatus
    from app.models.membership import TenantMembership
    from app.models.tenant import Tenant

    tenant_id = str(uuid.uuid4())
    manager_id = str(uuid.uuid4())
    employee_id = str(uuid.uuid4())

    tenant = Tenant(
        id=tenant_id,
        name="T4",
        is_active=True,
        primary_color="#000000",
        secondary_color="#ffffff",
    )
    manager = User(
        id=manager_id,
        email="self_manager@example.com",
        username="self_manager",
        hashed_password=bcrypt.hashpw(b"P1!", bcrypt.gensalt()).decode(),
        full_name="M G",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    employee = User(
        id=employee_id,
        email="emp_worker@example.com",
        username="emp_worker",
        hashed_password=bcrypt.hashpw(b"P1!", bcrypt.gensalt()).decode(),
        full_name="E P",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    mgr_mem = TenantMembership(
        user_id=manager_id,
        tenant_id=tenant_id,
        is_active=True,
        is_business_manager=True,
        is_employee=True,
    )
    emp_mem = TenantMembership(
        user_id=employee_id,
        tenant_id=tenant_id,
        is_active=True,
        is_employee=True,
    )
    db_session.add_all([tenant, manager, employee, mgr_mem, emp_mem])
    await db_session.commit()

    from app.core.config import settings as app_settings
    token = make_manager_jwt(manager_id, tenant_id, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code}: {resp.text}"
    )
    user_ids = [u["id"] for u in resp.json()]
    assert manager_id not in user_ids, (
        f"Manager should be excluded from user list but found in: {user_ids}"
    )
    assert employee_id in user_ids, (
        f"Employee should appear in user list but not found in: {user_ids}"
    )
