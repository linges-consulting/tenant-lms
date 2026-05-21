"""
Progress endpoint tests — Phase 3 Task 4.

Tests the progress pushback behaviour when a training is re-published with
changed chapter content (BR-402, BR-602).

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
from app.models.training_history import TrainingHistory
from app.models.chapter import Chapter, ContentType
from app.models.progress import UserProgress, ProgressStatus
from app.models.enrollment import Enrollment
from app.models.audit_log import AuditLog
from app.models.quiz_attempt import QuizAttempt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_creator(tenant_id: str, user_id: str = None):
    return make_user_auth(
        user_id=user_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Training Creator"],
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


async def _create_training_with_chapters(db_session, tenant_id: str, creator_id: str):
    """
    Insert a training with 3 flat chapters directly into the DB.
    Returns (training, [ch1, ch2, ch3]).
    The training is placed in Ready state (is_ready=True, is_published=False) so
    the publish endpoint's state guard passes. A TrainingHistory entry at version=1
    is seeded separately to represent the previously-published snapshot for diff/pushback.
    """
    training = Training(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Test Training",
        description="desc",
        category="Compliance",
        structure_type="flat",
        version=1,
        is_ready=True,       # Ready state — publish endpoint requires this
        is_published=False,  # not yet published — publish will set this and bump version
        created_by_id=creator_id,
    )
    db_session.add(training)

    chapters = []
    for i in range(1, 4):
        ch = Chapter(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            training_id=training.id,
            title=f"Chapter {i}",
            content_type=ContentType.RICH_TEXT,
            content_data={"text": f"original content {i}"},
            sequence_order=i,
        )
        db_session.add(ch)
        chapters.append(ch)

    await db_session.flush()
    return training, chapters


async def _complete_all_chapters(db_session, tenant_id: str, training: Training, chapters, user_id: str):
    """Insert COMPLETED UserProgress rows for all chapters for a given user."""
    for ch in chapters:
        row = UserProgress(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            training_id=training.id,
            chapter_id=ch.id,
            status=ProgressStatus.COMPLETED,
            training_version_id=training.version,
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(row)
    await db_session.flush()


# ---------------------------------------------------------------------------
# T-CO-402: Cascade reset — first changed chapter and all following are reset
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pushback_resets_to_changed_chapter_and_forward(client, db_session):
    """
    T-CO-402: Re-publishing with a changed Ch2 (sequence_order=2) must:
      - Leave Ch1 (sequence_order=1) progress COMPLETED (unchanged chapter before change point).
      - Soft-delete Ch2 and Ch3 progress (changed chapter and all subsequent chapters).
      - Write at least one audit_log entry with action='progress_reset'.
    """
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    creator = _make_creator(tenant_id, creator_id)

    # ------------------------------------------------------------------
    # 1. Seed DB: training + 3 chapters + completed progress for learner
    # ------------------------------------------------------------------
    training, (ch1, ch2, ch3) = await _create_training_with_chapters(db_session, tenant_id, creator_id)
    await _complete_all_chapters(db_session, tenant_id, training, [ch1, ch2, ch3], learner_id)

    # Save IDs before any commit so they survive session expiry after rollback.
    training_id = training.id
    ch1_id = ch1.id
    ch2_id = ch2.id
    ch3_id = ch3.id

    # Seed a TrainingHistory entry representing the OLD (version 1) published snapshot.
    # The publish endpoint diffs the current snapshot against this entry to find changed chapters.
    # Without this entry, `old_history` would be None and no pushback would occur.
    old_snapshot = {
        "id": training_id,
        "title": "Test Training",
        "modules": [],
        # Use 'orphan_chapters' — the key produced by TrainingStructure.model_dump().
        # The flatten_chapters helper also accepts legacy 'chapters' key for old snapshots.
        "orphan_chapters": [
            {"id": ch1_id, "title": "Chapter 1", "sequence_order": 1, "content_data": {"text": "original content 1"}},
            {"id": ch2_id, "title": "Chapter 2", "sequence_order": 2, "content_data": {"text": "original content 2"}},
            {"id": ch3_id, "title": "Chapter 3", "sequence_order": 3, "content_data": {"text": "original content 3"}},
        ],
    }
    old_history = TrainingHistory(
        tenant_id=tenant_id,
        training_id=training_id,
        version=1,  # matches training.version
        snapshot=old_snapshot,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(old_history)
    await db_session.commit()

    # ------------------------------------------------------------------
    # 2. Modify Ch2 content in DB (simulating a content edit before re-publish)
    # ------------------------------------------------------------------
    ch2.content_data = {"text": "CHANGED content for chapter 2"}
    await db_session.commit()

    # ------------------------------------------------------------------
    # 3. Call publish endpoint — this should trigger pushback.
    #    Publish requires Business Manager role (BR-301a).
    # ------------------------------------------------------------------
    manager = _make_manager(tenant_id)
    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training_id}/publish")
        assert resp.status_code == 200, f"Publish failed: {resp.status_code} — {resp.text}"
    finally:
        _clear_overrides()

    # Expire the session so subsequent queries see what the endpoint committed.
    await db_session.rollback()

    # ------------------------------------------------------------------
    # 4. Assert Ch1 progress survives (unchanged chapter before change point)
    # ------------------------------------------------------------------
    ch1_progress = await db_session.execute(
        select(UserProgress).where(
            UserProgress.user_id == learner_id,
            UserProgress.chapter_id == ch1_id,
        )
    )
    ch1_row = ch1_progress.scalar_one_or_none()
    assert ch1_row is not None, "Ch1 progress row should still exist"
    assert ch1_row.deleted_at is None, "Ch1 progress should NOT be soft-deleted (unchanged, before change point)"
    assert ch1_row.status == ProgressStatus.COMPLETED, "Ch1 should remain COMPLETED"

    # ------------------------------------------------------------------
    # 5. Assert Ch2 progress is soft-deleted (changed chapter)
    # ------------------------------------------------------------------
    ch2_progress = await db_session.execute(
        select(UserProgress).where(
            UserProgress.user_id == learner_id,
            UserProgress.chapter_id == ch2_id,
        )
    )
    ch2_row = ch2_progress.scalar_one_or_none()
    # Either soft-deleted (deleted_at set) or hard-deleted (row gone) — we require soft delete
    assert ch2_row is not None, "Ch2 progress row should NOT be hard-deleted — use soft delete"
    assert ch2_row.deleted_at is not None, "Ch2 progress should be soft-deleted (deleted_at must be set)"

    # ------------------------------------------------------------------
    # 6. Assert Ch3 progress is soft-deleted (unchanged but AFTER change point)
    # ------------------------------------------------------------------
    ch3_progress = await db_session.execute(
        select(UserProgress).where(
            UserProgress.user_id == learner_id,
            UserProgress.chapter_id == ch3_id,
        )
    )
    ch3_row = ch3_progress.scalar_one_or_none()
    assert ch3_row is not None, "Ch3 progress row should NOT be hard-deleted — use soft delete"
    assert ch3_row.deleted_at is not None, "Ch3 progress must be soft-deleted — cascade forward required"

    # ------------------------------------------------------------------
    # 7. Assert at least one audit_log entry for progress_reset exists
    # ------------------------------------------------------------------
    audit_rows = await db_session.execute(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.action == "progress_reset",
            AuditLog.entity_id == training_id,
        )
    )
    audit_list = audit_rows.scalars().all()
    assert len(audit_list) >= 1, (
        "At least one audit_log row with action='progress_reset' must be written when progress is reset"
    )


# ---------------------------------------------------------------------------
# T-CO-403: Unchanged training re-publish does NOT reset progress
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pushback_skipped_when_no_chapters_changed(client, db_session):
    """
    T-CO-403: Re-publishing without any content changes must leave all progress intact.
    """
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    creator = _make_creator(tenant_id, creator_id)

    training, (ch1, ch2, ch3) = await _create_training_with_chapters(db_session, tenant_id, creator_id)
    await _complete_all_chapters(db_session, tenant_id, training, [ch1, ch2, ch3], learner_id)
    await db_session.commit()

    # Save IDs before session expiry.
    training_id = training.id
    ch1_id, ch2_id, ch3_id = ch1.id, ch2.id, ch3.id

    # First publish creates a history snapshot; we need it to exist before re-publish
    # so that the diff comparison has something to compare against.
    # We skip inserting a history row here — the endpoint handles first-publish case.
    # Publish requires Business Manager role (BR-301a).
    manager = _make_manager(tenant_id)
    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training_id}/publish")
        assert resp.status_code == 200, f"Publish failed: {resp.status_code} — {resp.text}"
    finally:
        _clear_overrides()

    await db_session.rollback()

    # All three chapters' progress should remain untouched
    for ch_id, label in [(ch1_id, "Ch1"), (ch2_id, "Ch2"), (ch3_id, "Ch3")]:
        row = await db_session.execute(
            select(UserProgress).where(
                UserProgress.user_id == learner_id,
                UserProgress.chapter_id == ch_id,
            )
        )
        row = row.scalar_one_or_none()
        assert row is not None, f"{label} progress must still exist"
        assert row.deleted_at is None, f"{label} progress must not be soft-deleted when nothing changed"


# ---------------------------------------------------------------------------
# Helpers for quiz tests
# ---------------------------------------------------------------------------

def _make_learner(tenant_id: str, user_id: str = None):
    return make_user_auth(
        user_id=user_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Employee"],
    )


def _make_manager(tenant_id: str, user_id: str = None):
    return make_user_auth(
        user_id=user_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Business Manager"],
    )


async def _create_quiz_training(db_session, tenant_id: str, creator_id: str, max_attempts: int = None):
    """Insert a training with a single QUIZ chapter. Returns (training, chapter)."""
    training = Training(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Quiz Training",
        description="desc",
        category="Compliance",
        structure_type="flat",
        version=1,
        is_published=True,
        created_by_id=creator_id,
    )
    db_session.add(training)

    content_data = {
        "passing_score": 80,
        "questions": [
            {
                "id": "q1",
                "type": "multiple_choice",
                "text": "What is 2+2?",
                "options": [
                    {"id": "a", "text": "3"},
                    {"id": "b", "text": "4"},
                ],
                "correct_option_ids": ["b"],
            }
        ],
    }
    if max_attempts is not None:
        content_data["max_attempts"] = max_attempts

    chapter = Chapter(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        training_id=training.id,
        title="Quiz Chapter",
        content_type=ContentType.QUIZ,
        content_data=content_data,
        sequence_order=1,
    )
    db_session.add(chapter)
    await db_session.flush()
    return training, chapter


# ---------------------------------------------------------------------------
# T-CO-406: Default max_attempts is 10 (not 3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quiz_default_max_attempts_is_10(client, db_session):
    """
    T-CO-406 (BR-406): When max_attempts is not set in content_data,
    the default must be 10. Submitting 10 wrong answers must NOT lock
    the learner; the 11th wrong submission must result in a 403.
    """
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    # No max_attempts in content_data — relies on default
    training, chapter = await _create_quiz_training(db_session, tenant_id, creator_id, max_attempts=None)
    await db_session.commit()

    training_id = training.id
    chapter_id = chapter.id

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)

    # Wrong answer payload (selects "a" instead of correct "b")
    wrong_payload = {"answers": [{"question_id": "q1", "selected_option_ids": ["a"]}]}

    try:
        # Submit 10 wrong answers — none should lock the learner
        for attempt_num in range(1, 11):
            resp = await client.post(
                f"/api/v1/trainings/{training_id}/chapters/{chapter_id}/submit-quiz",
                json=wrong_payload,
            )
            assert resp.status_code == 200, (
                f"Attempt {attempt_num}: expected 200 but got {resp.status_code} — {resp.text}"
            )
            data = resp.json()
            assert data["attempt_number"] == attempt_num, (
                f"Attempt {attempt_num}: wrong attempt_number in response"
            )
            assert data["max_attempts"] == 10, (
                f"Attempt {attempt_num}: max_attempts should default to 10, got {data['max_attempts']}"
            )

        # 11th wrong attempt must be rejected (locked out)
        resp = await client.post(
            f"/api/v1/trainings/{training_id}/chapters/{chapter_id}/submit-quiz",
            json=wrong_payload,
        )
        assert resp.status_code == 403, (
            f"11th attempt should return 403 lockout, got {resp.status_code} — {resp.text}"
        )
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CO-407: Manager can reset a learner's quiz lockout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manager_can_reset_quiz_lockout(client, db_session):
    """
    T-CO-407 (BR-407): A Business Manager calling
    POST /api/v1/trainings/{id}/chapters/{chapter_id}/quiz/reset/{learner_id}
    must soft-delete all active quiz attempts for that learner+chapter and
    return 200. After the reset the learner can submit again.
    """
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    manager_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(db_session, tenant_id, creator_id, max_attempts=3)
    await db_session.commit()

    training_id = training.id
    chapter_id = chapter.id

    # Seed 3 failed quiz attempts for the learner (simulating lockout)
    for i in range(1, 4):
        attempt = QuizAttempt(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=learner_id,
            chapter_id=chapter_id,
            attempt_number=i,
            score=0.0,
            passed=False,
            answers={"q1": ["a"]},
        )
        db_session.add(attempt)
    await db_session.commit()

    # Confirm the learner is locked out before reset
    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    wrong_payload = {"answers": [{"question_id": "q1", "selected_option_ids": ["a"]}]}
    resp_before = await client.post(
        f"/api/v1/trainings/{training_id}/chapters/{chapter_id}/submit-quiz",
        json=wrong_payload,
    )
    assert resp_before.status_code == 403, (
        f"Learner should be locked before reset; got {resp_before.status_code}"
    )
    _clear_overrides()

    # Manager calls the reset endpoint
    manager = _make_manager(tenant_id, manager_id)
    _set_user(manager)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training_id}/chapters/{chapter_id}/quiz/reset/{learner_id}"
        )
        assert resp.status_code == 200, (
            f"Manager reset should return 200, got {resp.status_code} — {resp.text}"
        )
        assert resp.json().get("message") == "Quiz lockout reset."
    finally:
        _clear_overrides()

    # Verify all attempts for learner+chapter are now soft-deleted
    await db_session.rollback()
    active_attempts = await db_session.execute(
        select(QuizAttempt).where(
            QuizAttempt.user_id == learner_id,
            QuizAttempt.chapter_id == chapter_id,
            QuizAttempt.deleted_at.is_(None),
        )
    )
    active_list = active_attempts.scalars().all()
    assert len(active_list) == 0, (
        f"All attempts should be soft-deleted after reset, but {len(active_list)} remain active"
    )

    # Verify learner can now submit again (no longer locked)
    _set_user(learner)
    try:
        resp_after = await client.post(
            f"/api/v1/trainings/{training_id}/chapters/{chapter_id}/submit-quiz",
            json=wrong_payload,
        )
        assert resp_after.status_code == 200, (
            f"Learner should be able to submit after reset, got {resp_after.status_code} — {resp_after.text}"
        )
    finally:
        _clear_overrides()
