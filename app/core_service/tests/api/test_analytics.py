import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock
from app.main import app
from app.api.deps import get_current_user, get_current_tenant_id
from app.models.training import Training
from app.models.assignment import TrainingAssignment
from app.models.enrollment import Enrollment
from app.models.chapter import Chapter, ContentType
from tests.conftest import override_current_user, make_user_auth


def _make_manager(tenant_id: str):
    return make_user_auth(user_id=str(uuid.uuid4()), tenant_id=tenant_id, roles=["Business Manager"])


def _set_user(user):
    app.dependency_overrides[get_current_user] = override_current_user(user)
    async def _tid(): return user.tenant_id
    app.dependency_overrides[get_current_tenant_id] = _tid


def _clear():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_tenant_id, None)


@pytest.mark.asyncio
async def test_analytics_list_returns_trainings(client, db_session):
    tid = str(uuid.uuid4())
    user = _make_manager(tid)
    _set_user(user)
    learner_id = str(uuid.uuid4())
    training = Training(
        id=str(uuid.uuid4()), tenant_id=tid, title="Safety 101",
        category="Safety", is_published=True, created_by_id=user.id,
    )
    db_session.add(training)
    # Assignment + matching Enrollment (auth service creates both in production)
    db_session.add(TrainingAssignment(
        id=str(uuid.uuid4()), tenant_id=tid,
        training_id=training.id, user_id=learner_id,
    ))
    db_session.add(Enrollment(
        id=str(uuid.uuid4()), tenant_id=tid,
        training_id=training.id, user_id=learner_id,
    ))
    await db_session.commit()
    try:
        with patch("app.api.v1.endpoints.analytics.deps.get_users_batch", new_callable=AsyncMock) as mock_batch:
            mock_batch.return_value = {user.id: {"full_name": "Test User", "email": "t@t.com", "username": "testuser"}}
            resp = await client.get("/api/v1/analytics/trainings")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Safety 101"
        assert data[0]["enrolled_count"] == 1
        assert data[0]["completed_count"] == 0
        assert data[0]["completion_pct"] == 0.0
        assert data[0]["overdue_count"] == 0
        assert data[0]["lockout_count"] == 0
    finally:
        _clear()


@pytest.mark.asyncio
async def test_analytics_list_tenant_isolation(client, db_session):
    """Trainings from a different tenant must not appear in results."""
    tid_a = str(uuid.uuid4())
    tid_b = str(uuid.uuid4())
    user_a = _make_manager(tid_a)
    _set_user(user_a)

    # Tenant A training
    training_a = Training(
        id=str(uuid.uuid4()), tenant_id=tid_a, title="A Training",
        category="Safety", is_published=True, created_by_id=user_a.id,
    )
    # Tenant B training — must NOT appear in tenant A's results
    training_b = Training(
        id=str(uuid.uuid4()), tenant_id=tid_b, title="B Training",
        category="Safety", is_published=True, created_by_id=str(uuid.uuid4()),
    )
    db_session.add(training_a)
    db_session.add(training_b)
    await db_session.commit()
    try:
        with patch("app.api.v1.endpoints.analytics.deps.get_users_batch", new_callable=AsyncMock) as mb:
            mb.return_value = {}
            resp = await client.get("/api/v1/analytics/trainings")
        assert resp.status_code == 200
        data = resp.json()
        titles = [t["title"] for t in data]
        assert "A Training" in titles
        assert "B Training" not in titles
    finally:
        _clear()


@pytest.mark.asyncio
async def test_analytics_detail_overview(client, db_session):
    """Detail endpoint returns overview stats for a training."""
    tid = str(uuid.uuid4())
    user = _make_manager(tid)
    learner_id = str(uuid.uuid4())
    _set_user(user)

    training = Training(
        id=str(uuid.uuid4()), tenant_id=tid, title="Health & Safety",
        category="HR", is_published=True, created_by_id=user.id,
    )
    db_session.add(training)
    assignment = TrainingAssignment(
        id=str(uuid.uuid4()), tenant_id=tid,
        training_id=training.id, user_id=learner_id,
    )
    db_session.add(assignment)
    enrollment = Enrollment(
        id=str(uuid.uuid4()), tenant_id=tid,
        training_id=training.id, user_id=learner_id,
        is_completed=True, completed_at=datetime.now(timezone.utc),
    )
    db_session.add(enrollment)
    await db_session.commit()
    try:
        with patch("app.api.v1.endpoints.analytics.deps.get_users_batch", new_callable=AsyncMock) as mock_b:
            mock_b.return_value = {
                learner_id: {"full_name": "Learner One", "email": "l@t.com", "username": "learner1"},
                user.id: {"full_name": "Manager", "email": "m@t.com", "username": "manager1"},
            }
            resp = await client.get(f"/api/v1/analytics/trainings/{training.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enrolled_count"] == 1
        assert data["completed_count"] == 1
        assert data["completion_pct"] == 100.0
        assert data["overdue_count"] == 0
        assert len(data["employees"]) == 1
        assert data["employees"][0]["status"] == "completed"
    finally:
        _clear()


@pytest.mark.asyncio
async def test_analytics_detail_quiz_stats(client, db_session):
    """Detail endpoint returns per-quiz chapter stats."""
    from app.models.quiz_attempt import QuizAttempt as QA
    tid = str(uuid.uuid4())
    user = _make_manager(tid)
    learner_id = str(uuid.uuid4())
    _set_user(user)

    training = Training(
        id=str(uuid.uuid4()), tenant_id=tid, title="Fire Safety",
        category="Safety", is_published=True, created_by_id=user.id,
    )
    db_session.add(training)
    chapter = Chapter(
        id=str(uuid.uuid4()), tenant_id=tid, training_id=training.id,
        title="Fire Quiz", content_type=ContentType.QUIZ,
        content_data={"max_attempts": 3, "questions": []}, sequence_order=1,
    )
    db_session.add(chapter)
    assignment = TrainingAssignment(
        id=str(uuid.uuid4()), tenant_id=tid,
        training_id=training.id, user_id=learner_id,
    )
    db_session.add(assignment)
    attempt = QA(
        id=str(uuid.uuid4()), tenant_id=tid, user_id=learner_id,
        chapter_id=chapter.id, attempt_number=1, score=80.0, passed=True,
        enrollment_attempt_id=1,
    )
    db_session.add(attempt)
    await db_session.commit()
    try:
        with patch("app.api.v1.endpoints.analytics.deps.get_users_batch", new_callable=AsyncMock) as mock_b:
            mock_b.return_value = {learner_id: {"full_name": "L", "email": "l@t.com", "username": "l1"}}
            resp = await client.get(f"/api/v1/analytics/trainings/{training.id}")
        assert resp.status_code == 200
        data = resp.json()
        quizzes = data["quiz_chapters"]
        assert len(quizzes) == 1
        assert quizzes[0]["pass_rate"] == 100.0
        assert quizzes[0]["avg_score"] == 80.0
        assert quizzes[0]["locked_count"] == 0
    finally:
        _clear()


@pytest.mark.asyncio
async def test_employee_drill_down(client, db_session):
    from app.models.chapter import Chapter, ContentType
    from app.models.quiz_attempt import QuizAttempt as QA
    tid = str(uuid.uuid4())
    user = _make_manager(tid)
    learner_id = str(uuid.uuid4())
    _set_user(user)

    training = Training(
        id=str(uuid.uuid4()), tenant_id=tid, title="T", category="C",
        is_published=True, created_by_id=user.id,
    )
    db_session.add(training)
    db_session.add(TrainingAssignment(
        id=str(uuid.uuid4()), tenant_id=tid,
        training_id=training.id, user_id=learner_id,
    ))
    chapter = Chapter(
        id=str(uuid.uuid4()), tenant_id=tid, training_id=training.id,
        title="Quiz 1", content_type=ContentType.QUIZ,
        content_data={"max_attempts": 3, "questions": []}, sequence_order=1,
    )
    db_session.add(chapter)
    for i in range(1, 3):
        db_session.add(QA(
            id=str(uuid.uuid4()), tenant_id=tid, user_id=learner_id,
            chapter_id=chapter.id, attempt_number=i, score=50.0 + i * 10,
            passed=(i == 2), enrollment_attempt_id=1,
        ))
    await db_session.commit()
    try:
        resp = await client.get(
            f"/api/v1/analytics/trainings/{training.id}/employees/{learner_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["chapter_title"] == "Quiz 1"
        assert len(data[0]["attempts"]) == 2
        assert data[0]["attempts"][1]["passed"] is True
    finally:
        _clear()


@pytest.mark.asyncio
async def test_list_report_csv(client, db_session):
    tid = str(uuid.uuid4())
    user = _make_manager(tid)
    _set_user(user)
    training = Training(
        id=str(uuid.uuid4()), tenant_id=tid, title="CSV Training",
        category="Safety", is_published=True, created_by_id=user.id,
    )
    db_session.add(training)
    await db_session.commit()
    try:
        with patch("app.api.v1.endpoints.analytics.deps.get_users_batch", new_callable=AsyncMock) as mb:
            mb.return_value = {}
            resp = await client.get("/api/v1/analytics/report?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "CSV Training" in resp.text
    finally:
        _clear()


@pytest.mark.asyncio
async def test_detail_report_csv(client, db_session):
    tid = str(uuid.uuid4())
    user = _make_manager(tid)
    learner_id = str(uuid.uuid4())
    _set_user(user)
    training = Training(
        id=str(uuid.uuid4()), tenant_id=tid, title="T",
        category="C", is_published=True, created_by_id=user.id,
    )
    db_session.add(training)
    db_session.add(TrainingAssignment(
        id=str(uuid.uuid4()), tenant_id=tid,
        training_id=training.id, user_id=learner_id,
    ))
    await db_session.commit()
    try:
        with patch("app.api.v1.endpoints.analytics.deps.get_users_batch", new_callable=AsyncMock) as mb:
            mb.return_value = {learner_id: {"full_name": "Learner", "email": "l@t.com", "username": "l"}}
            resp = await client.get(f"/api/v1/analytics/trainings/{training.id}/report?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
    finally:
        _clear()


@pytest.mark.asyncio
async def test_profile_training_history(client, db_session):
    tid = str(uuid.uuid4())
    user = _make_manager(tid)
    learner_id = str(uuid.uuid4())
    _set_user(user)

    training = Training(
        id=str(uuid.uuid4()), tenant_id=tid, title="Compliance",
        category="HR", is_published=True, created_by_id=user.id,
    )
    db_session.add(training)
    db_session.add(TrainingAssignment(
        id=str(uuid.uuid4()), tenant_id=tid,
        training_id=training.id, user_id=learner_id,
    ))
    db_session.add(Enrollment(
        id=str(uuid.uuid4()), tenant_id=tid,
        training_id=training.id, user_id=learner_id,
        is_completed=True, completed_at=datetime.now(timezone.utc),
    ))
    await db_session.commit()
    try:
        resp = await client.get(f"/api/v1/analytics/profile/{learner_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Compliance"
        assert data[0]["status"] == "completed"
    finally:
        _clear()


@pytest.mark.asyncio
async def test_send_reminder_publishes_event(client, db_session):
    tid = str(uuid.uuid4())
    user = _make_manager(tid)
    learner_id = str(uuid.uuid4())
    _set_user(user)

    training = Training(
        id=str(uuid.uuid4()), tenant_id=tid, title="Fire Safety",
        category="Safety", is_published=True, created_by_id=user.id,
    )
    db_session.add(training)
    db_session.add(TrainingAssignment(
        id=str(uuid.uuid4()), tenant_id=tid,
        training_id=training.id, user_id=learner_id,
    ))
    await db_session.commit()

    try:
        with patch("app.api.v1.endpoints.analytics.publisher") as mock_pub, \
             patch("app.api.v1.endpoints.analytics.deps.get_users_batch", new_callable=AsyncMock) as mock_b:
            mock_pub.publish_event = AsyncMock()
            mock_b.return_value = {learner_id: {"full_name": "Lee", "email": "lee@t.com", "username": "lee"}}
            resp = await client.post(
                f"/api/v1/analytics/trainings/{training.id}/send-reminder",
                json={"user_ids": [learner_id]},
            )
        assert resp.status_code == 200
        mock_pub.publish_event.assert_called_once()
        call_args = mock_pub.publish_event.call_args
        assert call_args[0][0] == "TRAINING_REMINDER"
        assert call_args[0][1]["user_id"] == learner_id
    finally:
        _clear()
