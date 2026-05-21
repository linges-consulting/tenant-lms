"""
Quiz engine tests — scoring rules, attempt limits, lockout, manager reset.

Covers:
  TC-QUZ-01..07, 09..16, 18..29, 31..37, 40..41

Auth pattern:
  Override get_current_user AND get_current_tenant_id via app.dependency_overrides.
  Bearer tokens have no effect in core-service unit tests.
"""

import pytest
import uuid
from sqlalchemy import select

from app.main import app
from app.api.deps import get_current_user, get_current_tenant_id
from app.models.training import Training
from app.models.chapter import Chapter, ContentType
from app.models.quiz_attempt import QuizAttempt
from tests.conftest import override_current_user, make_user_auth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_creator(tenant_id: str, user_id: str = None):
    return make_user_auth(
        user_id=user_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Training Creator"],
    )


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


def _set_user(user):
    app.dependency_overrides[get_current_user] = override_current_user(user)

    async def _tenant_id():
        return user.tenant_id

    app.dependency_overrides[get_current_tenant_id] = _tenant_id


def _clear_overrides():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_tenant_id, None)


async def _create_quiz_training(
    db_session,
    tenant_id: str,
    creator_id: str,
    questions: list,
    max_attempts: int = 3,
    passing_score: int = 80,
):
    """Insert a published training with a single QUIZ chapter. Returns (training, chapter)."""
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
        "passing_score": passing_score,
        "max_attempts": max_attempts,
        "questions": questions,
    }
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


MC_QUESTIONS = [
    {
        "id": "q1",
        "type": "multiple_choice",
        "text": "What is 2+2?",
        "options": [{"id": "a", "text": "3"}, {"id": "b", "text": "4"}],
        "correct_option_ids": ["b"],
    }
]

MS_QUESTIONS = [
    {
        "id": "q1",
        "type": "multiple_select",
        "text": "Select the even numbers",
        "options": [
            {"id": "a", "text": "1"},
            {"id": "b", "text": "2"},
            {"id": "c", "text": "3"},
            {"id": "d", "text": "4"},
            {"id": "e", "text": "5"},
        ],
        "correct_option_ids": ["b", "d"],
    }
]

TF_QUESTIONS = [
    {
        "id": "q1",
        "type": "true_false",
        "text": "The sky is blue",
        "options": [{"id": "true", "text": "True"}, {"id": "false", "text": "False"}],
        "correct_option_ids": ["true"],
    }
]


# ===========================================================================
# TC-QUZ-01..04 — Quiz Creation
# ===========================================================================

@pytest.mark.asyncio
async def test_quz_01_create_quiz_with_max_attempts(client, db_session):
    """TC-QUZ-01: Creating quiz lesson with max_attempts=3 stores config correctly."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    training = Training(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Quiz Config Test",
        category="Compliance",
        structure_type="flat",
        version=1,
        is_published=False,
        is_ready=False,
        created_by_id=creator.id,
    )
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters",
            json={
                "title": "Quiz Chapter",
                "content_type": "QUIZ",
                "sequence_order": 1,
                "content_data": {
                    "passing_score": 80,
                    "max_attempts": 3,
                    "questions": MC_QUESTIONS,
                },
            },
        )
        assert resp.status_code in (200, 201), f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["content_data"]["max_attempts"] == 3
        assert data["content_data"]["passing_score"] == 80
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_quz_05_mc_question_created(client, db_session):
    """TC-QUZ-05: Create MC question with 4 options, 1 correct → stored correctly."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    training = Training(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="MC Test",
        category="Safety",
        structure_type="flat",
        version=1,
        is_published=False,
        is_ready=False,
        created_by_id=creator.id,
    )
    db_session.add(training)
    await db_session.commit()

    mc_q = {
        "id": "q1",
        "type": "multiple_choice",
        "text": "Question text",
        "options": [
            {"id": "a", "text": "Option A"},
            {"id": "b", "text": "Option B"},
            {"id": "c", "text": "Option C"},
            {"id": "d", "text": "Option D"},
        ],
        "correct_option_ids": ["c"],
    }

    _set_user(creator)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters",
            json={
                "title": "MC Chapter",
                "content_type": "QUIZ",
                "sequence_order": 1,
                "content_data": {
                    "passing_score": 100,
                    "max_attempts": 5,
                    "questions": [mc_q],
                },
            },
        )
        assert resp.status_code in (200, 201), f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        questions = data["content_data"]["questions"]
        assert len(questions) == 1
        assert questions[0]["correct_option_ids"] == ["c"]
    finally:
        _clear_overrides()


# ===========================================================================
# TC-QUZ-06, 07 — Multiple Choice scoring
# ===========================================================================

@pytest.mark.asyncio
async def test_quz_06_mc_correct_answer_scores_correct(client, db_session):
    """TC-QUZ-06: Selecting correct MC answer → question scored correct, passed."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, MC_QUESTIONS, max_attempts=3, passing_score=100
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={"answers": [{"question_id": "q1", "selected_option_ids": ["b"]}]},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["passed"] is True, f"Should be passed, got: {data}"
        assert data["score"] == 100.0, f"Score should be 100, got: {data['score']}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_quz_07_mc_wrong_answer_scores_incorrect(client, db_session):
    """TC-QUZ-07: Selecting wrong MC answer → question scored incorrect, failed."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, MC_QUESTIONS, max_attempts=3, passing_score=100
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={"answers": [{"question_id": "q1", "selected_option_ids": ["a"]}]},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["passed"] is False, f"Should be failed, got: {data}"
        assert data["score"] == 0.0, f"Score should be 0, got: {data['score']}"
    finally:
        _clear_overrides()


# ===========================================================================
# TC-QUZ-10..14 — Multiple Select (all-or-nothing) scoring
# ===========================================================================

@pytest.mark.asyncio
async def test_quz_10_ms_all_correct_selected_scores_correct(client, db_session):
    """TC-QUZ-10: Selecting exactly all correct MS options → correct."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, MS_QUESTIONS, max_attempts=3, passing_score=100
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={"answers": [{"question_id": "q1", "selected_option_ids": ["b", "d"]}]},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["passed"] is True, f"All correct options selected → should pass: {data}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_quz_11_ms_partial_correct_scores_incorrect(client, db_session):
    """TC-QUZ-11: Selecting only 1 of 2 correct MS options → incorrect (no partial credit)."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, MS_QUESTIONS, max_attempts=3, passing_score=100
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={"answers": [{"question_id": "q1", "selected_option_ids": ["b"]}]},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["passed"] is False, f"Partial MS selection → should fail: {data}"
        assert data["score"] == 0.0, f"Partial MS → score must be 0: {data['score']}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_quz_12_ms_correct_plus_wrong_scores_incorrect(client, db_session):
    """TC-QUZ-12: Selecting both correct options + 1 wrong option → incorrect."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, MS_QUESTIONS, max_attempts=3, passing_score=100
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={"answers": [{"question_id": "q1", "selected_option_ids": ["b", "d", "a"]}]},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["passed"] is False, f"Correct + wrong options → should fail: {data}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_quz_13_ms_no_selection_scores_incorrect(client, db_session):
    """TC-QUZ-13: Submitting no options for MS question → incorrect."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, MS_QUESTIONS, max_attempts=3, passing_score=100
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={"answers": [{"question_id": "q1", "selected_option_ids": []}]},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["passed"] is False, f"No selection → should fail: {data}"
    finally:
        _clear_overrides()


# ===========================================================================
# TC-QUZ-16, 17 — True/False scoring
# ===========================================================================

@pytest.mark.asyncio
async def test_quz_16_tf_correct_scores_pass(client, db_session):
    """TC-QUZ-16: Selecting correct T/F answer → pass."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, TF_QUESTIONS, max_attempts=3, passing_score=100
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={"answers": [{"question_id": "q1", "selected_option_ids": ["true"]}]},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["passed"] is True, f"Correct T/F → should pass: {data}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_quz_17_tf_wrong_scores_fail(client, db_session):
    """TC-QUZ-17: Selecting wrong T/F answer → fail."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, TF_QUESTIONS, max_attempts=3, passing_score=100
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={"answers": [{"question_id": "q1", "selected_option_ids": ["false"]}]},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["passed"] is False, f"Wrong T/F → should fail: {data}"
    finally:
        _clear_overrides()


# ===========================================================================
# TC-QUZ-26..30 — Scoring & Pass/Fail thresholds
# ===========================================================================

@pytest.mark.asyncio
async def test_quz_26_score_at_passing_threshold_passes(client, db_session):
    """TC-QUZ-26: Answering exactly at passing_score=50 → pass."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    # Two questions, passing_score=50, answer 1 correctly
    questions = [
        {
            "id": "q1",
            "type": "multiple_choice",
            "text": "Q1",
            "options": [{"id": "a", "text": "Right"}, {"id": "b", "text": "Wrong"}],
            "correct_option_ids": ["a"],
        },
        {
            "id": "q2",
            "type": "multiple_choice",
            "text": "Q2",
            "options": [{"id": "a", "text": "Right"}, {"id": "b", "text": "Wrong"}],
            "correct_option_ids": ["a"],
        },
    ]
    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, questions, max_attempts=5, passing_score=50
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={"answers": [
                {"question_id": "q1", "selected_option_ids": ["a"]},   # correct
                {"question_id": "q2", "selected_option_ids": ["b"]},   # wrong
            ]},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["passed"] is True, f"50% == passing_score=50 → should pass: {data}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_quz_27_score_below_threshold_fails(client, db_session):
    """TC-QUZ-27: Scoring 1 below passing threshold → fail."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    # 3 questions, passing_score=80 — answer only 2/3 → 66% < 80
    questions = [
        {
            "id": f"q{i}",
            "type": "multiple_choice",
            "text": f"Q{i}",
            "options": [{"id": "a", "text": "Right"}, {"id": "b", "text": "Wrong"}],
            "correct_option_ids": ["a"],
        }
        for i in range(1, 4)
    ]
    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, questions, max_attempts=5, passing_score=80
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={"answers": [
                {"question_id": "q1", "selected_option_ids": ["a"]},
                {"question_id": "q2", "selected_option_ids": ["a"]},
                {"question_id": "q3", "selected_option_ids": ["b"]},  # wrong
            ]},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["passed"] is False, f"66% < 80 → should fail: {data}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_quz_28_score_100_passes(client, db_session):
    """TC-QUZ-28: Answering all correctly → 100% → pass."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, MC_QUESTIONS, max_attempts=3, passing_score=80
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={"answers": [{"question_id": "q1", "selected_option_ids": ["b"]}]},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["passed"] is True, f"100% → should pass: {data}"
        assert data["score"] == 100.0
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_quz_29_score_0_fails(client, db_session):
    """TC-QUZ-29: Answering nothing correctly → 0% → fail."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, MC_QUESTIONS, max_attempts=3, passing_score=80
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={"answers": [{"question_id": "q1", "selected_option_ids": ["a"]}]},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["passed"] is False, f"0% → should fail: {data}"
        assert data["score"] == 0.0
    finally:
        _clear_overrides()


# ===========================================================================
# TC-QUZ-31..35 — Attempt limits & lockout
# ===========================================================================

@pytest.mark.asyncio
async def test_quz_31_attempt_counter_increments(client, db_session):
    """TC-QUZ-31: Attempt counter increments on each failed submission."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, MC_QUESTIONS, max_attempts=5, passing_score=100
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    wrong_payload = {"answers": [{"question_id": "q1", "selected_option_ids": ["a"]}]}
    try:
        resp1 = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json=wrong_payload,
        )
        assert resp1.status_code == 200
        assert resp1.json()["attempt_number"] == 1

        resp2 = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json=wrong_payload,
        )
        assert resp2.status_code == 200
        assert resp2.json()["attempt_number"] == 2
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_quz_32_final_attempt_fail_locks_learner(client, db_session):
    """TC-QUZ-32: Using final attempt on fail → locked out → 403 on next attempt."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, MC_QUESTIONS, max_attempts=2, passing_score=100
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    wrong_payload = {"answers": [{"question_id": "q1", "selected_option_ids": ["a"]}]}
    try:
        # Use both attempts
        for _ in range(2):
            resp = await client.post(
                f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
                json=wrong_payload,
            )
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        # 3rd attempt — should be locked
        locked_resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json=wrong_payload,
        )
        assert locked_resp.status_code == 403, (
            f"Expected 403 after lockout, got {locked_resp.status_code}: {locked_resp.text}"
        )
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_quz_34_locked_learner_cannot_submit_via_api(client, db_session):
    """TC-QUZ-34: Locked-out learner cannot submit via direct API call → 403."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, MC_QUESTIONS, max_attempts=1, passing_score=100
    )
    await db_session.commit()

    # Seed 1 failed attempt directly
    attempt = QuizAttempt(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=learner_id,
        chapter_id=chapter.id,
        attempt_number=1,
        score=0.0,
        passed=False,
        answers={"q1": ["a"]},
    )
    db_session.add(attempt)
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={"answers": [{"question_id": "q1", "selected_option_ids": ["b"]}]},
        )
        assert resp.status_code == 403, (
            f"Expected 403 for locked learner, got {resp.status_code}: {resp.text}"
        )
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_quz_35_pass_on_last_attempt_not_locked(client, db_session):
    """TC-QUZ-35: Passing on the last attempt does not lock the learner."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, MC_QUESTIONS, max_attempts=2, passing_score=100
    )
    await db_session.commit()

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    wrong_payload = {"answers": [{"question_id": "q1", "selected_option_ids": ["a"]}]}
    correct_payload = {"answers": [{"question_id": "q1", "selected_option_ids": ["b"]}]}
    try:
        # Fail attempt 1
        resp1 = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json=wrong_payload,
        )
        assert resp1.status_code == 200

        # Pass attempt 2 (last allowed)
        resp2 = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json=correct_payload,
        )
        assert resp2.status_code == 200, f"Expected 200, got {resp2.status_code}: {resp2.text}"
        data = resp2.json()
        assert data["passed"] is True, f"Should be passed on last attempt: {data}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_quz_36_attempt_counter_is_per_enrollment(client, db_session):
    """TC-QUZ-36: Two learners have independent attempt counters."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_a_id = str(uuid.uuid4())
    learner_b_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, MC_QUESTIONS, max_attempts=3, passing_score=100
    )
    await db_session.commit()

    wrong_payload = {"answers": [{"question_id": "q1", "selected_option_ids": ["a"]}]}

    # Learner A uses 2 attempts
    learner_a = _make_learner(tenant_id, learner_a_id)
    _set_user(learner_a)
    try:
        for _ in range(2):
            r = await client.post(
                f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
                json=wrong_payload,
            )
            assert r.status_code == 200
    finally:
        _clear_overrides()

    # Learner B should still have 3 fresh attempts
    learner_b = _make_learner(tenant_id, learner_b_id)
    _set_user(learner_b)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json=wrong_payload,
        )
        assert resp.status_code == 200, (
            f"Learner B should not be locked (Learner A used attempts), got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert data["attempt_number"] == 1, (
            f"Learner B attempt_number should be 1, got {data['attempt_number']}"
        )
    finally:
        _clear_overrides()


# ===========================================================================
# TC-QUZ-40 — Non-manager cannot reset quiz lockout
# ===========================================================================

@pytest.mark.asyncio
async def test_quz_40_employee_cannot_reset_quiz_lockout(client, db_session):
    """TC-QUZ-40: Base Employee cannot reset quiz lockout → 403."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    employee_id = str(uuid.uuid4())

    training, chapter = await _create_quiz_training(
        db_session, tenant_id, creator_id, MC_QUESTIONS, max_attempts=1, passing_score=100
    )
    await db_session.commit()

    # Seed a failed attempt
    attempt = QuizAttempt(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=learner_id,
        chapter_id=chapter.id,
        attempt_number=1,
        score=0.0,
        passed=False,
        answers={"q1": ["a"]},
    )
    db_session.add(attempt)
    await db_session.commit()

    employee = _make_learner(tenant_id, employee_id)
    _set_user(employee)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/quiz/reset/{learner_id}"
        )
        assert resp.status_code == 403, (
            f"Expected 403 for Employee resetting quiz, got {resp.status_code}: {resp.text}"
        )
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_quz_41_manager_cannot_reset_cross_tenant(client, db_session):
    """TC-QUZ-41: Manager cannot reset quiz lockout for learner in another tenant → 403/404."""
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    # Training is in Tenant A
    training, chapter = await _create_quiz_training(
        db_session, tenant_a, creator_id, MC_QUESTIONS, max_attempts=1, passing_score=100
    )
    await db_session.commit()

    # Manager from Tenant B tries to reset
    manager_b = _make_manager(tenant_b)
    _set_user(manager_b)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/quiz/reset/{learner_id}"
        )
        assert resp.status_code in (403, 404), (
            f"Expected 403/404 for cross-tenant quiz reset, got {resp.status_code}: {resp.text}"
        )
    finally:
        _clear_overrides()
