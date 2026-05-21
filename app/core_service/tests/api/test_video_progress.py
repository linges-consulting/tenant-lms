"""
Video progress endpoint tests — Phase 3 Task 8.

Tests T-CO-81 and T-CO-82: POST /api/v1/progress/video saves resume position
and milestones, and marks a chapter COMPLETED when milestone_100 + video_ended.

Auth pattern:
  Core service validates JWTs via an outbound HTTP call to auth-service.
  Tests must override get_current_user AND get_current_tenant_id directly via
  app.dependency_overrides — Bearer tokens have no effect here.
"""

import pytest
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.main import app
from app.api.deps import get_current_user, get_current_tenant_id
from tests.conftest import override_current_user, make_user_auth
from app.models.training import Training
from app.models.chapter import Chapter, ContentType
from app.models.progress import UserProgress, ProgressStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_learner(tenant_id: str, user_id: str = None):
    return make_user_auth(
        user_id=user_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Employee"],
    )


def _set_user(user):
    """Install dependency overrides for current user and tenant_id."""
    app.dependency_overrides[get_current_user] = override_current_user(user)

    async def _tenant_id():
        return user.tenant_id

    app.dependency_overrides[get_current_tenant_id] = _tenant_id


def _clear_overrides():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_tenant_id, None)


async def _create_video_training(db_session, tenant_id: str, creator_id: str):
    """Insert a training with a single VIDEO chapter. Returns (training, chapter)."""
    training = Training(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Video Training",
        description="desc",
        category="Compliance",
        structure_type="flat",
        version=1,
        is_published=True,
        created_by_id=creator_id,
    )
    db_session.add(training)

    chapter = Chapter(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        training_id=training.id,
        title="Video Chapter",
        content_type=ContentType.VIDEO,
        content_data={"url": "/storage/media/sample.mp4"},
        sequence_order=1,
    )
    db_session.add(chapter)
    await db_session.flush()
    return training, chapter


# ---------------------------------------------------------------------------
# T-CO-81: POST /api/v1/progress/video saves resume_position_seconds and milestone_25
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_video_progress_saves_position_and_milestone_25(client, db_session):
    """
    T-CO-81: POST /api/v1/progress/video with position_seconds=142 and
    milestone_25=True must return 200 and persist those values to UserProgress.
    """
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_video_training(db_session, tenant_id, creator_id)
    await db_session.commit()

    training_id = training.id
    chapter_id = chapter.id

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)

    payload = {
        "training_id": training_id,
        "chapter_id": chapter_id,
        "position_seconds": 142,
        "milestone_25": True,
        "milestone_50": False,
        "milestone_75": False,
        "milestone_100": False,
        "video_ended": False,
    }

    try:
        resp = await client.post("/api/v1/progress/video", json=payload)
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code} — {resp.text}"
        data = resp.json()
        assert data["resume_position_seconds"] == 142
    finally:
        _clear_overrides()

    # Query db directly to verify persisted values
    await db_session.rollback()
    result = await db_session.execute(
        select(UserProgress).where(
            UserProgress.user_id == learner_id,
            UserProgress.chapter_id == chapter_id,
            UserProgress.deleted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    assert row is not None, "UserProgress row should have been created"
    assert row.resume_position_seconds == 142, (
        f"resume_position_seconds should be 142, got {row.resume_position_seconds}"
    )
    assert row.milestone_25 is True, "milestone_25 should be True"
    assert row.milestone_50 is False, "milestone_50 should be False"
    assert row.milestone_75 is False, "milestone_75 should be False"
    assert row.milestone_100 is False, "milestone_100 should be False"
    assert row.status == ProgressStatus.IN_PROGRESS, (
        f"status should be IN_PROGRESS, got {row.status}"
    )


# ---------------------------------------------------------------------------
# T-CO-82: milestone_100=True + video_ended=True marks chapter COMPLETED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_video_progress_completion_on_milestone_100_and_ended(client, db_session):
    """
    T-CO-82: POST /api/v1/progress/video with position_seconds=600,
    milestone_100=True, and video_ended=True must set UserProgress.status
    to COMPLETED and set completed_at.
    """
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_video_training(db_session, tenant_id, creator_id)
    await db_session.commit()

    training_id = training.id
    chapter_id = chapter.id

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)

    payload = {
        "training_id": training_id,
        "chapter_id": chapter_id,
        "position_seconds": 600,
        "milestone_25": True,
        "milestone_50": True,
        "milestone_75": True,
        "milestone_100": True,
        "video_ended": True,
    }

    try:
        resp = await client.post("/api/v1/progress/video", json=payload)
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code} — {resp.text}"
        data = resp.json()
        assert data["status"] == "COMPLETED", (
            f"Response status should be COMPLETED, got {data['status']}"
        )
        assert data["resume_position_seconds"] == 600
    finally:
        _clear_overrides()

    # Query db directly to verify COMPLETED status persisted
    await db_session.rollback()
    result = await db_session.execute(
        select(UserProgress).where(
            UserProgress.user_id == learner_id,
            UserProgress.chapter_id == chapter_id,
            UserProgress.deleted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    assert row is not None, "UserProgress row should have been created"
    assert row.status == ProgressStatus.COMPLETED, (
        f"status should be COMPLETED, got {row.status}"
    )
    assert row.completed_at is not None, "completed_at should be set when status is COMPLETED"
    assert row.milestone_100 is True, "milestone_100 should be True"
    assert row.resume_position_seconds == 600, (
        f"resume_position_seconds should be 600, got {row.resume_position_seconds}"
    )
