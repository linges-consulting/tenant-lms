"""
Dashboard endpoint tests — Task 9.

Auth pattern:
  The core service validates JWTs via an outbound HTTP call to auth-service.
  Tests must override get_current_user (and optionally get_current_tenant_id)
  directly via app.dependency_overrides.  Bearer tokens have no effect here.
"""

import pytest
import uuid

from app.main import app
from app.api.deps import get_current_user, get_current_tenant_id
from tests.conftest import override_current_user, make_user_auth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_user(user):
    """Install dependency overrides for current user and tenant_id."""
    tenant_id = user.tenant_id
    app.dependency_overrides[get_current_user] = override_current_user(user)

    async def _tenant_id():
        return tenant_id

    app.dependency_overrides[get_current_tenant_id] = _tenant_id


def _clear_overrides():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_tenant_id, None)


# ---------------------------------------------------------------------------
# test_manager_dashboard: Business Manager gets dashboard summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manager_dashboard(client, db_session):
    """
    T-DB-01: Business Manager calling GET /api/v1/dashboards/manager
    receives 200 with required summary fields.
    """
    tenant_id = str(uuid.uuid4())
    user = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Business Manager"],
    )
    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/manager")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "total_employees" in data, "Response missing 'total_employees'"
        assert "overdue_assignments" in data, "Response missing 'overdue_assignments'"
        assert "quiz_lockouts" in data, "Response missing 'quiz_lockouts'"
        assert "completion_rate" in data, "Response missing 'completion_rate'"
        assert "total_assignments" in data, "Response missing 'total_assignments'"
        assert "completed_assignments" in data, "Response missing 'completed_assignments'"
        # With empty DB the counts should be 0
        assert data["overdue_assignments"] == 0
        assert data["quiz_lockouts"] == 0
        assert data["completion_rate"] == 0.0
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_manager_dashboard_forbidden_for_employee(client, db_session):
    """
    T-DB-02: An employee must receive 403 when calling the manager dashboard.
    """
    tenant_id = str(uuid.uuid4())
    user = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Employee"],
    )
    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/manager")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# test_creator_dashboard: Training Creator gets their training stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_creator_dashboard(client, db_session):
    """
    T-DB-03: Training Creator calling GET /api/v1/dashboards/creator
    receives 200 with total_trainings, published, and draft fields.
    """
    tenant_id = str(uuid.uuid4())
    user = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Training Creator"],
    )
    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/creator")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "total_trainings" in data, "Response missing 'total_trainings'"
        assert "published" in data, "Response missing 'published'"
        assert "draft" in data, "Response missing 'draft'"
        # With empty DB counts should be 0
        assert data["total_trainings"] == 0
        assert data["published"] == 0
        assert data["draft"] == 0
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_creator_dashboard_forbidden_for_employee(client, db_session):
    """
    T-DB-04: An employee must receive 403 when calling the creator dashboard.
    """
    tenant_id = str(uuid.uuid4())
    user = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Employee"],
    )
    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/creator")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# test_employee_dashboard: Any authenticated user gets personal training view
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_employee_dashboard(client, db_session):
    """
    T-DB-05: Any authenticated user calling GET /api/v1/dashboards/employee
    receives 200 with in_progress, upcoming_due, and recently_completed fields.
    """
    tenant_id = str(uuid.uuid4())
    user = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Employee"],
    )
    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/employee")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "in_progress" in data, "Response missing 'in_progress'"
        assert "upcoming_due" in data, "Response missing 'upcoming_due'"
        assert "recently_completed" in data, "Response missing 'recently_completed'"
        # With empty DB all lists should be empty
        assert isinstance(data["in_progress"], list)
        assert isinstance(data["upcoming_due"], list)
        assert isinstance(data["recently_completed"], list)
        assert len(data["in_progress"]) == 0
        assert len(data["upcoming_due"]) == 0
        assert len(data["recently_completed"]) == 0
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_employee_dashboard_accessible_by_manager(client, db_session):
    """
    T-DB-06: A Business Manager can also access the employee dashboard (any auth user).
    """
    tenant_id = str(uuid.uuid4())
    user = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Business Manager"],
    )
    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/employee")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()
