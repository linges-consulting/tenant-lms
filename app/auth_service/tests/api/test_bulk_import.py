import pytest
import io
import csv
import uuid
import bcrypt
from tests.conftest import make_sysadmin_jwt, make_manager_jwt


def make_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["email", "first_name", "last_name", "is_business_manager", "is_training_creator"],
    )
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode()


async def _setup_sysadmin(db_session):
    """Create a real SysAdmin user in DB and return (user_id, jwt_token)."""
    from app.models.user import User, UserStatus
    from app.core.config import settings as app_settings

    sysadmin_id = str(uuid.uuid4())
    sysadmin = User(
        id=sysadmin_id,
        email=f"sysadmin-{sysadmin_id[:8]}@example.com",
        username=f"sysadmin_{sysadmin_id[:8]}",
        hashed_password=bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode(),
        full_name="Sys Admin",
        is_sysadmin=True,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add(sysadmin)
    await db_session.commit()

    token = make_sysadmin_jwt(user_id=sysadmin_id, secret=app_settings.EXTERNAL_JWT_SECRET)
    return sysadmin_id, token


async def _setup_tenant(db_session, name="BulkT", suffix=None):
    """Create a Tenant in DB and return its id."""
    from app.models.tenant import Tenant

    tenant_id = str(uuid.uuid4())
    slug_safe = (suffix or tenant_id[:6]).replace("-", "")
    tenant = Tenant(
        id=tenant_id,
        name=f"{name}-{slug_safe}",
        is_active=True,
        primary_color="#000000",
        secondary_color="#ffffff",
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant_id


@pytest.mark.asyncio
async def test_bulk_import_returns_report(client, db_session):
    """T-BI-01: SysAdmin bulk import succeeds for all valid rows."""
    tenant_id = await _setup_tenant(db_session, name="BulkT", suffix="bulk1")
    _, token = await _setup_sysadmin(db_session)

    csv_data = make_csv([
        {
            "email": "a@example.com",
            "first_name": "Alice",
            "last_name": "Alpha",
            "is_business_manager": "false",
            "is_training_creator": "false",
        },
        {
            "email": "b@example.com",
            "first_name": "Bob",
            "last_name": "Beta",
            "is_business_manager": "false",
            "is_training_creator": "false",
        },
    ])
    resp = await client.post(
        f"/api/v1/users/bulk-import?tenant_id={tenant_id}",
        files={"file": ("users.csv", csv_data, "text/csv")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"Unexpected {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "successes" in data
    assert "failures" in data
    assert len(data["successes"]) == 2
    assert len(data["failures"]) == 0


@pytest.mark.asyncio
async def test_bulk_import_requires_sysadmin(client, db_session):
    """T-BI-02: Non-SysAdmin (manager) is rejected with 403."""
    from app.core.config import settings as app_settings
    from app.models.user import User, UserStatus
    from app.models.membership import TenantMembership

    tenant_id = await _setup_tenant(db_session, name="BulkT", suffix="bulk2")
    manager_id = str(uuid.uuid4())

    manager = User(
        id=manager_id,
        email=f"mgr-{manager_id[:8]}@example.com",
        username=f"mgr_{manager_id[:8]}",
        hashed_password=bcrypt.hashpw(b"Pass1!", bcrypt.gensalt()).decode(),
        full_name="Manager",
        is_sysadmin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
    )
    mem = TenantMembership(
        user_id=manager_id,
        tenant_id=tenant_id,
        is_active=True,
        is_business_manager=True,
        is_employee=True,
        status=UserStatus.ACTIVE,
    )
    db_session.add_all([manager, mem])
    await db_session.commit()

    token = make_manager_jwt(manager_id, tenant_id, secret=app_settings.EXTERNAL_JWT_SECRET)
    csv_data = make_csv([
        {
            "email": "x@example.com",
            "first_name": "X",
            "last_name": "Y",
            "is_business_manager": "false",
            "is_training_creator": "false",
        }
    ])
    resp = await client.post(
        f"/api/v1/users/bulk-import?tenant_id={tenant_id}",
        files={"file": ("users.csv", csv_data, "text/csv")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_bulk_import_partial_success(client, db_session):
    """T-BI-03: Invalid rows land in failures; valid rows are still processed."""
    tenant_id = await _setup_tenant(db_session, name="BulkT", suffix="bulk3")
    _, token = await _setup_sysadmin(db_session)

    csv_data = make_csv([
        {
            "email": "good@example.com",
            "first_name": "Good",
            "last_name": "User",
            "is_business_manager": "false",
            "is_training_creator": "false",
        },
        {
            "email": "not-an-email",
            "first_name": "",
            "last_name": "",
            "is_business_manager": "false",
            "is_training_creator": "false",
        },
    ])
    resp = await client.post(
        f"/api/v1/users/bulk-import?tenant_id={tenant_id}",
        files={"file": ("users.csv", csv_data, "text/csv")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"Unexpected {resp.status_code}: {resp.text}"
    data = resp.json()
    assert len(data["successes"]) == 1
    assert len(data["failures"]) == 1
    assert "invalid email" in data["failures"][0]["reason"].lower()
