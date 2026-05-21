"""Cross-tenant isolation tests (C-602).

T-CO-ISO-01: complete_chapter — tenant B user cannot complete tenant A's chapter.
T-CO-ISO-02: submit_quiz    — tenant B user cannot submit a quiz for tenant A's chapter.
TC-ISO-03:   Training list  — training from tenant A never appears in tenant B's list.
TC-ISO-04:   GET /structure — tenant B user cannot read tenant A's training structure.
TC-ISO-05:   Assignment     — tenant B manager cannot assign tenant A's training.
TC-ISO-06:   Category list  — tenant B categories not included in tenant A's listing.
"""
import pytest
import pytest_asyncio
import uuid

from sqlalchemy import select
from tests.conftest import make_user_auth, override_current_user, app
from app.api.deps import get_current_user, get_current_tenant_id
from app.models.training import Training
from app.models.chapter import Chapter, ContentType


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _set_user(user):
    """Override both get_current_user and get_current_tenant_id for a request."""
    tenant_id = user.tenant_id
    app.dependency_overrides[get_current_user] = override_current_user(user)

    async def _tenant_id():
        return tenant_id

    app.dependency_overrides[get_current_tenant_id] = _tenant_id


def _clear_overrides():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_tenant_id, None)


def _training(tenant_id: str, owner_id: str) -> Training:
    return Training(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Tenant A Training",
        category="IT",
        structure_type="flat",
        is_published=True,
        is_active=True,
        created_by_id=owner_id,
        version=1,
    )


def _rich_chapter(training: Training) -> Chapter:
    return Chapter(
        id=str(uuid.uuid4()),
        training_id=training.id,
        tenant_id=training.tenant_id,
        title="Chapter 1",
        sequence_order=1,
        content_type=ContentType.RICH_TEXT,
        content_data={"html": "<p>hello</p>"},
    )


def _quiz_chapter(training: Training) -> Chapter:
    return Chapter(
        id=str(uuid.uuid4()),
        training_id=training.id,
        tenant_id=training.tenant_id,
        title="Quiz Chapter",
        sequence_order=1,
        content_type=ContentType.QUIZ,
        content_data={
            "questions": [
                {
                    "id": "q1",
                    "type": "multiple_choice",
                    "text": "2+2?",
                    "options": [
                        {"id": "a", "text": "3"},
                        {"id": "b", "text": "4"},
                    ],
                    "correct_option_ids": ["b"],
                }
            ],
            "passing_score": 80,
            "max_attempts": 3,
        },
    )


# ---------------------------------------------------------------------------
# T-CO-ISO-01: complete_chapter tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_chapter_tenant_isolation(client, db_session):
    """T-CO-ISO-01: User from tenant B cannot complete a chapter belonging to tenant A."""
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())

    training = _training(tenant_a, owner_id)
    chapter = _rich_chapter(training)
    db_session.add_all([training, chapter])
    await db_session.commit()

    # Attacker belongs to tenant_b
    attacker = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_b,
        roles=["Employee"],
    )
    _set_user(attacker)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/complete"
        )
    finally:
        _clear_overrides()

    # Must be rejected — training not found for tenant_b
    assert resp.status_code in (403, 404), (
        f"Expected 403 or 404, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# T-CO-ISO-02: submit_quiz tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_quiz_tenant_isolation(client, db_session):
    """T-CO-ISO-02: User from tenant B cannot submit a quiz for tenant A's chapter."""
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())

    training = _training(tenant_a, owner_id)
    chapter = _quiz_chapter(training)
    db_session.add_all([training, chapter])
    await db_session.commit()

    # Attacker belongs to tenant_b
    attacker = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_b,
        roles=["Employee"],
    )
    _set_user(attacker)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={
                "answers": [
                    {"question_id": "q1", "selected_option_ids": ["b"]}
                ]
            },
        )
    finally:
        _clear_overrides()

    # The chapter belongs to tenant_a; tenant_b user must be rejected
    assert resp.status_code in (403, 404), (
        f"Expected 403 or 404, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# TC-ISO-03: Training list — training from tenant A never appears in tenant B's list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_training_list_tenant_isolation(client, db_session):
    """GET /trainings must return only trainings belonging to the calling user's tenant."""
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())

    training_a = _training(tenant_a, owner_id)
    db_session.add(training_a)
    await db_session.commit()

    # Tenant B Training Creator — should NOT see training_a
    user_b = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_b,
        roles=["Training Creator"],
    )
    _set_user(user_b)
    try:
        resp = await client.get("/api/v1/trainings")
    finally:
        _clear_overrides()

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    items = data["items"] if isinstance(data, dict) and "items" in data else data
    ids = [t["id"] for t in items]
    assert training_a.id not in ids, (
        f"Tenant A training must not appear in Tenant B's training list"
    )


# ---------------------------------------------------------------------------
# TC-ISO-04: GET /structure — tenant B user cannot read tenant A's training structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_structure_tenant_isolation(client, db_session):
    """Tenant B user requesting structure of a Tenant A training must get 403 or 404."""
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())

    training_a = _training(tenant_a, owner_id)
    db_session.add(training_a)
    await db_session.commit()

    user_b = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_b,
        roles=["Training Creator"],
    )
    _set_user(user_b)
    try:
        resp = await client.get(f"/api/v1/trainings/{training_a.id}/structure")
    finally:
        _clear_overrides()

    assert resp.status_code in (403, 404), (
        f"Expected 403/404 for cross-tenant structure read, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# TC-ISO-05: Assignment — tenant B Manager cannot assign a Tenant A training
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_assign_cross_tenant_rejected(client, db_session):
    """Tenant B Manager bulk-assigning a Tenant A training must be rejected."""
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())

    training_a = _training(tenant_a, owner_id)
    db_session.add(training_a)
    await db_session.commit()

    manager_b = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_b,
        roles=["Business Manager"],
    )
    _set_user(manager_b)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training_a.id}/assignments/bulk",
            json={"user_ids": [str(uuid.uuid4())], "group_ids": []},
        )
    finally:
        _clear_overrides()

    assert resp.status_code in (403, 404), (
        f"Expected 403/404 for cross-tenant assignment, got {resp.status_code}: {resp.text}"
    )
