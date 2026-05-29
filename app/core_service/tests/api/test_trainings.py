"""
Training endpoint tests — Phase 3 Task 2.

Auth pattern:
  The core service validates JWTs via an outbound HTTP call to auth-service.
  Tests must override get_current_user AND get_current_tenant_id directly
  via app.dependency_overrides — Bearer tokens have no effect here.
"""

import pytest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.main import app
from app.api.deps import get_current_user, get_current_tenant_id
from app.models.training import Training
from app.models.chapter import Chapter, ContentType
from app.models.enrollment import Enrollment
from app.models.assignment import TrainingAssignment
from app.models.collaborator import TrainingCollaborator
from app.models.progress import UserProgress, ProgressStatus
from tests.conftest import override_current_user, make_user_auth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_creator(tenant_id: str):
    """Return a UserAuth object for a Training Creator in the given tenant."""
    return make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Training Creator"],
    )


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
# T-CO-01: Creating a training without category returns 422
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_training_requires_category(client, db_session):
    """Omitting 'category' must produce a 422 Unprocessable Entity."""
    tenant_id = str(uuid.uuid4())
    user = _make_creator(tenant_id)
    _set_user(user)
    try:
        resp = await client.post(
            "/api/v1/trainings",
            json={
                "title": "No Category Training",
                "description": "desc",
                "structure_type": "flat",
                "requires_certificate": False,
            },
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CT-01: Creating a training with a valid category succeeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_training_with_category(client, db_session):
    """Training with all required fields should be created successfully (201)."""
    tenant_id = str(uuid.uuid4())
    user = _make_creator(tenant_id)
    _set_user(user)
    try:
        resp = await client.post(
            "/api/v1/trainings",
            json={
                "title": "Safety Training",
                "description": "A safety course.",
                "category": "Safety",
                "structure_type": "flat",
                "requires_certificate": False,
            },
        )
        assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["category"] == "Safety"
        assert data["structure_type"] == "flat"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CT-02: Tags are stored and returned
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_training_with_tags(client, db_session):
    """Tags provided at creation must appear in the response."""
    tenant_id = str(uuid.uuid4())
    user = _make_creator(tenant_id)
    _set_user(user)
    try:
        resp = await client.post(
            "/api/v1/trainings",
            json={
                "title": "Tagged Training",
                "description": "desc",
                "category": "HR",
                "structure_type": "flat",
                "tags": ["onboarding", "compliance"],
                "requires_certificate": False,
            },
        )
        assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "onboarding" in data["tags"]
        assert "compliance" in data["tags"]
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CO-38: structure_type column is kept but no longer enforced as immutable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_structure_type_can_be_updated(client, db_session):
    """structure_type is no longer immutable — updating it via PUT must succeed."""
    tenant_id = str(uuid.uuid4())
    user = _make_creator(tenant_id)
    _set_user(user)
    try:
        # Create the training
        create_resp = await client.post(
            "/api/v1/trainings",
            json={
                "title": "Flat Training",
                "description": "desc",
                "category": "IT",
                "structure_type": "flat",
                "requires_certificate": False,
            },
        )
        assert create_resp.status_code in (200, 201), (
            f"Create failed: {create_resp.status_code}: {create_resp.text}"
        )
        training_id = create_resp.json()["id"]

        # structure_type can now be changed — expect success
        put_resp = await client.put(
            f"/api/v1/trainings/{training_id}",
            json={
                "title": "Flat Training",
                "category": "IT",
                "structure_type": "modular",
                "requires_certificate": False,
            },
        )
        assert put_resp.status_code in (200, 201), (
            f"Expected 200, got {put_resp.status_code}: {put_resp.text}"
        )
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CO-ASSIGN-01 (BR-301a): Training Creator cannot bulk-assign trainings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_training_creator_cannot_bulk_assign(client, db_session):
    """
    BR-301a: Training Creators build content; only Business Managers and SysAdmins
    can assign trainings. A Training Creator hitting the bulk-assign endpoint must
    receive 403 Forbidden.
    """
    tenant_id = str(uuid.uuid4())

    # Create training as a creator first (so the training exists)
    creator = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Training Creator"],
    )
    _set_user(creator)
    try:
        create_resp = await client.post(
            "/api/v1/trainings",
            json={
                "title": "Creator's Training",
                "description": "desc",
                "category": "Safety",
                "structure_type": "flat",
                "requires_certificate": False,
            },
        )
        assert create_resp.status_code in (200, 201), (
            f"Training creation failed: {create_resp.status_code}: {create_resp.text}"
        )
        training_id = create_resp.json()["id"]
    finally:
        _clear_overrides()

    # Now attempt to bulk-assign as Training Creator — must be 403
    _set_user(creator)
    try:
        assign_resp = await client.post(
            f"/api/v1/trainings/{training_id}/assignments/bulk",
            json={
                "user_ids": [str(uuid.uuid4())],
                "group_ids": [],
            },
        )
        assert assign_resp.status_code == 403, (
            f"Expected 403 for Training Creator bulk-assign, got {assign_resp.status_code}: {assign_resp.text}"
        )
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CO-ASSIGN-02 (BR-301a): Business Manager can bulk-assign trainings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_business_manager_can_bulk_assign(client, db_session):
    """
    BR-301a: Business Managers are authorized to assign trainings.
    Training must be published before assignment is allowed.
    """
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())

    # Insert a published training directly so assignment is allowed
    training = Training(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Manager Assignable Training",
        description="desc",
        category="HR",
        structure_type="flat",
        is_published=True,
        is_active=True,
        is_archived=False,
        is_ready=True,
        requires_certificate=False,
        created_by_id=creator_id,
    )
    db_session.add(training)
    await db_session.commit()
    training_id = training.id

    # Business Manager assigns
    manager = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Business Manager"],
    )
    _set_user(manager)
    try:
        assign_resp = await client.post(
            f"/api/v1/trainings/{training_id}/assignments/bulk",
            json={
                "user_ids": [str(uuid.uuid4())],
                "group_ids": [],
            },
        )
        assert assign_resp.status_code == 200, (
            f"Expected 200 for Business Manager bulk-assign, got {assign_resp.status_code}: {assign_resp.text}"
        )
    finally:
        _clear_overrides()


async def test_sysadmin_can_bulk_assign(client, db_session):
    """T-CO-ASSIGN-03: SysAdmin can bulk-assign trainings (BR-301a).
    Training must be published before assignment is allowed.
    """
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())

    # Insert a published training directly so assignment is allowed
    training = Training(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="SysAdmin Training",
        description="desc",
        category="IT",
        structure_type="flat",
        is_published=True,
        is_active=True,
        is_archived=False,
        is_ready=True,
        requires_certificate=False,
        created_by_id=creator_id,
    )
    db_session.add(training)
    await db_session.commit()
    training_id = training.id

    # SysAdmin assigns
    _set_user(make_user_auth(str(uuid.uuid4()), tenant_id, ["SysAdmin"]))
    try:
        assign_resp = await client.post(
            f"/api/v1/trainings/{training_id}/assignments/bulk",
            json={"user_ids": [str(uuid.uuid4())], "group_ids": []},
        )
        assert assign_resp.status_code == 200, (
            f"Expected 200 for SysAdmin bulk-assign, got {assign_resp.status_code}: {assign_resp.text}"
        )
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CT-03: Filter trainings by category
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_trainings_filter_by_category(client, db_session):
    """
    T-CT-03: GET /api/v1/trainings/manager?category=Safety must return only
    trainings whose category matches 'Safety', excluding those with a different
    category (e.g. 'HR').
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    # Mock enrich helper so no outbound HTTP is made
    with patch("app.api.v1.endpoints.trainings.deps.get_users_batch", new_callable=AsyncMock) as mock_batch:
        mock_batch.return_value = {}

        # Seed two trainings with different categories directly in db_session
        safety_training = Training(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            title="Safety Basics",
            description="Safety course",
            category="Safety",
            structure_type="flat",
            is_published=False,
            is_active=True,
            is_archived=False,
            requires_certificate=False,
            created_by_id=creator.id,
        )
        hr_training = Training(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            title="HR Onboarding",
            description="HR course",
            category="HR",
            structure_type="flat",
            is_published=False,
            is_active=True,
            is_archived=False,
            requires_certificate=False,
            created_by_id=creator.id,
        )
        db_session.add(safety_training)
        db_session.add(hr_training)
        await db_session.commit()

        _set_user(creator)
        try:
            resp = await client.get("/api/v1/trainings/manager?category=Safety")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
            data = resp.json()
            titles = [t["title"] for t in data]
            assert "Safety Basics" in titles, f"Safety training missing from response: {titles}"
            assert "HR Onboarding" not in titles, f"HR training should not appear: {titles}"
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# T-CT-04: Filter trainings by status=published
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_trainings_filter_by_status_published(client, db_session):
    """
    T-CT-04: GET /api/v1/trainings/manager?status=published must return only
    published trainings, excluding drafts.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    with patch("app.api.v1.endpoints.trainings.deps.get_users_batch", new_callable=AsyncMock) as mock_batch:
        mock_batch.return_value = {}

        published_training = Training(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            title="Published Course",
            description="A published course",
            category="Compliance",
            structure_type="flat",
            is_published=True,
            is_active=True,
            is_archived=False,
            requires_certificate=False,
            created_by_id=creator.id,
        )
        draft_training = Training(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            title="Draft Course",
            description="A draft course",
            category="Compliance",
            structure_type="flat",
            is_published=False,
            is_active=True,
            is_archived=False,
            requires_certificate=False,
            created_by_id=creator.id,
        )
        db_session.add(published_training)
        db_session.add(draft_training)
        await db_session.commit()

        _set_user(creator)
        try:
            resp = await client.get("/api/v1/trainings/manager?status=published")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
            data = resp.json()
            titles = [t["title"] for t in data]
            assert "Published Course" in titles, f"Published training missing: {titles}"
            assert "Draft Course" not in titles, f"Draft training should not appear: {titles}"
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# Helper: seed a draft training directly into db_session
# ---------------------------------------------------------------------------

def _make_draft_training(tenant_id: str, created_by_id: str, **kwargs) -> Training:
    """Build a Training ORM object in Draft state (is_ready=False, is_published=False, is_archived=False)."""
    defaults = dict(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Test Training",
        description="A test description",
        category="Safety",
        structure_type="flat",
        is_published=False,
        is_active=True,
        is_archived=False,
        is_ready=False,
        requires_certificate=False,
        created_by_id=created_by_id,
    )
    defaults.update(kwargs)
    return Training(**defaults)


def _make_chapter(training_id: str, tenant_id: str) -> Chapter:
    """Build a minimal Chapter ORM object."""
    return Chapter(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        training_id=training_id,
        title="Chapter One",
        content_type=ContentType.RICH_TEXT,
        content_data={"text": "hello"},
        sequence_order=1,
    )


# ---------------------------------------------------------------------------
# T-MR-01: mark-ready succeeds when all conditions are met
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_ready_success(client, db_session):
    """
    BR-305a: POST /trainings/{id}/mark-ready returns 200 and lifecycle_status=="ready"
    when the training has title, description, category, and at least one chapter.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id)
    chapter = _make_chapter(training.id, tenant_id)
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/mark-ready")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["is_ready"] is True, f"is_ready should be True: {data}"
        assert data["lifecycle_status"] == "ready", f"lifecycle_status should be 'ready': {data}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-MR-02: mark-ready succeeds when training has no description (description is optional)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_ready_succeeds_without_description(client, db_session):
    """BR-305a (updated): Description is not required for mark-ready — title + category + ≥1 chapter suffice."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id, description=None)
    chapter = _make_chapter(training.id, tenant_id)
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/mark-ready")
        assert resp.status_code == 200, f"Expected 200 (description optional), got {resp.status_code}: {resp.text}"
        assert resp.json()["is_ready"] is True
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-MR-03: mark-ready fails when training has no chapter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_ready_fails_without_chapter(client, db_session):
    """BR-305a: Training with no chapters must return 400."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/mark-ready")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "lesson" in resp.json()["detail"].lower(), f"Error should mention lesson: {resp.json()}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-MR-04: mark-ready fails when called by a non-owner
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_ready_non_owner_forbidden(client, db_session):
    """BR-305a: A Training Creator who is not the owner must receive 403."""
    tenant_id = str(uuid.uuid4())
    owner = _make_creator(tenant_id)
    other_creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, owner.id)
    chapter = _make_chapter(training.id, tenant_id)
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    # other_creator is NOT the owner
    _set_user(other_creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/mark-ready")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-MR-05: mark-ready fails when training is already in Ready state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_ready_already_ready_fails(client, db_session):
    """BR-305a: Calling mark-ready on an already-ready training must return 400."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id, is_ready=True)
    chapter = _make_chapter(training.id, tenant_id)
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/mark-ready")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-MR-06: mark-ready fails when training is published
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_ready_already_published_fails(client, db_session):
    """BR-305a: Calling mark-ready on a published training must return 400."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id, is_published=True)
    chapter = _make_chapter(training.id, tenant_id)
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/mark-ready")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-MR-06b: mark-ready fails when training is archived
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_ready_already_archived_fails(client, db_session):
    """BR-305a: Calling mark-ready on an archived training must return 400."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id, is_archived=True)
    chapter = _make_chapter(training.id, tenant_id)
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/mark-ready")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-MR-07: mark-ready on a non-existent training returns 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_ready_not_found(client, db_session):
    """mark-ready on an unknown training ID must return 404."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{uuid.uuid4()}/mark-ready")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-MR-08: mark-ready fails when training has no title
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_ready_fails_without_title(client, db_session):
    """BR-305a: Training with no title must return 400."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id, title="")
    chapter = _make_chapter(training.id, tenant_id)
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/mark-ready")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-MR-09: mark-ready fails when training has no category
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_ready_fails_without_category(client, db_session):
    """BR-305a: Training with no category must return 400."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id, category="")
    chapter = _make_chapter(training.id, tenant_id)
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/mark-ready")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# Helpers for send-to-draft tests
# ---------------------------------------------------------------------------

def _make_ready_training(tenant_id: str, created_by_id: str, **kwargs) -> Training:
    """Build a Training ORM object in Ready state (is_ready=True, is_published=False, is_archived=False)."""
    defaults = dict(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Ready Training",
        description="A ready description",
        category="Safety",
        structure_type="flat",
        is_published=False,
        is_active=True,
        is_archived=False,
        is_ready=True,
        requires_certificate=False,
        created_by_id=created_by_id,
    )
    defaults.update(kwargs)
    return Training(**defaults)


def _make_manager(tenant_id: str):
    """Return a UserAuth object for a Business Manager in the given tenant."""
    return make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Business Manager"],
    )


# ---------------------------------------------------------------------------
# T-SD-01: send-to-draft succeeds for the owner Training Creator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_to_draft_owner_success(client, db_session):
    """
    BR-301a: Owner Training Creator can send a Ready training back to Draft.
    Response must be 200 and lifecycle_status == 'draft'.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_ready_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/send-to-draft")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["is_ready"] is False, f"is_ready should be False: {data}"
        assert data["lifecycle_status"] == "draft", f"lifecycle_status should be 'draft': {data}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-SD-02: send-to-draft by a Business Manager (non-owner) is now forbidden
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_to_draft_manager_non_owner_forbidden(client, db_session):
    """
    BR-301: Only the training owner can send a Ready training to Draft.
    A Business Manager who is NOT the owner must receive 403.
    Managers use /unpublish (published → ready) then the creator sends to draft.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)

    training = _make_ready_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/send-to-draft")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-SD-03: send-to-draft fails when training is in Draft state (not Ready)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_to_draft_not_ready_fails(client, db_session):
    """
    BR-301a: Calling send-to-draft on a Draft training (is_ready=False) must
    return 400.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id)  # is_ready=False
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/send-to-draft")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "ready" in resp.json()["detail"].lower(), f"Error should mention ready state: {resp.json()}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-SD-04: send-to-draft from Published state is blocked for everyone
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_to_draft_from_published_blocked(client, db_session):
    """
    BR-301: Published → Draft is not a valid transition via send-to-draft.
    A Manager must use /unpublish (published → ready) first.
    Even a manager calling send-to-draft on a published training gets 400.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)

    training = _make_draft_training(tenant_id, creator.id, is_published=True)
    db_session.add(training)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/send-to-draft")
        assert resp.status_code == 403, f"Expected 403 (not owner), got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-SD-04b: send-to-draft from Published state — owner gets 400 (must unpublish first)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_to_draft_from_published_owner_blocked(client, db_session):
    """
    BR-301: Even the training owner cannot send a Published training to Draft
    via send-to-draft. Must return 400 with a message directing them to use
    /unpublish first. Managers use /unpublish (published → ready); then the
    owner can send to draft.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id, is_published=True)
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/send-to-draft")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "unpublish" in resp.json()["detail"].lower(), f"Error should mention unpublish: {resp.json()}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-SD-04c: send-to-draft on an Archived training returns 400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_to_draft_archived_fails(client, db_session):
    """
    BR-301a: Calling send-to-draft on an Archived training must return 400.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id, is_archived=True)
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/send-to-draft")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "archived" in resp.json()["detail"].lower(), f"Error should mention archived: {resp.json()}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-SD-05: send-to-draft fails for a non-owner Training Creator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_to_draft_non_owner_creator_forbidden(client, db_session):
    """
    BR-301a: A Training Creator who is NOT the owner must receive 403.
    """
    tenant_id = str(uuid.uuid4())
    owner = _make_creator(tenant_id)
    other_creator = _make_creator(tenant_id)

    training = _make_ready_training(tenant_id, owner.id)
    db_session.add(training)
    await db_session.commit()

    # other_creator is NOT the owner
    _set_user(other_creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/send-to-draft")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-SD-06: send-to-draft on a non-existent training returns 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_to_draft_not_found(client, db_session):
    """send-to-draft on an unknown training ID must return 404."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{uuid.uuid4()}/send-to-draft")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# /unpublish endpoint tests (BR-301: published → ready, manager only)
# ---------------------------------------------------------------------------

def _make_published_training(tenant_id: str, created_by_id: str, **kwargs) -> Training:
    """Build a Training ORM object in Published state."""
    defaults = dict(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Published Training",
        description="A published description",
        category="Safety",
        structure_type="flat",
        is_published=True,
        is_active=True,
        is_archived=False,
        is_ready=False,
        requires_certificate=False,
        created_by_id=created_by_id,
    )
    defaults.update(kwargs)
    return Training(**defaults)


# T-UN-01: Manager can unpublish a published training → returns to Ready state
@pytest.mark.asyncio
async def test_unpublish_manager_success(client, db_session):
    """
    BR-301: A Business Manager can unpublish a published training.
    Result: is_published=False, is_ready=True (lifecycle_status='ready').
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)

    training = _make_published_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/unpublish")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["is_published"] is False, f"is_published should be False: {data}"
        assert data["is_ready"] is True, f"is_ready should be True (back to ready): {data}"
        assert data["lifecycle_status"] == "ready", f"lifecycle_status should be 'ready': {data}"
    finally:
        _clear_overrides()


# T-UN-02: Unpublish resets learner progress and enrollments
@pytest.mark.asyncio
async def test_unpublish_resets_learner_progress(client, db_session):
    """
    BR-301: Unpublishing resets all learner progress — enrollments are
    un-completed and UserProgress rows are deleted.
    """
    from sqlalchemy import select as sa_select
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)

    training = _make_published_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.flush()

    learner_id = str(uuid.uuid4())
    enrollment = Enrollment(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=learner_id,
        training_id=training.id,
        is_completed=True,
        completed_at=datetime.now(timezone.utc),
        training_version_id=1,
    )
    progress = UserProgress(
        tenant_id=tenant_id,
        user_id=learner_id,
        training_id=training.id,
        chapter_id=str(uuid.uuid4()),
        status=ProgressStatus.COMPLETED,
        training_version_id=1,
    )
    db_session.add(enrollment)
    db_session.add(progress)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/unpublish")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        await db_session.refresh(enrollment)
        assert enrollment.is_completed is False, "Enrollment should be un-completed"
        assert enrollment.completed_at is None, "completed_at should be cleared"
        assert enrollment.training_version_id is None, "training_version_id should be cleared"

        remaining = await db_session.execute(
            sa_select(UserProgress).where(UserProgress.training_id == training.id)
        )
        assert remaining.scalars().all() == [], "UserProgress rows should be deleted"
    finally:
        _clear_overrides()


# T-UN-03: Creator (non-manager) cannot unpublish → 403
@pytest.mark.asyncio
async def test_unpublish_creator_forbidden(client, db_session):
    """
    BR-301: Only a Business Manager can unpublish. A Training Creator who is
    the owner but does not hold the Business Manager role must receive 403.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_published_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/unpublish")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# T-UN-04: Unpublishing a non-published training → 400
@pytest.mark.asyncio
async def test_unpublish_not_published_fails(client, db_session):
    """
    BR-301: Calling /unpublish on a training that is not published must
    return 400.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)

    training = _make_ready_training(tenant_id, creator.id)  # is_published=False
    db_session.add(training)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/unpublish")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# T-UN-05: Unpublishing an archived training → 400
@pytest.mark.asyncio
async def test_unpublish_archived_fails(client, db_session):
    """
    BR-301: Archived trainings cannot be unpublished. Must return 400.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)

    training = _make_published_training(tenant_id, creator.id, is_archived=True)
    db_session.add(training)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/unpublish")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "archived" in resp.json()["detail"].lower(), f"Error should mention archived: {resp.json()}"
    finally:
        _clear_overrides()


# T-UN-06: Full baton flow — unpublish then send-to-draft
@pytest.mark.asyncio
async def test_unpublish_then_send_to_draft_baton_flow(client, db_session):
    """
    BR-301: Full baton handoff — Manager unpublishes (published → ready),
    then the owner sends to draft (ready → draft). Both steps must succeed.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)

    training = _make_published_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    # Step 1: Manager unpublishes → ready
    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/unpublish")
        assert resp.status_code == 200, f"Unpublish failed: {resp.text}"
        assert resp.json()["lifecycle_status"] == "ready"
    finally:
        _clear_overrides()

    # Step 2: Owner sends to draft → draft
    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/send-to-draft")
        assert resp.status_code == 200, f"Send-to-draft failed: {resp.text}"
        assert resp.json()["lifecycle_status"] == "draft"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# Helpers for publish / archive tests
# ---------------------------------------------------------------------------

def _make_manager(tenant_id: str):
    """Return a UserAuth object for a Business Manager in the given tenant."""
    return make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Business Manager"],
    )


def _make_ready_training(tenant_id: str, created_by_id: str, **kwargs) -> Training:
    """Build a Training ORM object in Ready state."""
    defaults = dict(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Ready Training",
        description="A ready description",
        category="Safety",
        structure_type="flat",
        is_published=False,
        is_active=True,
        is_archived=False,
        is_ready=True,
        requires_certificate=False,
        created_by_id=created_by_id,
    )
    defaults.update(kwargs)
    return Training(**defaults)


def _make_published_training(tenant_id: str, created_by_id: str, **kwargs) -> Training:
    """Build a Training ORM object in Published state."""
    defaults = dict(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Published Training",
        description="A published description",
        category="Safety",
        structure_type="flat",
        is_published=True,
        is_active=True,
        is_archived=False,
        is_ready=True,
        requires_certificate=False,
        created_by_id=created_by_id,
    )
    defaults.update(kwargs)
    return Training(**defaults)


def _make_enrollment(training_id: str, tenant_id: str, user_id: str, is_completed: bool = False) -> Enrollment:
    """Build an Enrollment ORM object."""
    return Enrollment(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user_id,
        training_id=training_id,
        is_completed=is_completed,
    )


def _make_assignment(training_id: str, tenant_id: str, user_id: str, due_date=None) -> TrainingAssignment:
    """Build a TrainingAssignment ORM object."""
    return TrainingAssignment(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        training_id=training_id,
        user_id=user_id,
        due_date=due_date,
    )


# ---------------------------------------------------------------------------
# Publish endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_publish_success(client, db_session):
    """Manager can publish a Ready training → 200, lifecycle_status == 'published'."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)

    training = _make_ready_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/publish")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["is_published"] is True, f"is_published should be True: {data}"
        assert data["lifecycle_status"] == "published", f"lifecycle_status should be 'published': {data}"
        assert data["version"] == 2, f"version should be incremented to 2 (from default 1): {data}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_publish_not_ready_fails(client, db_session):
    """Attempting to publish a Draft training (is_ready=False) must return 400."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)

    training = _make_draft_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/publish")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_publish_creator_forbidden(client, db_session):
    """Training Creator (not a Manager) attempting to publish must receive 403."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_ready_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/publish")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_publish_already_published_fails(client, db_session):
    """Attempting to publish an already-published training must return 400."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)

    training = _make_published_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/publish")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# Archive endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_archive_success(client, db_session):
    """Manager can archive a Published training with no blocking enrollments → 200, lifecycle_status == 'archived'."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)

    training = _make_published_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/archive")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["is_archived"] is True, f"is_archived should be True: {data}"
        assert data["lifecycle_status"] == "archived", f"lifecycle_status should be 'archived': {data}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_archive_not_published_fails(client, db_session):
    """Attempting to archive a Draft training must return 400."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)

    training = _make_draft_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/archive")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_archive_gate_blocks_active_learner(client, db_session):
    """BR-503: Archive must be blocked if any learner has an incomplete assignment with a future due_date."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)
    learner_id = str(uuid.uuid4())

    training = _make_published_training(tenant_id, creator.id)
    enrollment = _make_enrollment(training.id, tenant_id, learner_id, is_completed=False)
    future_due = datetime.now(timezone.utc) + timedelta(days=30)
    assignment = _make_assignment(training.id, tenant_id, learner_id, due_date=future_due)

    db_session.add(training)
    db_session.add(enrollment)
    db_session.add(assignment)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/archive")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "Cannot archive" in resp.json()["detail"], f"Error detail mismatch: {resp.json()}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_archive_creator_forbidden(client, db_session):
    """Training Creator (not a Manager) attempting to archive must receive 403."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_published_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/archive")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_archive_gate_allows_when_all_completed(client, db_session):
    """BR-503: Archive must succeed when all enrolled learners have completed the training."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)
    learner_id = str(uuid.uuid4())

    training = _make_published_training(tenant_id, creator.id)
    # Enrollment is completed — no blocking reason
    enrollment = _make_enrollment(training.id, tenant_id, learner_id, is_completed=True)
    future_due = datetime.now(timezone.utc) + timedelta(days=30)
    assignment = _make_assignment(training.id, tenant_id, learner_id, due_date=future_due)

    db_session.add(training)
    db_session.add(enrollment)
    db_session.add(assignment)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/archive")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["is_archived"] is True, f"is_archived should be True: {data}"
        assert data["lifecycle_status"] == "archived", f"lifecycle_status should be 'archived': {data}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_archive_gate_allows_when_due_date_passed(client, db_session):
    """BR-503: Archive must succeed when the assignment due_date is in the past (even if incomplete)."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    manager = _make_manager(tenant_id)
    learner_id = str(uuid.uuid4())

    training = _make_published_training(tenant_id, creator.id)
    # Enrollment is NOT completed, but the due_date is in the past — not blocking
    enrollment = _make_enrollment(training.id, tenant_id, learner_id, is_completed=False)
    past_due = datetime.now(timezone.utc) - timedelta(days=5)
    assignment = _make_assignment(training.id, tenant_id, learner_id, due_date=past_due)

    db_session.add(training)
    db_session.add(enrollment)
    db_session.add(assignment)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/archive")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["is_archived"] is True, f"is_archived should be True: {data}"
        assert data["lifecycle_status"] == "archived", f"lifecycle_status should be 'archived': {data}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# C8: GET /{id}/structure must include all Training fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_structure_includes_tags(client, db_session):
    """GET /structure must return tags set on the training."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = Training(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Tagged Training",
        description="desc",
        category="Safety",
        structure_type="flat",
        is_published=True,
        is_active=True,
        is_archived=False,
        is_ready=True,
        requires_certificate=False,
        tags=["onboarding", "compliance"],
        created_by_id=creator.id,
    )
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.get(f"/api/v1/trainings/{training.id}/structure")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "tags" in data, "Response must include 'tags' field"
        assert set(data["tags"]) == {"onboarding", "compliance"}, f"Unexpected tags: {data['tags']}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_get_structure_includes_category(client, db_session):
    """GET /structure must return the category set on the training."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = Training(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Category Training",
        description="desc",
        category="Compliance",
        structure_type="flat",
        is_published=True,
        is_active=True,
        is_archived=False,
        is_ready=True,
        requires_certificate=True,
        tags=[],
        created_by_id=creator.id,
    )
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.get(f"/api/v1/trainings/{training.id}/structure")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("category") == "Compliance", f"Expected category='Compliance', got: {data.get('category')}"
        assert data.get("requires_certificate") is True, f"Expected requires_certificate=True, got: {data.get('requires_certificate')}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_get_structure_includes_is_ready(client, db_session):
    """GET /structure must return is_ready=True when the training is in Ready state."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = Training(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Ready Training",
        description="desc",
        category="IT",
        structure_type="flat",
        is_published=False,
        is_active=True,
        is_archived=False,
        is_ready=True,
        requires_certificate=False,
        tags=[],
        created_by_id=creator.id,
    )
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.get(f"/api/v1/trainings/{training.id}/structure")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("is_ready") is True, f"Expected is_ready=True, got: {data.get('is_ready')}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_get_structure_includes_lifecycle_status(client, db_session):
    """GET /structure must include lifecycle_status='draft' for an unpublished training."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = Training(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Draft Training",
        description="desc",
        category="HR",
        structure_type="flat",
        is_published=False,
        is_active=True,
        is_archived=False,
        is_ready=False,
        requires_certificate=False,
        tags=[],
        created_by_id=creator.id,
    )
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.get(f"/api/v1/trainings/{training.id}/structure")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("lifecycle_status") == "draft", (
            f"Expected lifecycle_status='draft', got: {data.get('lifecycle_status')}"
        )
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# COL1: Draft-only edit lock on chapter endpoints (BR-301, BR-302)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_chapter_allowed_when_draft(client, db_session):
    """BR-301: Owner can add a chapter to a Draft training (is_ready=False, is_published=False)."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters",
            json={"title": "New Chapter", "content_type": "RICH_TEXT", "content_data": {}, "sequence_order": 1},
        )
        assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_create_chapter_blocked_when_ready(client, db_session):
    """BR-301: Cannot add a chapter when training is in Ready state (is_ready=True) — must return 403."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id, is_ready=True)
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters",
            json={"title": "New Chapter", "content_type": "RICH_TEXT", "content_data": {}, "sequence_order": 1},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_create_chapter_blocked_when_published(client, db_session):
    """BR-301: Cannot add a chapter when training is Published — must return 403."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id, is_published=True)
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters",
            json={"title": "New Chapter", "content_type": "RICH_TEXT", "content_data": {}, "sequence_order": 1},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_create_chapter_blocked_when_archived(client, db_session):
    """BR-301: Cannot add a chapter when training is Archived — must return 403."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id, is_archived=True)
    db_session.add(training)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters",
            json={"title": "New Chapter", "content_type": "RICH_TEXT", "content_data": {}, "sequence_order": 1},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_update_chapter_blocked_when_ready(client, db_session):
    """BR-301: Cannot update a chapter when training is in Ready state — must return 403."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id, is_ready=True)
    chapter = _make_chapter(training.id, tenant_id)
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.patch(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}",
            json={"title": "Updated Title"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_delete_chapter_blocked_when_ready(client, db_session):
    """BR-301: Cannot delete a chapter when training is in Ready state — must return 403."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id, is_ready=True)
    chapter = _make_chapter(training.id, tenant_id)
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.delete(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}",
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_collaborator_can_edit_draft(client, db_session):
    """BR-302: A collaborator on a Draft training can create a chapter."""
    tenant_id = str(uuid.uuid4())
    owner = _make_creator(tenant_id)
    collaborator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, owner.id)
    collab_record = TrainingCollaborator(training_id=training.id, user_id=collaborator.id)
    db_session.add(training)
    db_session.add(collab_record)
    await db_session.commit()

    _set_user(collaborator)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters",
            json={"title": "Collab Chapter", "content_type": "RICH_TEXT", "content_data": {}, "sequence_order": 1},
        )
        assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_collaborator_blocked_from_editing_ready_training(client, db_session):
    """BR-302: Collaborator cannot edit a Ready training — must return 403."""
    tenant_id = str(uuid.uuid4())
    owner = _make_creator(tenant_id)
    collaborator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, owner.id, is_ready=True)
    collab_record = TrainingCollaborator(training_id=training.id, user_id=collaborator.id)
    db_session.add(training)
    db_session.add(collab_record)
    await db_session.commit()

    _set_user(collaborator)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters",
            json={"title": "Collab Chapter", "content_type": "RICH_TEXT", "content_data": {}, "sequence_order": 1},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_non_owner_non_collaborator_blocked(client, db_session):
    """BR-301/BR-302: A Training Creator who is neither owner nor collaborator must be 403 on Draft too."""
    tenant_id = str(uuid.uuid4())
    owner = _make_creator(tenant_id)
    other_creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, owner.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(other_creator)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters",
            json={"title": "Unauthorized Chapter", "content_type": "RICH_TEXT", "content_data": {}, "sequence_order": 1},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# COL2: Add/remove collaborator allowed at any training state (BR-302)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_collaborator_allowed_when_ready(client, db_session):
    """BR-302: Owner can add a collaborator to a Ready training (not just Draft)."""
    tenant_id = str(uuid.uuid4())
    owner = _make_creator(tenant_id)
    collaborator = _make_creator(tenant_id)

    training = _make_ready_training(tenant_id, owner.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(owner)
    try:
        with patch("app.core.events.publisher.publish_event", new_callable=AsyncMock):
            resp = await client.post(
                f"/api/v1/trainings/{training.id}/collaborators",
                json=[collaborator.id],
            )
        assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.text}"
        ids = [c["user_id"] for c in resp.json()]
        assert collaborator.id in ids
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_add_collaborator_allowed_when_published(client, db_session):
    """BR-302: Owner can add a collaborator to a Published training."""
    tenant_id = str(uuid.uuid4())
    owner = _make_creator(tenant_id)
    collaborator = _make_creator(tenant_id)

    training = _make_published_training(tenant_id, owner.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(owner)
    try:
        with patch("app.core.events.publisher.publish_event", new_callable=AsyncMock):
            resp = await client.post(
                f"/api/v1/trainings/{training.id}/collaborators",
                json=[collaborator.id],
            )
        assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.text}"
        ids = [c["user_id"] for c in resp.json()]
        assert collaborator.id in ids
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_remove_collaborator_allowed_when_ready(client, db_session):
    """BR-302: Owner can remove a collaborator from a Ready training."""
    tenant_id = str(uuid.uuid4())
    owner = _make_creator(tenant_id)
    collaborator = _make_creator(tenant_id)

    training = _make_ready_training(tenant_id, owner.id)
    collab_record = TrainingCollaborator(training_id=training.id, user_id=collaborator.id)
    db_session.add(training)
    db_session.add(collab_record)
    await db_session.commit()

    _set_user(owner)
    try:
        resp = await client.delete(
            f"/api/v1/trainings/{training.id}/collaborators/{collaborator.id}",
        )
        assert resp.status_code in (200, 204), f"Expected 200/204, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_add_collaborator_publishes_notification_event(client, db_session):
    """BR-302a: Adding a collaborator publishes a COLLABORATOR_ADDED event."""
    tenant_id = str(uuid.uuid4())
    owner = _make_creator(tenant_id)
    collaborator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, owner.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(owner)
    try:
        with patch("app.core.events.publisher.publish_event", new_callable=AsyncMock) as mock_publish:
            resp = await client.post(
                f"/api/v1/trainings/{training.id}/collaborators",
                json=[collaborator.id],
            )
            assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.text}"
            # Verify COLLABORATOR_ADDED event was published
            calls = [call for call in mock_publish.call_args_list if call.args[0] == "COLLABORATOR_ADDED"]
            assert len(calls) >= 1, f"Expected COLLABORATOR_ADDED event, got calls: {mock_publish.call_args_list}"
            payload = calls[0].args[1]
            assert payload["collaborator_user_id"] == collaborator.id
            assert payload["training_id"] == training.id
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# BR-309a: Role-filtered audit endpoint
# ---------------------------------------------------------------------------

def _make_audit_log(tenant_id: str, training_id: str, action: str, user_id: str = None):
    """Build an AuditLog ORM object for a training-level event."""
    from app.models.audit_log import AuditLog
    return AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user_id or str(uuid.uuid4()),
        action=action,
        entity_type="training",
        entity_id=training_id,
        metadata_json=None,
    )


@pytest.mark.asyncio
async def test_audit_owner_sees_all_events(client, db_session):
    """
    BR-309a: Training owner (Creator who created it) sees ALL audit events,
    including non-state-transition events like COLLABORATOR_ADDED.
    """
    tenant_id = str(uuid.uuid4())
    owner = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, owner.id)
    db_session.add(training)

    log_state = _make_audit_log(tenant_id, training.id, "MARK_READY", owner.id)
    log_collab = _make_audit_log(tenant_id, training.id, "COLLABORATOR_ADDED", owner.id)
    db_session.add(log_state)
    db_session.add(log_collab)
    await db_session.commit()

    _set_user(owner)
    try:
        resp = await client.get(f"/api/v1/trainings/{training.id}/audit")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        actions = [e["action"] for e in resp.json()]
        assert "MARK_READY" in actions, "Owner should see MARK_READY"
        assert "COLLABORATOR_ADDED" in actions, "Owner should see COLLABORATOR_ADDED"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_audit_collaborator_sees_all_events(client, db_session):
    """
    BR-309a: Active collaborator sees ALL audit events for that training.
    """
    tenant_id = str(uuid.uuid4())
    owner = _make_creator(tenant_id)
    collab_user = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, owner.id)
    db_session.add(training)

    collaborator_row = TrainingCollaborator(
        training_id=training.id,
        user_id=collab_user.id,
    )
    db_session.add(collaborator_row)

    log_state = _make_audit_log(tenant_id, training.id, "MARK_READY", owner.id)
    log_collab = _make_audit_log(tenant_id, training.id, "COLLABORATOR_ADDED", owner.id)
    db_session.add(log_state)
    db_session.add(log_collab)
    await db_session.commit()

    _set_user(collab_user)
    try:
        resp = await client.get(f"/api/v1/trainings/{training.id}/audit")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        actions = [e["action"] for e in resp.json()]
        assert "MARK_READY" in actions, "Collaborator should see MARK_READY"
        assert "COLLABORATOR_ADDED" in actions, "Collaborator should see COLLABORATOR_ADDED"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_audit_manager_sees_all_events(client, db_session):
    """
    Updated: Business Manager who is NOT the owner or collaborator now sees ALL
    audit entries (state transitions AND other events like COLLABORATOR_ADDED).
    """
    tenant_id = str(uuid.uuid4())
    owner = _make_creator(tenant_id)
    manager = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Business Manager"],
    )

    training = _make_draft_training(tenant_id, owner.id)
    db_session.add(training)

    log_state = _make_audit_log(tenant_id, training.id, "MARK_READY", owner.id)
    log_collab = _make_audit_log(tenant_id, training.id, "COLLABORATOR_ADDED", owner.id)
    db_session.add(log_state)
    db_session.add(log_collab)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.get(f"/api/v1/trainings/{training.id}/audit")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        actions = [e["action"] for e in resp.json()]
        assert "MARK_READY" in actions, "Manager should see MARK_READY (state transition)"
        assert "COLLABORATOR_ADDED" in actions, "Manager should now see all events including COLLABORATOR_ADDED"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_audit_non_collaborator_creator_forbidden(client, db_session):
    """
    BR-309a: A Training Creator who is neither owner nor collaborator of a training
    must receive 403 when accessing the audit endpoint.
    """
    tenant_id = str(uuid.uuid4())
    owner = _make_creator(tenant_id)
    other_creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, owner.id)
    db_session.add(training)
    await db_session.commit()

    _set_user(other_creator)
    try:
        resp = await client.get(f"/api/v1/trainings/{training.id}/audit")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_audit_manager_sees_all_action_types(client, db_session):
    """
    Updated: Manager sees ALL action types — both state-transition and non-state events.
    """
    tenant_id = str(uuid.uuid4())
    owner = _make_creator(tenant_id)
    manager = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Business Manager"],
    )

    training = _make_draft_training(tenant_id, owner.id)
    db_session.add(training)

    state_actions = ["MARK_READY", "SEND_TO_DRAFT", "PUBLISH", "UNPUBLISH", "ARCHIVE"]
    non_state_actions = ["COLLABORATOR_ADDED", "COLLABORATOR_REMOVED", "CREATE_TRAINING", "UPDATE_TRAINING"]

    for action in state_actions + non_state_actions:
        db_session.add(_make_audit_log(tenant_id, training.id, action, owner.id))
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.get(f"/api/v1/trainings/{training.id}/audit")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        returned_actions = set(e["action"] for e in resp.json())
        for a in state_actions:
            assert a in returned_actions, f"Manager should see {a}"
        # Managers now see ALL events, including non-state ones
        for a in non_state_actions:
            assert a in returned_actions, f"Manager should now see {a}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_audit_training_not_found(client, db_session):
    """
    GET /audit on a non-existent training must return 404.
    """
    tenant_id = str(uuid.uuid4())
    manager = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Business Manager"],
    )

    _set_user(manager)
    try:
        resp = await client.get(f"/api/v1/trainings/{uuid.uuid4()}/audit")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-QZ-SC-01: Quiz score is rounded to whole number
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quiz_score_is_whole_number(client, db_session):
    """
    Submitting a quiz with 2/3 correct answers must return score=67 (not 66.7).
    """
    from app.models.chapter import Chapter, ContentType
    import json

    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    # Create training + quiz chapter with 3 questions
    q1_id = str(uuid.uuid4())
    q2_id = str(uuid.uuid4())
    q3_id = str(uuid.uuid4())
    opt_correct = str(uuid.uuid4())
    opt_wrong = str(uuid.uuid4())
    training = Training(
        id=str(uuid.uuid4()), tenant_id=tenant_id, title="Quiz Score Test",
        category="test", structure_type="flat", is_published=True,
        created_by_id=creator.id, requires_certificate=False,
    )
    chapter = Chapter(
        id=str(uuid.uuid4()), tenant_id=tenant_id, training_id=training.id,
        title="Quiz", content_type=ContentType.QUIZ, sequence_order=1,
        content_data={
            "passing_score": 80,
            "max_attempts": 0,
            "questions": [
                {"id": q1_id, "text": "Q1", "type": "multiple_choice",
                 "options": [{"id": opt_correct, "text": "A"}, {"id": opt_wrong, "text": "B"}],
                 "correct_option_ids": [opt_correct]},
                {"id": q2_id, "text": "Q2", "type": "multiple_choice",
                 "options": [{"id": opt_correct, "text": "A"}, {"id": opt_wrong, "text": "B"}],
                 "correct_option_ids": [opt_correct]},
                {"id": q3_id, "text": "Q3", "type": "multiple_choice",
                 "options": [{"id": opt_correct, "text": "A"}, {"id": opt_wrong, "text": "B"}],
                 "correct_option_ids": [opt_correct]},
            ],
        },
    )
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    _set_user(creator)
    try:
        # Submit 2 correct, 1 wrong → 2/3 = 66.67% → should round to 67
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/submit-quiz",
            json={"answers": [
                {"question_id": q1_id, "selected_option_ids": [opt_correct]},
                {"question_id": q2_id, "selected_option_ids": [opt_correct]},
                {"question_id": q3_id, "selected_option_ids": [opt_wrong]},
            ]},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        score = data["score"]
        assert isinstance(score, int), f"Score must be int, got {type(score)}: {score}"
        assert score == 67, f"Expected 67, got {score}"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CC-01: Completion count endpoint returns correct count
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_completion_count_returns_zero_when_no_completions(client, db_session):
    """GET /completion-count returns 0 when no enrollments are completed."""
    tenant_id = str(uuid.uuid4())
    manager = _make_manager(tenant_id)
    training = Training(
        id=str(uuid.uuid4()), tenant_id=tenant_id, title="Count Test",
        category="test", structure_type="flat", is_published=True,
        created_by_id=str(uuid.uuid4()), requires_certificate=False,
    )
    db_session.add(training)
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.get(f"/api/v1/trainings/{training.id}/completion-count")
        assert resp.status_code == 200, resp.text
        assert resp.json()["completed_count"] == 0
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_completion_count_counts_completed_enrollments(client, db_session):
    """GET /completion-count reflects the number of completed enrollments."""
    from app.models.enrollment import Enrollment

    tenant_id = str(uuid.uuid4())
    manager = _make_manager(tenant_id)
    training = Training(
        id=str(uuid.uuid4()), tenant_id=tenant_id, title="Count Test 2",
        category="test", structure_type="flat", is_published=True,
        created_by_id=str(uuid.uuid4()), requires_certificate=False,
    )
    db_session.add(training)
    # Add 2 completed + 1 incomplete enrollment
    for _ in range(2):
        db_session.add(Enrollment(
            id=str(uuid.uuid4()), tenant_id=tenant_id, training_id=training.id,
            user_id=str(uuid.uuid4()), is_completed=True,
        ))
    db_session.add(Enrollment(
        id=str(uuid.uuid4()), tenant_id=tenant_id, training_id=training.id,
        user_id=str(uuid.uuid4()), is_completed=False,
    ))
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.get(f"/api/v1/trainings/{training.id}/completion-count")
        assert resp.status_code == 200, resp.text
        assert resp.json()["completed_count"] == 2
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CL-01: Clone training creates a deep copy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clone_training_creates_deep_copy(client, db_session):
    """POST /clone creates a new draft training with cloned modules and chapters."""
    from app.models.module import Module
    from app.models.chapter import Chapter, ContentType

    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = Training(
        id=str(uuid.uuid4()), tenant_id=tenant_id, title="Original",
        category="test", structure_type="flat", is_published=False,
        created_by_id=creator.id, requires_certificate=False,
    )
    module = Module(
        id=str(uuid.uuid4()), tenant_id=tenant_id, training_id=training.id,
        title="Module 1", sequence_order=1,
    )
    chapter = Chapter(
        id=str(uuid.uuid4()), tenant_id=tenant_id, training_id=training.id,
        module_id=module.id, title="Chapter 1", content_type=ContentType.RICH_TEXT,
        sequence_order=1, content_data={"text": "Hello"},
    )
    db_session.add_all([training, module, chapter])
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/clone")
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["title"] == "Copy of Original"
        assert data["is_published"] is False
        assert data["is_ready"] is False
        assert data["id"] != training.id
        # Owner of clone is the requester
        assert data["created_by_id"] == creator.id
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_clone_training_does_not_copy_enrollments(client, db_session):
    """Cloned training has zero enrollments — only the source training's enrollments exist."""
    from sqlalchemy import select as sa_select

    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = Training(
        id=str(uuid.uuid4()), tenant_id=tenant_id, title="With Enrollments",
        category="test", structure_type="flat", is_published=True,
        created_by_id=creator.id, requires_certificate=False,
    )
    db_session.add(training)
    db_session.add(Enrollment(
        id=str(uuid.uuid4()), tenant_id=tenant_id, training_id=training.id,
        user_id=str(uuid.uuid4()), is_completed=True,
    ))
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.post(f"/api/v1/trainings/{training.id}/clone")
        assert resp.status_code == 201, resp.text
        clone_id = resp.json()["id"]

        # Verify clone has no enrollments
        result = await db_session.execute(
            sa_select(Enrollment).where(Enrollment.training_id == clone_id)
        )
        assert result.scalars().all() == [], "Clone must have no enrollments"
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# content_expires_at — BR-802 (creator-set content expiry)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_training_create_accepts_content_expires_at(client, db_session):
    """BR-802: Creator can set content_expires_at when creating a training."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    _set_user(creator)
    try:
        resp = await client.post(
            "/api/v1/trainings",
            json={
                "title": "Expiring Training",
                "category": "Compliance",
                "requires_certificate": False,
                "content_expires_at": "2030-01-01T00:00:00Z",
            },
        )
        assert resp.status_code in (200, 201), resp.text
        data = resp.json()
        assert "content_expires_at" in data
        assert data["content_expires_at"] is not None
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_training_create_no_expires_at_field(client, db_session):
    """BR-802: The old expires_at field no longer exists on the Training response."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    _set_user(creator)
    try:
        resp = await client.post(
            "/api/v1/trainings",
            json={"title": "No Expiry", "category": "Safety", "requires_certificate": False},
        )
        assert resp.status_code in (200, 201), resp.text
        data = resp.json()
        assert "expires_at" not in data, "expires_at must not appear on the Training response"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_auto_archive_uses_content_expires_at(client, db_session):
    """BR-802: Auto-archive endpoint archives trainings whose content_expires_at has passed."""
    from app.core.config import settings

    tenant_id = str(uuid.uuid4())
    past = datetime.now(timezone.utc) - timedelta(days=1)
    future = datetime.now(timezone.utc) + timedelta(days=30)

    expired_training = Training(
        id=str(uuid.uuid4()), tenant_id=tenant_id, title="Expired Content",
        category="test", is_published=True, is_archived=False, is_active=True,
        requires_certificate=False, content_expires_at=past,
    )
    live_training = Training(
        id=str(uuid.uuid4()), tenant_id=tenant_id, title="Still Live",
        category="test", is_published=True, is_archived=False, is_active=True,
        requires_certificate=False, content_expires_at=future,
    )
    db_session.add_all([expired_training, live_training])
    await db_session.commit()

    resp = await client.post(
        "/api/v1/trainings/internal/auto-archive-expired",
        headers={"X-Internal-Api-Key": settings.INTERNAL_API_KEY},
    )
    assert resp.status_code == 200, resp.text

    await db_session.refresh(expired_training)
    await db_session.refresh(live_training)
    assert expired_training.is_archived is True
    assert expired_training.is_published is False
    assert live_training.is_archived is False


# ---------------------------------------------------------------------------
# PATCH /trainings/assignments/{assignment_id} — BR-801
# ---------------------------------------------------------------------------

def _make_manager(tenant_id: str):
    return make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Business Manager"],
    )


@pytest.mark.asyncio
async def test_update_assignment_due_date_success(client, db_session):
    """BR-801: Business Manager can update due_date on an existing assignment."""
    tenant_id = str(uuid.uuid4())
    manager = _make_manager(tenant_id)
    learner_id = str(uuid.uuid4())

    training = Training(
        id=str(uuid.uuid4()), tenant_id=tenant_id, title="T", category="C",
        is_published=True, requires_certificate=False,
    )
    assignment = TrainingAssignment(
        id=str(uuid.uuid4()), training_id=training.id, tenant_id=tenant_id,
        user_id=learner_id, assigned_at=datetime.now(timezone.utc),
    )
    db_session.add_all([training, assignment])
    await db_session.commit()

    new_due = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    _set_user(manager)
    try:
        resp = await client.patch(
            f"/api/v1/trainings/assignments/{assignment.id}",
            json={"due_date": new_due},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == assignment.id
        assert data["due_date"] is not None
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_update_assignment_clears_due_date(client, db_session):
    """BR-801: Passing due_date=null clears the due date on an assignment."""
    tenant_id = str(uuid.uuid4())
    manager = _make_manager(tenant_id)
    learner_id = str(uuid.uuid4())

    training = Training(
        id=str(uuid.uuid4()), tenant_id=tenant_id, title="T", category="C",
        is_published=True, requires_certificate=False,
    )
    assignment = TrainingAssignment(
        id=str(uuid.uuid4()), training_id=training.id, tenant_id=tenant_id,
        user_id=learner_id, due_date=datetime.now(timezone.utc) + timedelta(days=7),
        assigned_at=datetime.now(timezone.utc),
    )
    db_session.add_all([training, assignment])
    await db_session.commit()

    _set_user(manager)
    try:
        resp = await client.patch(
            f"/api/v1/trainings/assignments/{assignment.id}",
            json={"due_date": None},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["due_date"] is None
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_update_assignment_forbidden_for_creator(client, db_session):
    """BR-801: Training Creator cannot update assignment due dates."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    learner_id = str(uuid.uuid4())

    training = Training(
        id=str(uuid.uuid4()), tenant_id=tenant_id, title="T", category="C",
        is_published=True, requires_certificate=False,
    )
    assignment = TrainingAssignment(
        id=str(uuid.uuid4()), training_id=training.id, tenant_id=tenant_id,
        user_id=learner_id, assigned_at=datetime.now(timezone.utc),
    )
    db_session.add_all([training, assignment])
    await db_session.commit()

    _set_user(creator)
    try:
        resp = await client.patch(
            f"/api/v1/trainings/assignments/{assignment.id}",
            json={"due_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()},
        )
        assert resp.status_code == 403, resp.text
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_update_assignment_not_found(client, db_session):
    """PATCH on a nonexistent assignment_id returns 404."""
    tenant_id = str(uuid.uuid4())
    manager = _make_manager(tenant_id)
    _set_user(manager)
    try:
        resp = await client.patch(
            f"/api/v1/trainings/assignments/{uuid.uuid4()}",
            json={"due_date": None},
        )
        assert resp.status_code == 404, resp.text
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_update_assignment_tenant_isolation(client, db_session):
    """Manager from tenant A cannot update an assignment belonging to tenant B."""
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    manager_a = _make_manager(tenant_a)

    training = Training(
        id=str(uuid.uuid4()), tenant_id=tenant_b, title="T", category="C",
        is_published=True, requires_certificate=False,
    )
    assignment = TrainingAssignment(
        id=str(uuid.uuid4()), training_id=training.id, tenant_id=tenant_b,
        user_id=str(uuid.uuid4()), assigned_at=datetime.now(timezone.utc),
    )
    db_session.add_all([training, assignment])
    await db_session.commit()

    _set_user(manager_a)
    try:
        resp = await client.patch(
            f"/api/v1/trainings/assignments/{assignment.id}",
            json={"due_date": None},
        )
        assert resp.status_code == 404, resp.text
    finally:
        _clear_overrides()
