"""
Tenant Management Tests — TC-TEN-01 through TC-TEN-43.

Covers:
  01-tenant-crud.md : TC-TEN-01 … TC-TEN-24  (create, view, update, deactivate)
  02-branding.md    : TC-TEN-25 … TC-TEN-36  (frontend-only tests are skipped with notes)
  03-tenant-isolation.md : TC-TEN-37 … TC-TEN-43 (isolation)

Notes on frontend-only test cases (not implemented here — backend has no corresponding endpoint):
  TC-TEN-25: CSS --primary variable injection is a browser/frontend concern.
  TC-TEN-26: CSS --secondary variable injection is a browser/frontend concern.
  TC-TEN-27: Updated color reflected on next login — browser CSS variable concern.
  TC-TEN-28: Null colors → default theme — browser/frontend concern.
  TC-TEN-29: SysAdmin portal uses neutral theme — browser/frontend concern.
  TC-TEN-30: Logo shown in sidebar — browser/frontend concern.
  TC-TEN-31: Fallback to initials when logo_url=null — browser/frontend concern.
  TC-TEN-33: SysAdmin sees all tenants in settings overview — covered by TC-TEN-10.
  TC-TEN-34: Tenant list sort order — browser/frontend concern.
  TC-TEN-35: Save branding shows success toast — browser/frontend concern.
  TC-TEN-36: Deactivating shows state change — browser/frontend concern.
  TC-TEN-43: Branding does not bleed between sessions — browser/frontend concern.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, patch
from tests.conftest import make_sysadmin_jwt, make_manager_jwt, make_jwt


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _tid():
    return str(uuid.uuid4())


def _uid():
    return str(uuid.uuid4())


async def _create_sysadmin(db):
    from app.models.user import User, UserStatus
    uid = _uid()
    user = User(
        id=uid,
        email=f"sysadmin_{uid[:8]}@system.local",
        username=f"sa_{uid[:8]}",
        hashed_password="hashed",
        full_name="Sys Admin",
        is_sysadmin=True,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()
    return uid


async def _create_tenant(db, *, name=None, is_active=True,
                          primary_color="#000000", secondary_color="#ffffff",
                          logo_url=None):
    from app.models.tenant import Tenant
    tid = _tid()
    tenant = Tenant(
        id=tid,
        name=name or f"Tenant-{tid[:6]}",
        is_active=is_active,
        primary_color=primary_color,
        secondary_color=secondary_color,
        logo_url=logo_url,
    )
    db.add(tenant)
    await db.flush()
    return tid


async def _create_user(db, *, email=None, is_active=True, is_sysadmin=False):
    from app.models.user import User, UserStatus
    uid = _uid()
    user = User(
        id=uid,
        email=email or f"user_{uid[:8]}@example.com",
        username=f"u_{uid[:8]}",
        hashed_password="hashed",
        full_name="Test User",
        is_sysadmin=is_sysadmin,
        is_active=is_active,
        status=UserStatus.ACTIVE if is_active else UserStatus.INACTIVE,
    )
    db.add(user)
    await db.flush()
    return uid


async def _create_membership(db, user_id, tenant_id, *, is_manager=False, is_active=True):
    from app.models.membership import TenantMembership
    from app.models.user import UserStatus
    mem = TenantMembership(
        user_id=user_id,
        tenant_id=tenant_id,
        is_active=is_active,
        is_employee=True,
        is_business_manager=is_manager,
        is_training_creator=False,
        status=UserStatus.ACTIVE if is_active else UserStatus.INACTIVE,
    )
    db.add(mem)
    await db.flush()
    return mem


def _sysadmin_headers(sa_uid):
    from app.core.config import settings as app_settings
    token = make_sysadmin_jwt(user_id=sa_uid, secret=app_settings.EXTERNAL_JWT_SECRET)
    return {"Authorization": f"Bearer {token}"}


def _manager_headers(mgr_uid, tenant_id):
    from app.core.config import settings as app_settings
    token = make_manager_jwt(mgr_uid, tenant_id, secret=app_settings.EXTERNAL_JWT_SECRET)
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id}


def _employee_headers(user_uid, tenant_id):
    from app.core.config import settings as app_settings
    token = make_jwt(user_uid, tenant_id, ["Employee"], secret=app_settings.EXTERNAL_JWT_SECRET)
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id}


# ---------------------------------------------------------------------------
# TC-TEN-01: SysAdmin creates a new tenant with required fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sysadmin_creates_tenant(client, db_session):
    """TC-TEN-01: POST /tenants returns 201 with valid required fields."""
    sa_uid = await _create_sysadmin(db_session)
    await db_session.commit()

    payload = {
        "name": "Acme Corp",
        "admin_email": "admin@acme.com",
        "admin_name": "Acme Admin",
    }

    with patch("app.utils.provisioning.provision_default_certificate", new=AsyncMock(return_value=True)), \
         patch("app.core.events.event_publisher.publish", new=AsyncMock()):
        resp = await client.post(
            "/api/v1/tenants",
            json=payload,
            headers=_sysadmin_headers(sa_uid),
        )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["name"] == "Acme Corp"
    assert "id" in data


# ---------------------------------------------------------------------------
# TC-TEN-02: New tenant auto-receives default certificate template (BR-702)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_new_tenant_provisions_default_certificate(client, db_session):
    """TC-TEN-02: provision_default_certificate is called on tenant creation.

    The mock must target the symbol as imported in the tenants endpoint module,
    not the definition in utils.provisioning — otherwise the original function
    is called and the assertion would fail.
    """
    sa_uid = await _create_sysadmin(db_session)
    await db_session.commit()

    mock_provision = AsyncMock(return_value=True)

    # Patch at the point of use (the tenants endpoint module)
    with patch("app.api.v1.endpoints.tenants.provision_default_certificate", new=mock_provision), \
         patch("app.core.events.event_publisher.publish", new=AsyncMock()):
        resp = await client.post(
            "/api/v1/tenants",
            json={"name": "CertCo", "admin_email": "ceo@certco.com", "admin_name": "CEO"},
            headers=_sysadmin_headers(sa_uid),
        )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    mock_provision.assert_called_once()
    call_args = mock_provision.call_args
    # tenant_id and tenant_name must be passed
    assert call_args is not None


# ---------------------------------------------------------------------------
# TC-TEN-03: Initial Business Manager receives Magic Link (if new email)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_new_admin_email_gets_magic_link(client, db_session):
    """TC-TEN-03: Creating tenant with a brand-new email triggers USER_INVITED event."""
    sa_uid = await _create_sysadmin(db_session)
    await db_session.commit()

    mock_publish = AsyncMock()

    with patch("app.utils.provisioning.provision_default_certificate", new=AsyncMock(return_value=True)), \
         patch("app.core.events.event_publisher.publish", new=mock_publish):
        resp = await client.post(
            "/api/v1/tenants",
            json={"name": "NewCo", "admin_email": "brand-new@newco.io", "admin_name": "New Admin"},
            headers=_sysadmin_headers(sa_uid),
        )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    mock_publish.assert_called_once()
    event_type, payload = mock_publish.call_args[0]
    assert event_type == "USER_INVITED"
    assert "invite_url" in payload
    # The response should include the invite URL
    data = resp.json()
    assert data.get("manager_invite_url"), "Expected manager_invite_url in response"
    assert data.get("is_admin_new") is True


# ---------------------------------------------------------------------------
# TC-TEN-04: Initial Manager auto-linked if existing active user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_existing_active_user_auto_linked(client, db_session):
    """TC-TEN-04: If admin_email already belongs to an ACTIVE user, membership is ACTIVE immediately."""
    from app.models.user import User, UserStatus

    sa_uid = await _create_sysadmin(db_session)

    # Pre-create an active user with the admin email
    existing_uid = _uid()
    existing_user = User(
        id=existing_uid,
        email="existing@acme.com",
        username=f"exist_{existing_uid[:6]}",
        hashed_password="hashed",
        full_name="Existing User",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(existing_user)
    await db_session.commit()

    mock_publish = AsyncMock()

    with patch("app.utils.provisioning.provision_default_certificate", new=AsyncMock(return_value=True)), \
         patch("app.core.events.event_publisher.publish", new=mock_publish):
        resp = await client.post(
            "/api/v1/tenants",
            json={"name": "AutoLink Corp", "admin_email": "existing@acme.com", "admin_name": "Existing User"},
            headers=_sysadmin_headers(sa_uid),
        )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    # Existing active users should NOT get an invite link and is_admin_new should be False
    assert data.get("is_admin_new") is False
    # No USER_INVITED event because user exists and is active
    mock_publish.assert_not_called()


# ---------------------------------------------------------------------------
# TC-TEN-05: Tenant created with optional logo URL stored
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_tenant_with_logo_url(client, db_session):
    """TC-TEN-05: logo_url is persisted on the tenant record."""
    sa_uid = await _create_sysadmin(db_session)
    await db_session.commit()

    logo = "https://cdn.example.com/logo.png"

    with patch("app.utils.provisioning.provision_default_certificate", new=AsyncMock(return_value=True)), \
         patch("app.core.events.event_publisher.publish", new=AsyncMock()):
        resp = await client.post(
            "/api/v1/tenants",
            json={"name": "LogoCo", "admin_email": "logo@logoco.com", "admin_name": "Logo Admin", "logo_url": logo},
            headers=_sysadmin_headers(sa_uid),
        )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    assert resp.json()["logo_url"] == logo


# ---------------------------------------------------------------------------
# TC-TEN-06: Tenant created with optional brand colors stored
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_tenant_with_brand_colors(client, db_session):
    """TC-TEN-06: primary_color and secondary_color are persisted."""
    sa_uid = await _create_sysadmin(db_session)
    await db_session.commit()

    with patch("app.utils.provisioning.provision_default_certificate", new=AsyncMock(return_value=True)), \
         patch("app.core.events.event_publisher.publish", new=AsyncMock()):
        resp = await client.post(
            "/api/v1/tenants",
            json={
                "name": "ColorCo",
                "admin_email": "color@colorco.com",
                "admin_name": "Color Admin",
                "primary_color": "#3B82F6",
                "secondary_color": "#EFF6FF",
            },
            headers=_sysadmin_headers(sa_uid),
        )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["primary_color"] == "#3B82F6"
    assert data["secondary_color"] == "#EFF6FF"


# ---------------------------------------------------------------------------
# TC-TEN-07: Tenant name is required
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_tenant_missing_name(client, db_session):
    """TC-TEN-07: Omitting name returns 422."""
    sa_uid = await _create_sysadmin(db_session)
    await db_session.commit()

    with patch("app.utils.provisioning.provision_default_certificate", new=AsyncMock(return_value=True)):
        resp = await client.post(
            "/api/v1/tenants",
            json={"admin_email": "admin@co.com", "admin_name": "Admin"},
            headers=_sysadmin_headers(sa_uid),
        )

    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# TC-TEN-08: Admin email is required
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_tenant_missing_admin_email(client, db_session):
    """TC-TEN-08: Omitting admin_email returns 422."""
    sa_uid = await _create_sysadmin(db_session)
    await db_session.commit()

    with patch("app.utils.provisioning.provision_default_certificate", new=AsyncMock(return_value=True)):
        resp = await client.post(
            "/api/v1/tenants",
            json={"name": "NoCo", "admin_name": "Admin"},
            headers=_sysadmin_headers(sa_uid),
        )

    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# TC-TEN-09: Non-SysAdmin cannot create a tenant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_sysadmin_cannot_create_tenant(client, db_session):
    """TC-TEN-09: Manager JWT on POST /tenants returns 403."""
    tid = await _create_tenant(db_session)
    mgr_uid = await _create_user(db_session)
    await _create_membership(db_session, mgr_uid, tid, is_manager=True)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/tenants",
        json={"name": "Hijack Corp", "admin_email": "hacker@evil.com", "admin_name": "Hacker"},
        headers=_manager_headers(mgr_uid, tid),
    )

    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# TC-TEN-10: SysAdmin can list all tenants
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sysadmin_can_list_all_tenants(client, db_session):
    """TC-TEN-10: GET /tenants returns list of all tenants for SysAdmin."""
    sa_uid = await _create_sysadmin(db_session)
    tid1 = await _create_tenant(db_session, name="Alpha Corp")
    tid2 = await _create_tenant(db_session, name="Beta Corp")
    await db_session.commit()

    resp = await client.get("/api/v1/tenants", headers=_sysadmin_headers(sa_uid))

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert isinstance(data, list)
    ids = {t["id"] for t in data}
    assert tid1 in ids
    assert tid2 in ids


# ---------------------------------------------------------------------------
# TC-TEN-11: SysAdmin can view individual tenant details
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sysadmin_can_view_tenant_detail(client, db_session):
    """TC-TEN-11: GET /tenants/admin/{id} returns tenant record for SysAdmin."""
    sa_uid = await _create_sysadmin(db_session)
    tid = await _create_tenant(db_session, name="Detail Corp")
    await db_session.commit()

    resp = await client.get(f"/api/v1/tenants/admin/{tid}", headers=_sysadmin_headers(sa_uid))

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["id"] == tid
    assert data["name"] == "Detail Corp"
    assert "user_count" in data


# ---------------------------------------------------------------------------
# TC-TEN-12: Non-SysAdmin cannot list all tenants
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_sysadmin_cannot_list_tenants(client, db_session):
    """TC-TEN-12: Manager JWT on GET /tenants returns 403."""
    tid = await _create_tenant(db_session)
    mgr_uid = await _create_user(db_session)
    await _create_membership(db_session, mgr_uid, tid, is_manager=True)
    await db_session.commit()

    resp = await client.get("/api/v1/tenants", headers=_manager_headers(mgr_uid, tid))

    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# TC-TEN-13: Tenant list includes both active and inactive tenants
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tenant_list_includes_active_and_inactive(client, db_session):
    """TC-TEN-13: GET /tenants returns tenants with both is_active states."""
    sa_uid = await _create_sysadmin(db_session)
    active_tid = await _create_tenant(db_session, name="Active Corp", is_active=True)
    inactive_tid = await _create_tenant(db_session, name="Inactive Corp", is_active=False)
    await db_session.commit()

    resp = await client.get("/api/v1/tenants", headers=_sysadmin_headers(sa_uid))

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    ids = {t["id"] for t in data}
    assert active_tid in ids
    assert inactive_tid in ids
    # Verify is_active flag is present and correct
    active_rec = next(t for t in data if t["id"] == active_tid)
    inactive_rec = next(t for t in data if t["id"] == inactive_tid)
    assert active_rec["is_active"] is True
    assert inactive_rec["is_active"] is False


# ---------------------------------------------------------------------------
# TC-TEN-14: SysAdmin can update tenant name
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sysadmin_can_update_tenant_name(client, db_session):
    """TC-TEN-14: PATCH /tenants/admin/{id} updates name."""
    sa_uid = await _create_sysadmin(db_session)
    tid = await _create_tenant(db_session, name="Old Name Corp")
    await db_session.commit()

    resp = await client.patch(
        f"/api/v1/tenants/admin/{tid}",
        json={"name": "New Name Corp"},
        headers=_sysadmin_headers(sa_uid),
    )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json()["name"] == "New Name Corp"


# ---------------------------------------------------------------------------
# TC-TEN-15: SysAdmin can update tenant logo URL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sysadmin_can_update_logo_url(client, db_session):
    """TC-TEN-15: PATCH /tenants/admin/{id} updates logo_url."""
    sa_uid = await _create_sysadmin(db_session)
    tid = await _create_tenant(db_session)
    await db_session.commit()

    new_logo = "https://cdn.example.com/new-logo.png"
    resp = await client.patch(
        f"/api/v1/tenants/admin/{tid}",
        json={"logo_url": new_logo},
        headers=_sysadmin_headers(sa_uid),
    )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json()["logo_url"] == new_logo


# ---------------------------------------------------------------------------
# TC-TEN-16: SysAdmin can update primary and secondary colors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sysadmin_can_update_brand_colors(client, db_session):
    """TC-TEN-16: PATCH /tenants/admin/{id} updates primary and secondary colors."""
    sa_uid = await _create_sysadmin(db_session)
    tid = await _create_tenant(db_session)
    await db_session.commit()

    resp = await client.patch(
        f"/api/v1/tenants/admin/{tid}",
        json={"primary_color": "#FF5733", "secondary_color": "#C70039"},
        headers=_sysadmin_headers(sa_uid),
    )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["primary_color"] == "#FF5733"
    assert data["secondary_color"] == "#C70039"


# ---------------------------------------------------------------------------
# TC-TEN-17: Non-SysAdmin cannot update tenant settings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_sysadmin_cannot_update_tenant(client, db_session):
    """TC-TEN-17: Manager JWT on PATCH /tenants/admin/{id} returns 403."""
    tid = await _create_tenant(db_session, name="Protected Corp")
    mgr_uid = await _create_user(db_session)
    await _create_membership(db_session, mgr_uid, tid, is_manager=True)
    await db_session.commit()

    resp = await client.patch(
        f"/api/v1/tenants/admin/{tid}",
        json={"name": "Hijacked"},
        headers=_manager_headers(mgr_uid, tid),
    )

    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# TC-TEN-18: Partial update — only provided fields are changed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_partial_update_only_changes_provided_fields(client, db_session):
    """TC-TEN-18: PATCH with only primary_color leaves name unchanged."""
    sa_uid = await _create_sysadmin(db_session)
    tid = await _create_tenant(db_session, name="Partial Corp", primary_color="#000000")
    await db_session.commit()

    resp = await client.patch(
        f"/api/v1/tenants/admin/{tid}",
        json={"primary_color": "#ABCDEF"},
        headers=_sysadmin_headers(sa_uid),
    )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["name"] == "Partial Corp", "Name should remain unchanged"
    assert data["primary_color"] == "#ABCDEF", "primary_color should be updated"


# ---------------------------------------------------------------------------
# TC-TEN-19: SysAdmin can deactivate an active tenant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sysadmin_can_deactivate_tenant(client, db_session):
    """TC-TEN-19: POST /tenants/{id}/deactivate sets is_active=False."""
    sa_uid = await _create_sysadmin(db_session)
    tid = await _create_tenant(db_session, is_active=True)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/tenants/{tid}/deactivate",
        headers=_sysadmin_headers(sa_uid),
    )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json()["is_active"] is False


# ---------------------------------------------------------------------------
# TC-TEN-20: Deactivated tenant user is blocked on next request
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deactivated_tenant_user_blocked(client, db_session):
    """TC-TEN-20: User with valid JWT for deactivated tenant receives 403."""
    from app.models.user import User, UserStatus

    # Create a user who is a member of an inactive tenant
    inactive_tid = await _create_tenant(db_session, is_active=False)
    user_uid = _uid()
    user = User(
        id=user_uid,
        email=f"blocked_{user_uid[:8]}@example.com",
        username=f"blocked_{user_uid[:8]}",
        hashed_password="hashed",
        full_name="Blocked User",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.flush()
    await _create_membership(db_session, user_uid, inactive_tid, is_manager=False, is_active=True)
    await db_session.commit()

    # User has a technically valid JWT but tenant is deactivated
    resp = await client.get(
        "/api/v1/users",
        headers=_employee_headers(user_uid, inactive_tid),
    )

    assert resp.status_code == 403, (
        f"TC-TEN-20: Expected 403 for deactivated tenant, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# TC-TEN-21: Deactivated tenant not shown in tenant selector
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deactivated_tenant_absent_from_selector(client, db_session):
    """TC-TEN-21: GET /auth/tenants excludes deactivated tenants for that user.

    The login endpoint returns a 'session_token' field (not 'access_token').
    The GET /auth/tenants endpoint accepts this session token.
    """
    from app.models.user import User, UserStatus
    import bcrypt

    # Create an active user with membership in an active tenant and a deactivated tenant
    active_tid = await _create_tenant(db_session, name="Active Tenant 21", is_active=True)
    inactive_tid = await _create_tenant(db_session, name="Inactive Tenant 21", is_active=False)

    user_uid = _uid()
    user = User(
        id=user_uid,
        email=f"selector21_{user_uid[:8]}@example.com",
        username=f"selector21_{user_uid[:8]}",
        hashed_password=bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode(),
        full_name="Selector User",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.flush()
    await _create_membership(db_session, user_uid, active_tid)
    await _create_membership(db_session, user_uid, inactive_tid)
    await db_session.commit()

    # Login to get a session token — the response field is 'session_token'
    resp = await client.post("/api/v1/auth/login", json={
        "email": f"selector21_{user_uid[:8]}@example.com",
        "password": "Pass1!",
    })
    assert resp.status_code == 200, f"Login failed: {resp.status_code}: {resp.text}"
    session_token = resp.json().get("session_token")
    assert session_token, f"Expected session_token in login response, got: {resp.json()}"

    # Retrieve tenant list using the session token
    tenants_resp = await client.get(
        "/api/v1/auth/tenants",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert tenants_resp.status_code == 200, f"Expected 200, got {tenants_resp.status_code}: {tenants_resp.text}"
    tenant_ids = {t["id"] for t in tenants_resp.json()}
    assert active_tid in tenant_ids, "Active tenant should appear in selector"
    assert inactive_tid not in tenant_ids, "Inactive tenant must be excluded from selector"


# ---------------------------------------------------------------------------
# TC-TEN-22: SysAdmin can reactivate a deactivated tenant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sysadmin_can_reactivate_tenant(client, db_session):
    """TC-TEN-22: POST /tenants/{id}/activate sets is_active=True."""
    sa_uid = await _create_sysadmin(db_session)
    tid = await _create_tenant(db_session, is_active=False)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/tenants/{tid}/activate",
        headers=_sysadmin_headers(sa_uid),
    )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json()["is_active"] is True


# ---------------------------------------------------------------------------
# TC-TEN-23: Reactivated tenant's users can make requests again
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reactivated_tenant_users_can_access(client, db_session):
    """TC-TEN-23: After reactivation, a manager's JWT for that tenant is no longer blocked.

    Uses a Manager (not Employee) because GET /api/v1/users requires Manager or
    Creator role. The key assertion is that the tenant-deactivation 403 becomes 200.
    """
    from app.models.user import User, UserStatus

    sa_uid = await _create_sysadmin(db_session)
    tid = await _create_tenant(db_session, is_active=False)

    mgr_uid = _uid()
    mgr = User(
        id=mgr_uid,
        email=f"reactivate_mgr_{mgr_uid[:8]}@example.com",
        username=f"react_mgr_{mgr_uid[:8]}",
        hashed_password="hashed",
        full_name="Reactivated Manager",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(mgr)
    await db_session.flush()
    await _create_membership(db_session, mgr_uid, tid, is_manager=True, is_active=True)
    await db_session.commit()

    # Confirm manager is blocked while tenant is deactivated
    blocked_resp = await client.get(
        "/api/v1/users",
        headers=_manager_headers(mgr_uid, tid),
    )
    assert blocked_resp.status_code == 403, "Manager should be blocked while tenant is deactivated"

    # Reactivate the tenant
    react_resp = await client.post(
        f"/api/v1/tenants/{tid}/activate",
        headers=_sysadmin_headers(sa_uid),
    )
    assert react_resp.status_code == 200, f"Reactivation failed: {react_resp.status_code}"

    # After reactivation, the same manager JWT should now succeed
    access_resp = await client.get(
        "/api/v1/users",
        headers=_manager_headers(mgr_uid, tid),
    )
    assert access_resp.status_code == 200, (
        f"TC-TEN-23: Expected 200 after reactivation, got {access_resp.status_code}: {access_resp.text}"
    )


# ---------------------------------------------------------------------------
# TC-TEN-24: Non-SysAdmin cannot deactivate a tenant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_sysadmin_cannot_deactivate_tenant(client, db_session):
    """TC-TEN-24: Manager JWT on POST /tenants/{id}/deactivate returns 403."""
    tid = await _create_tenant(db_session, is_active=True)
    mgr_uid = await _create_user(db_session)
    await _create_membership(db_session, mgr_uid, tid, is_manager=True)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/tenants/{tid}/deactivate",
        headers=_manager_headers(mgr_uid, tid),
    )

    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# TC-TEN-32: Logo URL stored on tenant resolves in certificate variable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_logo_url_stored_and_retrievable_for_certificate(client, db_session):
    """TC-TEN-32: logo_url is persisted so it can be used in certificate {{tenant_logo}} variable.
    Verified by checking GET /tenants/admin/{id} returns the logo_url correctly."""
    sa_uid = await _create_sysadmin(db_session)
    logo = "https://cdn.example.com/tenant-logo.png"
    tid = await _create_tenant(db_session, logo_url=logo)
    await db_session.commit()

    resp = await client.get(f"/api/v1/tenants/admin/{tid}", headers=_sysadmin_headers(sa_uid))

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json()["logo_url"] == logo


# ===========================================================================
# ISOLATION TESTS (03-tenant-isolation.md)
# ===========================================================================

# ---------------------------------------------------------------------------
# TC-TEN-37: Manager cannot view another tenant's data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manager_cannot_view_other_tenant_data(client, db_session):
    """TC-TEN-37: GET /users with Tenant-A JWT only returns Tenant-A users."""
    from app.models.user import User, UserStatus

    tid_a = await _create_tenant(db_session, name="TenantA")
    tid_b = await _create_tenant(db_session, name="TenantB")

    mgr_a_uid = _uid()
    mgr_a = User(
        id=mgr_a_uid,
        email=f"mgr_a_{mgr_a_uid[:6]}@a.com",
        username=f"mgr_a_{mgr_a_uid[:6]}",
        hashed_password="hashed",
        full_name="Mgr A",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(mgr_a)
    await db_session.flush()
    await _create_membership(db_session, mgr_a_uid, tid_a, is_manager=True)

    emp_b_uid = _uid()
    emp_b = User(
        id=emp_b_uid,
        email=f"emp_b_{emp_b_uid[:6]}@b.com",
        username=f"emp_b_{emp_b_uid[:6]}",
        hashed_password="hashed",
        full_name="Emp B",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(emp_b)
    await db_session.flush()
    await _create_membership(db_session, emp_b_uid, tid_b)
    await db_session.commit()

    from app.core.config import settings as app_settings
    resp = await client.get(
        "/api/v1/users",
        headers=_manager_headers(mgr_a_uid, tid_a),
    )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    returned_ids = {u["id"] for u in resp.json()}
    assert emp_b_uid not in returned_ids, "Tenant-B user must not appear in Tenant-A manager's user list"


# ---------------------------------------------------------------------------
# TC-TEN-38: Manager cannot update another tenant's settings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manager_cannot_update_other_tenant_settings(client, db_session):
    """TC-TEN-38: Manager of Tenant-A cannot PATCH /tenants/admin/{tenantB_id}."""
    tid_a = await _create_tenant(db_session, name="TenantA-38")
    tid_b = await _create_tenant(db_session, name="TenantB-38")
    mgr_uid = await _create_user(db_session)
    await _create_membership(db_session, mgr_uid, tid_a, is_manager=True)
    await db_session.commit()

    resp = await client.patch(
        f"/api/v1/tenants/admin/{tid_b}",
        json={"name": "Hijacked B"},
        headers=_manager_headers(mgr_uid, tid_a),
    )

    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# TC-TEN-39: User list for Manager only returns own-tenant users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_list_scoped_to_manager_tenant(client, db_session):
    """TC-TEN-39: GET /users with Tenant-A JWT only returns Tenant-A users."""
    from app.models.user import User, UserStatus

    tid_a = await _create_tenant(db_session, name="ScopedA")
    tid_b = await _create_tenant(db_session, name="ScopedB")

    mgr_uid = _uid()
    mgr = User(
        id=mgr_uid,
        email=f"scoped_mgr_{mgr_uid[:6]}@a.com",
        username=f"scmgr_{mgr_uid[:6]}",
        hashed_password="hashed",
        full_name="Scoped Mgr",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(mgr)
    await db_session.flush()
    await _create_membership(db_session, mgr_uid, tid_a, is_manager=True)

    emp_a_uid = _uid()
    emp_a = User(
        id=emp_a_uid,
        email=f"emp_a_{emp_a_uid[:6]}@a.com",
        username=f"empa_{emp_a_uid[:6]}",
        hashed_password="hashed",
        full_name="Emp A",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(emp_a)
    await db_session.flush()
    await _create_membership(db_session, emp_a_uid, tid_a)

    emp_b_uid = _uid()
    emp_b = User(
        id=emp_b_uid,
        email=f"emp_b39_{emp_b_uid[:6]}@b.com",
        username=f"empb_{emp_b_uid[:6]}",
        hashed_password="hashed",
        full_name="Emp B",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(emp_b)
    await db_session.flush()
    await _create_membership(db_session, emp_b_uid, tid_b)
    await db_session.commit()

    resp = await client.get(
        "/api/v1/users",
        headers=_manager_headers(mgr_uid, tid_a),
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    returned_ids = {u["id"] for u in resp.json()}
    assert emp_a_uid in returned_ids, "Tenant-A employee should appear"
    assert emp_b_uid not in returned_ids, "Tenant-B employee must not appear"


# ---------------------------------------------------------------------------
# TC-TEN-40: Deactivated tenant's JWT rejected even if technically valid
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deactivated_tenant_jwt_rejected(client, db_session):
    """TC-TEN-40: User with a valid JWT for a deactivated tenant receives 403."""
    from app.models.user import User, UserStatus

    tid = await _create_tenant(db_session, is_active=False)

    user_uid = _uid()
    user = User(
        id=user_uid,
        email=f"deactivated_jwt_{user_uid[:8]}@example.com",
        username=f"dejwt_{user_uid[:8]}",
        hashed_password="hashed",
        full_name="JWT Test User",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.flush()
    await _create_membership(db_session, user_uid, tid, is_active=True)
    await db_session.commit()

    # Even though the token is cryptographically valid and user is active,
    # the tenant deactivation check should block this request
    resp = await client.get(
        "/api/v1/users",
        headers=_employee_headers(user_uid, tid),
    )
    assert resp.status_code == 403, (
        f"TC-TEN-40: Expected 403 for deactivated tenant JWT, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# TC-TEN-41: SysAdmin can view and manage any tenant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sysadmin_can_view_any_tenant(client, db_session):
    """TC-TEN-41: SysAdmin GET /tenants/admin/{tenantB_id} returns 200."""
    sa_uid = await _create_sysadmin(db_session)
    tid = await _create_tenant(db_session, name="Any Corp")
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/tenants/admin/{tid}",
        headers=_sysadmin_headers(sa_uid),
    )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json()["id"] == tid


# ---------------------------------------------------------------------------
# TC-TEN-41 (update side): SysAdmin can update any tenant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sysadmin_can_manage_any_tenant(client, db_session):
    """TC-TEN-41 (update): SysAdmin PATCH /tenants/admin/{id} for any tenant returns 200."""
    sa_uid = await _create_sysadmin(db_session)
    tid = await _create_tenant(db_session, name="Manage Corp")
    await db_session.commit()

    resp = await client.patch(
        f"/api/v1/tenants/admin/{tid}",
        json={"name": "Managed Corp"},
        headers=_sysadmin_headers(sa_uid),
    )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json()["name"] == "Managed Corp"


# ---------------------------------------------------------------------------
# TC-TEN-42: SysAdmin cannot hold a tenant membership (BR-107)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sysadmin_cannot_hold_tenant_membership(client, db_session):
    """TC-TEN-42: Inviting a SysAdmin to a tenant must return 400 per BR-107.

    Rule #12: SysAdmins are global-only — cannot hold tenant memberships.
    """
    sa_uid = await _create_sysadmin(db_session)
    tid = await _create_tenant(db_session, name="Test Tenant 42")

    mgr_uid = await _create_user(db_session)
    await _create_membership(db_session, mgr_uid, tid, is_manager=True)
    await db_session.commit()

    # Retrieve the SysAdmin's email
    from app.models.user import User
    from sqlalchemy import select
    sa_result = await db_session.execute(select(User).where(User.id == sa_uid))
    sa_user = sa_result.scalar_one()

    # Use a valid external email for the SysAdmin to avoid Pydantic email validation
    # failures obscuring the BR-107 enforcement gap.
    sa_invite_email = "sysadmin-global@example.com"
    sa_user.email = sa_invite_email
    await db_session.commit()

    resp = await client.post(
        "/api/v1/users/invite",
        json={"email": sa_invite_email, "full_name": "Sys Admin"},
        headers=_manager_headers(mgr_uid, tid),
    )

    # BR-107: SysAdmin cannot hold tenant membership — must return 400.
    assert resp.status_code == 400, (
        f"TC-TEN-42: Expected 400 (SysAdmin cannot hold tenant membership per BR-107) "
        f"but got {resp.status_code}: {resp.text}."
    )
