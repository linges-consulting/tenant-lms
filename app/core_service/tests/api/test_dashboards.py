"""
Dashboard endpoint tests.

Auth pattern:
  The core service validates JWTs via an outbound HTTP call to auth-service.
  Tests must override get_current_user (and optionally get_current_tenant_id)
  directly via app.dependency_overrides.  Bearer tokens have no effect here.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta

from app.main import app
from app.api.deps import get_current_user, get_current_tenant_id
from app.models.training import Training
from app.models.assignment import TrainingAssignment
from app.models.enrollment import Enrollment
from tests.conftest import override_current_user, make_user_auth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_user(user):
    tenant_id = user.tenant_id
    app.dependency_overrides[get_current_user] = override_current_user(user)

    async def _tenant_id():
        return tenant_id

    app.dependency_overrides[get_current_tenant_id] = _tenant_id


def _clear_overrides():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_tenant_id, None)


def _make_published_training(tenant_id: str, training_id: str = None) -> Training:
    return Training(
        id=training_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Test Training",
        category="Compliance",
        version=1,
        is_published=True,
        is_ready=True,
        is_archived=False,
        is_active=True,
        requires_certificate=False,
    )


def _make_assignment(
    training_id: str,
    tenant_id: str,
    user_id: str = None,
    group_id: str = None,
    due_date: datetime = None,
) -> TrainingAssignment:
    return TrainingAssignment(
        id=str(uuid.uuid4()),
        training_id=training_id,
        tenant_id=tenant_id,
        user_id=user_id,
        group_id=group_id,
        due_date=due_date,
        assigned_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Manager dashboard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manager_dashboard_returns_correct_fields(client, db_session):
    """T-DB-01: Manager dashboard returns all required summary fields."""
    tenant_id = str(uuid.uuid4())
    user = make_user_auth(tenant_id=tenant_id, roles=["Business Manager"])
    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/manager")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        for field in ("total_trainings", "active_assignments", "overdue_count",
                      "quiz_lockouts", "completion_rate", "completed_assignments"):
            assert field in data, f"Response missing '{field}'"
        assert data["overdue_count"] == 0
        assert data["quiz_lockouts"] == 0
        assert data["completion_rate"] == 0.0
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_manager_dashboard_counts_overdue_user_assignments(client, db_session):
    """T-DB-02: overdue_count includes direct user assignments past their due date."""
    tenant_id = str(uuid.uuid4())
    manager = make_user_auth(tenant_id=tenant_id, roles=["Business Manager"])
    learner_id = str(uuid.uuid4())

    training = _make_published_training(tenant_id)
    past = datetime.now(timezone.utc) - timedelta(days=3)
    assignment = _make_assignment(training.id, tenant_id, user_id=learner_id, due_date=past)

    db_session.add(training)
    db_session.add(assignment)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.get("/api/v1/dashboards/manager")
        assert resp.status_code == 200, resp.text
        assert resp.json()["overdue_count"] == 1
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_manager_dashboard_counts_overdue_group_assignments(client, db_session):
    """T-DB-03: overdue_count includes group assignments past their due date."""
    tenant_id = str(uuid.uuid4())
    manager = make_user_auth(tenant_id=tenant_id, roles=["Business Manager"])
    group_id = str(uuid.uuid4())

    training = _make_published_training(tenant_id)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    assignment = _make_assignment(training.id, tenant_id, group_id=group_id, due_date=past)

    db_session.add(training)
    db_session.add(assignment)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.get("/api/v1/dashboards/manager")
        assert resp.status_code == 200, resp.text
        assert resp.json()["overdue_count"] == 1
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_manager_dashboard_completed_not_counted_as_overdue(client, db_session):
    """T-DB-04: A completed enrollment removes the assignment from overdue_count."""
    tenant_id = str(uuid.uuid4())
    manager = make_user_auth(tenant_id=tenant_id, roles=["Business Manager"])
    learner_id = str(uuid.uuid4())

    training = _make_published_training(tenant_id)
    past = datetime.now(timezone.utc) - timedelta(days=2)
    assignment = _make_assignment(training.id, tenant_id, user_id=learner_id, due_date=past)
    enrollment = Enrollment(
        id=str(uuid.uuid4()),
        training_id=training.id,
        user_id=learner_id,
        tenant_id=tenant_id,
        is_completed=True,
        enrolled_at=datetime.now(timezone.utc),
    )

    db_session.add_all([training, assignment, enrollment])
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.get("/api/v1/dashboards/manager")
        assert resp.status_code == 200, resp.text
        assert resp.json()["overdue_count"] == 0
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_manager_dashboard_forbidden_for_employee(client, db_session):
    """T-DB-05: Employee receives 403 on manager dashboard."""
    user = make_user_auth(tenant_id=str(uuid.uuid4()), roles=["Employee"])
    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/manager")
        assert resp.status_code == 403
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# Creator dashboard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_creator_dashboard_returns_correct_fields(client, db_session):
    """T-DB-06: Creator dashboard returns total_trainings, published_count, draft_count."""
    user = make_user_auth(tenant_id=str(uuid.uuid4()), roles=["Training Creator"])
    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/creator")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        for field in ("total_trainings", "published_count", "draft_count", "total_enrollments"):
            assert field in data, f"Response missing '{field}'"
        assert data["total_trainings"] == 0
        assert data["published_count"] == 0
        assert data["draft_count"] == 0
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_creator_dashboard_forbidden_for_employee(client, db_session):
    """T-DB-07: Employee receives 403 on creator dashboard."""
    user = make_user_auth(tenant_id=str(uuid.uuid4()), roles=["Employee"])
    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/creator")
        assert resp.status_code == 403
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# Employee dashboard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_employee_dashboard_returns_correct_fields(client, db_session):
    """T-DB-08: Employee dashboard returns assigned, in_progress, completed, overdue counts."""
    user = make_user_auth(tenant_id=str(uuid.uuid4()), roles=["Employee"])
    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/employee")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        for field in ("assigned_trainings", "in_progress_trainings",
                      "completed_trainings", "overdue_trainings"):
            assert field in data, f"Response missing '{field}'"
        assert data["assigned_trainings"] == 0
        assert data["overdue_trainings"] == 0
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_employee_dashboard_overdue_counts_direct_assignment(client, db_session):
    """T-DB-09: overdue_trainings increments when user has a past-due direct assignment."""
    tenant_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    user = make_user_auth(user_id=learner_id, tenant_id=tenant_id, roles=["Employee"])

    training = _make_published_training(tenant_id)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    assignment = _make_assignment(training.id, tenant_id, user_id=learner_id, due_date=past)

    db_session.add_all([training, assignment])
    await db_session.commit()

    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/employee")
        assert resp.status_code == 200, resp.text
        assert resp.json()["overdue_trainings"] == 1
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_employee_dashboard_overdue_counts_group_assignment(client, db_session):
    """T-DB-10: overdue_trainings includes group assignments when user is a group member."""
    tenant_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    group_id = str(uuid.uuid4())
    # Inject the group into the user's JWT groups list
    user = make_user_auth(user_id=learner_id, tenant_id=tenant_id, roles=["Employee"])
    user.groups = [group_id]

    training = _make_published_training(tenant_id)
    past = datetime.now(timezone.utc) - timedelta(days=2)
    assignment = _make_assignment(training.id, tenant_id, group_id=group_id, due_date=past)

    db_session.add_all([training, assignment])
    await db_session.commit()

    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/employee")
        assert resp.status_code == 200, resp.text
        assert resp.json()["overdue_trainings"] == 1
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_employee_dashboard_completed_not_overdue(client, db_session):
    """T-DB-11: A completed training is not counted as overdue even if past due date."""
    tenant_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    user = make_user_auth(user_id=learner_id, tenant_id=tenant_id, roles=["Employee"])

    training = _make_published_training(tenant_id)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    assignment = _make_assignment(training.id, tenant_id, user_id=learner_id, due_date=past)
    enrollment = Enrollment(
        id=str(uuid.uuid4()),
        training_id=training.id,
        user_id=learner_id,
        tenant_id=tenant_id,
        is_completed=True,
        enrolled_at=datetime.now(timezone.utc),
    )

    db_session.add_all([training, assignment, enrollment])
    await db_session.commit()

    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/employee")
        assert resp.status_code == 200, resp.text
        assert resp.json()["overdue_trainings"] == 0
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_employee_dashboard_accessible_by_manager(client, db_session):
    """T-DB-12: Business Manager can also call the employee dashboard."""
    user = make_user_auth(tenant_id=str(uuid.uuid4()), roles=["Business Manager"])
    _set_user(user)
    try:
        resp = await client.get("/api/v1/dashboards/employee")
        assert resp.status_code == 200
    finally:
        _clear_overrides()
