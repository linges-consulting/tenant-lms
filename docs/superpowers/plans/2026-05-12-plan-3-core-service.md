# Core Service Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all core service bugs and missing features: model fields (tags, structure_type, attempt_id, re-certification, completion_lock, video progress), permission escalation bugs, WeasyPrint migration, quiz correctness, progress pushback correctness, dashboard endpoints, and the full T-CO-* test suite.

**Architecture:** All changes are in `app/core_service/`. Each task produces a migration + endpoint fix + tests. Tests use pytest + httpx AsyncClient against a test Postgres DB (SQLite for unit tests where no PG-specific features needed). Run tests with `docker compose exec core-service pytest tests/ -v`.

**Tech Stack:** FastAPI, SQLAlchemy (async + asyncpg), Alembic, WeasyPrint, pytest, httpx

---

## File Map

| File | Action |
|---|---|
| `app/core_service/app/models/training.py` | Modify — add `tags`, `structure_type`, `requires_recertification`, `recertification_period_days` |
| `app/core_service/app/models/enrollment.py` | Modify — add `attempt_id`, `completion_lock` |
| `app/core_service/app/models/progress.py` | Modify — add `resume_position_seconds`, `milestone_25`, `milestone_50`, `milestone_75`, `milestone_100` |
| `app/core_service/app/models/quiz.py` | Modify — add `attempt_id` foreign key scope |
| `app/core_service/alembic/versions/` | Create — migration for all model changes |
| `app/core_service/app/api/v1/endpoints/trainings.py` | Modify — fix permissions, pushback, quiz grading, add filter params |
| `app/core_service/app/api/v1/endpoints/dashboards.py` | Create — Manager, Creator, Employee dashboard endpoints |
| `app/core_service/app/api/v1/endpoints/progress.py` | Create — `POST /progress/video` for video position + milestones |
| `app/core_service/app/api/v1/api.py` | Modify — register dashboards and progress routers |
| `app/core_service/app/utils/pdf.py` | Modify — replace xhtml2pdf with WeasyPrint |
| `app/core_service/requirements.txt` | Modify — add weasyprint, remove xhtml2pdf |
| `app/core_service/tests/conftest.py` | Create — DB setup, JWT helpers, fixtures |
| `app/core_service/tests/api/test_trainings.py` | Create — T-CO-01 to T-CO-50 |
| `app/core_service/tests/api/test_progress.py` | Create — T-CO-51 to T-CO-85 |
| `app/core_service/tests/api/test_certificates.py` | Create — T-CO-86 to T-CO-100 |
| `app/core_service/tests/api/test_dashboards.py` | Create — T-DB-01 to T-DB-09 |
| `app/core_service/tests/api/test_isolation.py` | Create — T-CO cross-tenant isolation tests |

---

### Task 1: Set up test infrastructure

**Files:**
- Create: `app/core_service/tests/conftest.py`
- Create: `app/core_service/tests/__init__.py`
- Create: `app/core_service/tests/api/__init__.py`

- [ ] **Step 1: Create `tests/conftest.py`**

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone
import jwt, uuid

from app.main import app
from app.db.session import get_db
from app.models.base import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
EXTERNAL_JWT_SECRET = "test-external"

@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

def make_jwt(user_id: str, tenant_id: str, roles: list[str], expires_in: int = 3600) -> str:
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": roles,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, EXTERNAL_JWT_SECRET, algorithm="HS256")

def auth(user_id: str, tenant_id: str, roles: list[str] = None) -> dict:
    token = make_jwt(user_id, tenant_id, roles or ["Employee"])
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 2: Add test dependencies to `requirements.txt`**

Ensure present:
```
pytest==7.4.3
pytest-asyncio==0.23.5
httpx==0.26.0
aiosqlite==0.19.0
```

- [ ] **Step 3: Commit**

```bash
git add app/core_service/tests/
git commit -m "test: add core service test infrastructure"
```

---

### Task 2: Add missing model fields + migration

**Files:**
- Modify: `app/core_service/app/models/training.py`
- Modify: `app/core_service/app/models/enrollment.py` (or wherever TrainingAssignment is defined)
- Modify: `app/core_service/app/models/progress.py` (or UserProgress model)

- [ ] **Step 1: Add fields to `Training` model**

```python
# In training.py, add to the Training class:
from sqlalchemy import Column, String, Boolean, Integer, ARRAY, Enum
import enum

class StructureType(str, enum.Enum):
    FLAT = "flat"
    MODULAR = "modular"

# Add these columns to Training:
tags = Column(ARRAY(String), nullable=True, default=list)   # use JSON for SQLite compat
structure_type = Column(String, nullable=False, default="flat")
requires_recertification = Column(Boolean, nullable=False, default=False)
recertification_period_days = Column(Integer, nullable=True)
category = Column(String, nullable=False)  # remove nullable=True
```

Note: For SQLite in tests, use `JSON` type instead of `ARRAY(String)`. Use a conditional import or a custom type.

- [ ] **Step 2: Add fields to `TrainingAssignment` model**

```python
# In the assignment/enrollment model:
completion_lock = Column(Boolean, nullable=False, default=False)
attempt_id = Column(Integer, nullable=False, default=1)
```

- [ ] **Step 3: Add fields to `UserProgress` model**

```python
# In the progress model (UserProgress):
resume_position_seconds = Column(Integer, nullable=True, default=0)
milestone_25 = Column(Boolean, nullable=False, default=False)
milestone_50 = Column(Boolean, nullable=False, default=False)
milestone_75 = Column(Boolean, nullable=False, default=False)
milestone_100 = Column(Boolean, nullable=False, default=False)
attempt_id = Column(Integer, nullable=False, default=1)
```

- [ ] **Step 4: Add `attempt_id` scope to `QuizAttempt` model**

```python
# In QuizAttempt model:
enrollment_attempt_id = Column(Integer, nullable=False, default=1)
```

- [ ] **Step 5: Generate and apply migration**

```bash
docker compose exec core-service alembic revision --autogenerate -m "add tags structure_type recertification attempt_id video_progress fields"
docker compose exec core-service alembic upgrade head
```

- [ ] **Step 6: Write model-level tests**

Create `app/core_service/tests/api/test_trainings.py`:

```python
import pytest, uuid
from tests.conftest import auth

# T-CO-01: Creating a training without category returns 422
@pytest.mark.asyncio
async def test_create_training_requires_category(client, db_session):
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    resp = await client.post("/api/v1/trainings", json={
        "title": "No Category Training",
        "description": "desc",
        "structure_type": "flat",
    }, headers=auth(user_id, tenant_id, ["Training Creator"]))
    assert resp.status_code == 422

# T-CT-01: Creating a training with a valid category succeeds
@pytest.mark.asyncio
async def test_create_training_with_category(client, db_session):
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    resp = await client.post("/api/v1/trainings", json={
        "title": "Safety Training",
        "description": "desc",
        "category": "Safety",
        "structure_type": "flat",
    }, headers=auth(user_id, tenant_id, ["Training Creator"]))
    assert resp.status_code in (200, 201)
    assert resp.json()["category"] == "Safety"

# T-CT-02: Tags are stored and returned
@pytest.mark.asyncio
async def test_create_training_with_tags(client, db_session):
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    resp = await client.post("/api/v1/trainings", json={
        "title": "Tagged Training",
        "description": "desc",
        "category": "HR",
        "structure_type": "flat",
        "tags": ["onboarding", "compliance"],
    }, headers=auth(user_id, tenant_id, ["Training Creator"]))
    assert resp.status_code in (200, 201)
    assert "onboarding" in resp.json()["tags"]

# T-CO-38: structure_type cannot be changed after creation
@pytest.mark.asyncio
async def test_structure_type_immutable_after_creation(client, db_session):
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    create_resp = await client.post("/api/v1/trainings", json={
        "title": "Flat Training",
        "description": "desc",
        "category": "IT",
        "structure_type": "flat",
    }, headers=auth(user_id, tenant_id, ["Training Creator"]))
    training_id = create_resp.json()["id"]

    patch_resp = await client.patch(f"/api/v1/trainings/{training_id}", json={
        "structure_type": "modular",
    }, headers=auth(user_id, tenant_id, ["Training Creator"]))
    assert patch_resp.status_code == 400
```

- [ ] **Step 7: Run tests to confirm behavior**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py -v 2>&1 | tail -20
```

- [ ] **Step 8: Fix the create training endpoint to enforce category and structure_type immutability**

In `trainings.py`, update the create endpoint's Pydantic schema:
```python
class TrainingCreate(BaseModel):
    title: str
    description: str
    category: str          # required — no default
    structure_type: str = "flat"
    tags: list[str] = []
    requires_recertification: bool = False
    recertification_period_days: int | None = None
```

In the update endpoint, reject `structure_type` changes:
```python
if update_data.get("structure_type") and update_data["structure_type"] != training.structure_type:
    raise HTTPException(status_code=400, detail="structure_type cannot be changed after creation.")
```

- [ ] **Step 9: Run tests again — confirm pass**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py -v
```

- [ ] **Step 10: Commit**

```bash
git add app/core_service/app/models/ app/core_service/alembic/ app/core_service/app/api/ app/core_service/tests/
git commit -m "feat: add tags, structure_type, recertification, attempt_id, video progress fields; enforce category required"
```

---

### Task 3: Fix permission escalation bugs

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/trainings.py`
- Modify: `app/core_service/app/api/v1/endpoints/certificates.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/api/test_trainings.py`:

```python
# T-CO-XX (BR-301a): Training Creator cannot assign trainings
@pytest.mark.asyncio
async def test_training_creator_cannot_assign(client, db_session):
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    training_id = str(uuid.uuid4())
    resp = await client.post(f"/api/v1/trainings/{training_id}/assignments/bulk", json={
        "user_ids": [str(uuid.uuid4())],
        "group_ids": [],
    }, headers=auth(creator_id, tenant_id, ["Training Creator"]))
    assert resp.status_code == 403
```

Add to `app/core_service/tests/api/test_certificates.py`:

```python
import pytest, uuid
from tests.conftest import auth

# T-CO-XX (BR-701): Business Manager cannot create certificate templates
@pytest.mark.asyncio
async def test_business_manager_cannot_create_template(client, db_session):
    tenant_id = str(uuid.uuid4())
    mgr_id = str(uuid.uuid4())
    resp = await client.post("/api/v1/certificates/templates", json={
        "name": "My Template",
        "html_content": "<html>{{learner_name}}</html>",
    }, headers=auth(mgr_id, tenant_id, ["Business Manager"]))
    assert resp.status_code == 403
```

- [ ] **Step 2: Run to confirm failures**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_training_creator_cannot_assign tests/api/test_certificates.py::test_business_manager_cannot_create_template -v
```

- [ ] **Step 3: Fix `bulk_assign_training` permission check in `trainings.py`**

Find the permission check (around line 541). Change it to only allow Business Managers and SysAdmins:

```python
# Before:
if not any(role in ["Business Manager", "Training Creator", "Admin"] for role in user_roles):
    raise HTTPException(status_code=403)

# After:
if not any(role in ["Business Manager", "SysAdmin"] for role in user_roles):
    raise HTTPException(status_code=403, detail="Only Business Managers can assign trainings.")
```

- [ ] **Step 4: Fix certificate template create/update/delete to require SysAdmin**

In `certificates.py`, find the template create/update/delete endpoints and replace the permission check:

```python
# Replace any Business Manager permission with SysAdmin-only:
current_user: User = Depends(get_sysadmin)  # use get_sysadmin dep instead of get_business_manager
```

- [ ] **Step 5: Run tests to confirm pass**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py tests/api/test_certificates.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/trainings.py app/core_service/app/api/v1/endpoints/certificates.py
git commit -m "fix: remove Training Creator from assignment permission, enforce SysAdmin-only template CRUD (BR-301a, BR-701)"
```

---

### Task 4: Fix progress pushback — soft delete, cascade, correct notification target

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/trainings.py` (publish_training / pushback section)

- [ ] **Step 1: Write failing tests**

Add to `tests/api/test_progress.py`:

```python
import pytest, uuid
from tests.conftest import auth

# T-CO-XX (BR-402): Publishing a new version pushes back affected users to the changed lesson
@pytest.mark.asyncio
async def test_pushback_resets_to_changed_chapter(client, db_session):
    # Setup: training with 3 chapters, user completed chapters 1-3, chapter 2 changes on re-publish
    # After re-publish: chapter 2 and chapter 3 progress should be reset (cascade forward)
    # Chapter 1 progress should remain
    tenant_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    from app.models.training import Training
    from app.models.chapter import Chapter
    from app.models.progress import UserProgress
    from app.models.enrollment import TrainingAssignment

    training_id = str(uuid.uuid4())
    training = Training(id=training_id, tenant_id=tenant_id, title="T", category="IT",
                        structure_type="flat", is_published=True, created_by_id=owner_id, version=1)
    ch1_id, ch2_id, ch3_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    chapters = [
        Chapter(id=ch1_id, training_id=training_id, title="Ch1", sequence_order=1, content_type="RICH_TEXT", content_data={"html": "a"}),
        Chapter(id=ch2_id, training_id=training_id, title="Ch2", sequence_order=2, content_type="RICH_TEXT", content_data={"html": "b"}),
        Chapter(id=ch3_id, training_id=training_id, title="Ch3", sequence_order=3, content_type="RICH_TEXT", content_data={"html": "c"}),
    ]
    assignment = TrainingAssignment(training_id=training_id, user_id=user_id, tenant_id=tenant_id, attempt_id=1)
    progress = [
        UserProgress(user_id=user_id, chapter_id=ch1_id, training_id=training_id, tenant_id=tenant_id, status="COMPLETED", attempt_id=1),
        UserProgress(user_id=user_id, chapter_id=ch2_id, training_id=training_id, tenant_id=tenant_id, status="COMPLETED", attempt_id=1),
        UserProgress(user_id=user_id, chapter_id=ch3_id, training_id=training_id, tenant_id=tenant_id, status="COMPLETED", attempt_id=1),
    ]
    db_session.add_all([training, *chapters, assignment, *progress])
    await db_session.commit()

    # Re-publish with changed Ch2 content
    resp = await client.post(f"/api/v1/trainings/{training_id}/publish", json={
        "chapters": [
            {"id": ch1_id, "title": "Ch1", "content_data": {"html": "a"}},
            {"id": ch2_id, "title": "Ch2", "content_data": {"html": "CHANGED"}},
            {"id": ch3_id, "title": "Ch3", "content_data": {"html": "c"}},
        ]
    }, headers=auth(owner_id, tenant_id, ["Training Creator"]))
    assert resp.status_code == 200

    from sqlalchemy import select
    result = await db_session.execute(
        select(UserProgress).where(UserProgress.user_id == user_id, UserProgress.training_id == training_id)
    )
    remaining = {p.chapter_id: p.status for p in result.scalars().all()}
    # Ch1 survives, Ch2 and Ch3 are reset (soft-deleted or set to IN_PROGRESS)
    assert remaining.get(ch1_id) == "COMPLETED"
    assert ch2_id not in remaining or remaining[ch2_id] != "COMPLETED"
    assert ch3_id not in remaining or remaining[ch3_id] != "COMPLETED"
```

- [ ] **Step 2: Run to confirm failure**

```bash
docker compose exec core-service pytest tests/api/test_progress.py::test_pushback_resets_to_changed_chapter -v
```

- [ ] **Step 3: Fix progress pushback in `trainings.py` `publish_training`**

Locate the pushback block (around line 856-907). Apply these fixes:

**a) Use soft delete instead of hard delete for enrollment:**
```python
# Before:
await db.execute(delete(Enrollment).where(...))

# After — mark deleted_at instead:
from datetime import datetime, timezone
affected_enrollments = await db.execute(select(Enrollment).where(...))
for enrollment in affected_enrollments.scalars():
    enrollment.deleted_at = datetime.now(timezone.utc)
await db.flush()
```

**b) Cascade reset — find the earliest changed chapter and reset all subsequent progress:**
```python
# Find minimum sequence_order among changed chapters
changed_sequences = [ch.sequence_order for ch in changed_chapters]
min_changed_seq = min(changed_sequences)

# Soft-delete progress for chapters at or after the changed position
chapters_to_reset = await db.execute(
    select(Chapter).where(
        Chapter.training_id == training_id,
        Chapter.sequence_order >= min_changed_seq,
    )
)
reset_chapter_ids = [ch.id for ch in chapters_to_reset.scalars()]

progress_rows = await db.execute(
    select(UserProgress).where(
        UserProgress.chapter_id.in_(reset_chapter_ids),
        UserProgress.tenant_id == tenant_id,
    )
)
for row in progress_rows.scalars():
    row.deleted_at = datetime.now(timezone.utc)
```

**c) Notify the Business Manager, not the learner:**
```python
# When publishing a notification event for pushback, use manager_user_id:
# You'll need to look up the manager for this tenant:
manager_result = await db.execute(
    select(TenantMembership).where(
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.is_business_manager == True,
        TenantMembership.is_active == True,
    )
)
for mgr in manager_result.scalars():
    await publish_event("PROGRESS_RESET", {
        "manager_user_id": mgr.user_id,
        "tenant_id": tenant_id,
        "training_id": training_id,
        "version_id": new_version_id,
        "affected_user_id": affected_user_id,
    })
```

**d) Write audit log entry for progress reset:**
```python
db.add(AuditLog(
    id=str(uuid.uuid4()),
    tenant_id=tenant_id,
    user_id=owner_id,
    action="PROGRESS_RESET",
    entity_type="Training",
    entity_id=training_id,
    metadata_json={"version_id": new_version_id, "affected_users": affected_user_ids},
))
```

- [ ] **Step 4: Run tests**

```bash
docker compose exec core-service pytest tests/api/test_progress.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/trainings.py
git commit -m "fix: progress pushback uses soft delete, cascades forward, notifies manager (BR-402, BR-602)"
```

---

### Task 5: Fix quiz — default attempts, grading, add manager reset endpoint

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/trainings.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/api/test_progress.py`:

```python
# T-CO-XX (BR-407): Default max_attempts is 10
@pytest.mark.asyncio
async def test_quiz_default_max_attempts_is_10(client, db_session):
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    from app.models.training import Training
    from app.models.chapter import Chapter
    from app.models.enrollment import TrainingAssignment

    training_id = str(uuid.uuid4())
    chapter_id = str(uuid.uuid4())
    quiz_content = {
        "questions": [
            {"id": "q1", "type": "multiple_choice", "text": "Q?", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}], "correct_option_ids": ["a"]},
        ]
        # No max_attempts specified — should default to 10
    }
    training = Training(id=training_id, tenant_id=tenant_id, title="T", category="IT", structure_type="flat", is_published=True, created_by_id=user_id, version=1)
    chapter = Chapter(id=chapter_id, training_id=training_id, title="Quiz", sequence_order=1, content_type="QUIZ", content_data=quiz_content)
    assignment = TrainingAssignment(training_id=training_id, user_id=user_id, tenant_id=tenant_id, attempt_id=1)
    db_session.add_all([training, chapter, assignment])
    await db_session.commit()

    # Submit 10 failed attempts — should not lock out until attempt 11
    for i in range(10):
        resp = await client.post(f"/api/v1/trainings/{training_id}/chapters/{chapter_id}/quiz/submit", json={
            "answers": [{"question_id": "q1", "selected_option_ids": ["b"]}]  # wrong answer
        }, headers=auth(user_id, tenant_id))
        # Should return "failed" not "locked" for first 10
        assert resp.json().get("status") != "locked", f"Locked after attempt {i+1}, expected after 10"

    # 11th attempt should result in locked
    resp = await client.post(f"/api/v1/trainings/{training_id}/chapters/{chapter_id}/quiz/submit", json={
        "answers": [{"question_id": "q1", "selected_option_ids": ["b"]}]
    }, headers=auth(user_id, tenant_id))
    assert resp.json().get("status") == "locked"

# T-CO-70: Manager can reset a quiz lockout
@pytest.mark.asyncio
async def test_manager_can_reset_quiz_lockout(client, db_session):
    tenant_id = str(uuid.uuid4())
    manager_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    from app.models.quiz import QuizAttempt
    from app.models.chapter import Chapter
    from app.models.training import Training

    training_id = str(uuid.uuid4())
    chapter_id = str(uuid.uuid4())
    training = Training(id=training_id, tenant_id=tenant_id, title="T", category="IT", structure_type="flat", is_published=True, created_by_id=manager_id, version=1)
    chapter = Chapter(id=chapter_id, training_id=training_id, title="Quiz", sequence_order=1, content_type="QUIZ", content_data={"questions": [], "max_attempts": 3})
    attempt = QuizAttempt(id=str(uuid.uuid4()), user_id=learner_id, chapter_id=chapter_id, tenant_id=tenant_id, is_locked=True, attempt_number=4, enrollment_attempt_id=1)
    db_session.add_all([training, chapter, attempt])
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/trainings/{training_id}/chapters/{chapter_id}/quiz/reset/{learner_id}",
        headers=auth(manager_id, tenant_id, ["Business Manager"])
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Fix quiz default `max_attempts` in `trainings.py`**

```python
# Find: content.get("max_attempts", 3)
# Replace with:
content.get("max_attempts", 10)
```

- [ ] **Step 3: Add manager quiz reset endpoint to `trainings.py`**

```python
@router.post("/{training_id}/chapters/{chapter_id}/quiz/reset/{user_id}")
async def reset_quiz_lockout(
    training_id: str,
    chapter_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_business_manager),
    tenant_id: str = Depends(get_current_tenant_id),
):
    from sqlalchemy import select, delete
    from app.models.quiz import QuizAttempt

    # Verify training belongs to tenant
    training = await db.execute(
        select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id)
    )
    if not training.scalars().first():
        raise HTTPException(status_code=404)

    # Delete all quiz attempts for this user+chapter+tenant (soft delete preferred)
    attempts = await db.execute(
        select(QuizAttempt).where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.chapter_id == chapter_id,
            QuizAttempt.tenant_id == tenant_id,
        )
    )
    for attempt in attempts.scalars():
        attempt.deleted_at = datetime.now(timezone.utc)

    db.add(AuditLog(
        id=str(uuid.uuid4()), tenant_id=tenant_id, user_id=current_user.id,
        action="QUIZ_RESET", entity_type="Chapter", entity_id=chapter_id,
        metadata_json={"target_user_id": user_id},
    ))
    await db.commit()
    return {"message": "Quiz lockout reset."}
```

- [ ] **Step 4: Fix quiz grading for Matching and Ordering question types**

Find the `submit_quiz` grading loop in `trainings.py`. Replace the single generic check with type-aware grading:

```python
for question in questions:
    q_type = question.get("type", "multiple_choice")
    user_answer = answers_map.get(question["id"], {})
    correct_ids = question.get("correct_option_ids", [])

    if q_type in ("multiple_choice", "multiple_select", "true_false"):
        is_correct = sorted(user_answer.get("selected_option_ids", [])) == sorted(correct_ids)
    elif q_type == "ordering":
        # Order matters — exact sequence required
        is_correct = user_answer.get("ordered_ids", []) == correct_ids
    elif q_type == "matching":
        # pairs: list of {left_id, right_id}
        correct_pairs = set(tuple(p) for p in question.get("correct_pairs", []))
        user_pairs = set(tuple(p.values()) for p in user_answer.get("pairs", []))
        is_correct = user_pairs == correct_pairs
    else:
        is_correct = False

    if is_correct:
        correct_count += 1
```

- [ ] **Step 5: Run tests**

```bash
docker compose exec core-service pytest tests/api/test_progress.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/trainings.py
git commit -m "fix: quiz default max_attempts=10, type-aware grading, manager quiz reset endpoint (BR-406, BR-407, T-CO-70)"
```

---

### Task 6: Add missing tenant_id filters — close cross-tenant leakage

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/trainings.py`
- Create: `app/core_service/tests/api/test_isolation.py`

- [ ] **Step 1: Write failing isolation tests**

```python
import pytest, uuid
from tests.conftest import auth

# T-CO cross-tenant: complete_chapter cannot access another tenant's training
@pytest.mark.asyncio
async def test_complete_chapter_tenant_isolation(client, db_session):
    from app.models.training import Training
    from app.models.chapter import Chapter

    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    training_id = str(uuid.uuid4())
    chapter_id = str(uuid.uuid4())

    training = Training(id=training_id, tenant_id=tenant_a, title="T", category="IT", structure_type="flat", is_published=True, created_by_id=owner_id, version=1)
    chapter = Chapter(id=chapter_id, training_id=training_id, title="Ch1", sequence_order=1, content_type="RICH_TEXT", content_data={"html": "x"})
    db_session.add_all([training, chapter])
    await db_session.commit()

    # User from tenant_b tries to complete chapter in tenant_a training
    attacker_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/trainings/{training_id}/chapters/{chapter_id}/complete",
        headers=auth(attacker_id, tenant_b)
    )
    assert resp.status_code in (403, 404)

# T-CO cross-tenant: submit_quiz cannot access another tenant's quiz
@pytest.mark.asyncio
async def test_submit_quiz_tenant_isolation(client, db_session):
    from app.models.training import Training
    from app.models.chapter import Chapter

    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    training_id = str(uuid.uuid4())
    chapter_id = str(uuid.uuid4())

    training = Training(id=training_id, tenant_id=tenant_a, title="T", category="IT", structure_type="flat", is_published=True, created_by_id=owner_id, version=1)
    chapter = Chapter(id=chapter_id, training_id=training_id, title="Quiz", sequence_order=1, content_type="QUIZ", content_data={"questions": []})
    db_session.add_all([training, chapter])
    await db_session.commit()

    attacker_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/trainings/{training_id}/chapters/{chapter_id}/quiz/submit",
        json={"answers": []},
        headers=auth(attacker_id, tenant_b)
    )
    assert resp.status_code in (403, 404)
```

- [ ] **Step 2: Run to confirm failures**

```bash
docker compose exec core-service pytest tests/api/test_isolation.py -v
```

- [ ] **Step 3: Fix `complete_chapter` training fetch to include `tenant_id`**

Find the training fetch in `complete_chapter` (around line 1568):

```python
# Before:
training = await db.execute(select(Training).where(Training.id == training_id))

# After:
training = await db.execute(
    select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id)
)
if not training.scalars().first():
    raise HTTPException(status_code=404)
```

- [ ] **Step 4: Fix `submit_quiz` training fetch to include `tenant_id`**

Same fix in the `submit_quiz` handler (around line 1880):

```python
training = await db.execute(
    select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id)
)
```

- [ ] **Step 5: Run isolation tests to confirm pass**

```bash
docker compose exec core-service pytest tests/api/test_isolation.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/trainings.py app/core_service/tests/api/test_isolation.py
git commit -m "fix: add tenant_id filter to complete_chapter and submit_quiz fetches (C-602)"
```

---

### Task 7: Replace xhtml2pdf with WeasyPrint, fix certificate variables

**Files:**
- Modify: `app/core_service/app/utils/pdf.py`
- Modify: `app/core_service/requirements.txt`

- [ ] **Step 1: Update `requirements.txt`**

```
# Remove:
xhtml2pdf

# Add:
weasyprint==62.3
```

- [ ] **Step 2: Write failing test**

Create `app/core_service/tests/api/test_certificates.py`:

```python
import pytest, uuid
from tests.conftest import auth

# T-CO-97: Certificate PDF is generated with correct variables resolved
@pytest.mark.asyncio
async def test_certificate_pdf_variables_resolved(client, db_session):
    from app.models.training import Training
    from app.models.certificate import Certificate, CertificateTemplate
    from app.models.tenant import Tenant

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    training_id = str(uuid.uuid4())
    cert_id = str(uuid.uuid4())
    template_id = str(uuid.uuid4())

    template_html = "<html><body><p>{{learner_name}}</p><p>{{training_title}}</p><p>{{tenant_name}}</p><p>{{completion_date}}</p></body></html>"
    tenant = Tenant(id=tenant_id, name="AcmeCo", primary_color="#123456", secondary_color="#abcdef")
    template = CertificateTemplate(id=template_id, tenant_id=tenant_id, name="Default", html_content=template_html, is_active=True)
    training = Training(id=training_id, tenant_id=tenant_id, title="Safety 101", category="Safety", structure_type="flat", is_published=True, created_by_id=user_id, version=1, template_id=template_id)
    cert = Certificate(id=cert_id, user_id=user_id, training_id=training_id, tenant_id=tenant_id, template_id=template_id, certificate_number="CERT-001", issued_at="2026-05-12T00:00:00Z", data={"learner_name": "Jane Doe", "training_title": "Safety 101", "completion_date": "2026-05-12", "tenant_name": "AcmeCo"})
    db_session.add_all([tenant, template, training, cert])
    await db_session.commit()

    resp = await client.get(f"/api/v1/certificates/{cert_id}/pdf", headers=auth(user_id, tenant_id))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    # Check the PDF bytes start with the PDF magic bytes
    assert resp.content[:4] == b"%PDF"
```

- [ ] **Step 3: Run to confirm failure**

```bash
docker compose exec core-service pytest tests/api/test_certificates.py::test_certificate_pdf_variables_resolved -v
```

- [ ] **Step 4: Rewrite `app/utils/pdf.py` using WeasyPrint**

```python
from weasyprint import HTML
from string import Template

REQUIRED_VARS = [
    "tenant_name", "tenant_logo", "tenant_primary_color",
    "learner_name", "training_title", "completion_date",
]

def render_certificate_pdf(html_template: str, variables: dict) -> bytes:
    """Render HTML template to a single-page landscape PDF using WeasyPrint."""
    # Replace {{var}} placeholders
    html = html_template
    for key, value in variables.items():
        html = html.replace(f"{{{{{key}}}}}", str(value or ""))

    # Inject landscape page size if not present
    landscape_css = "<style>@page { size: A4 landscape; margin: 1cm; }</style>"
    if "@page" not in html:
        html = html.replace("<head>", f"<head>{landscape_css}", 1)
        if "<head>" not in html:
            html = landscape_css + html

    return HTML(string=html).write_pdf()
```

- [ ] **Step 5: Update certificate issuance data to use spec-compliant variable names**

Find `_process_training_completion` in `trainings.py`. Fix the `cert_data` dict to use canonical keys:

```python
cert_data = {
    "learner_name": f"{user.first_name} {user.last_name}",
    "training_title": training.title,
    "completion_date": datetime.now(timezone.utc).date().isoformat(),
    "certificate_number": cert_number,
    "tenant_name": tenant.name,
    "tenant_logo": getattr(tenant, "logo_url", ""),
    "tenant_primary_color": tenant.primary_color,
}
```

- [ ] **Step 6: Run tests**

```bash
docker compose exec core-service pytest tests/api/test_certificates.py -v
```

- [ ] **Step 7: Commit**

```bash
git add app/core_service/app/utils/pdf.py app/core_service/requirements.txt app/core_service/app/api/v1/endpoints/trainings.py app/core_service/tests/api/test_certificates.py
git commit -m "fix: replace xhtml2pdf with WeasyPrint, fix certificate variable names (C-507, BR-705)"
```

---

### Task 8: Add video progress endpoint

**Files:**
- Create: `app/core_service/app/api/v1/endpoints/progress.py`
- Modify: `app/core_service/app/api/v1/api.py`

- [ ] **Step 1: Write failing tests**

Create `app/core_service/tests/api/test_video_progress.py`:

```python
import pytest, uuid
from tests.conftest import auth

# T-CO-81: POST /progress/video saves resume position
@pytest.mark.asyncio
async def test_video_progress_saves_resume_position(client, db_session):
    from app.models.training import Training
    from app.models.chapter import Chapter
    from app.models.enrollment import TrainingAssignment

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    training_id = str(uuid.uuid4())
    chapter_id = str(uuid.uuid4())

    training = Training(id=training_id, tenant_id=tenant_id, title="T", category="IT", structure_type="flat", is_published=True, created_by_id=user_id, version=1)
    chapter = Chapter(id=chapter_id, training_id=training_id, title="Video", sequence_order=1, content_type="VIDEO", content_data={"url": "https://example.com/video.mp4"})
    assignment = TrainingAssignment(training_id=training_id, user_id=user_id, tenant_id=tenant_id, attempt_id=1)
    db_session.add_all([training, chapter, assignment])
    await db_session.commit()

    resp = await client.post("/api/v1/progress/video", json={
        "training_id": training_id,
        "chapter_id": chapter_id,
        "position_seconds": 142,
        "milestone_25": True,
        "milestone_50": False,
        "milestone_75": False,
        "milestone_100": False,
    }, headers=auth(user_id, tenant_id))
    assert resp.status_code == 200

    # Verify stored
    from sqlalchemy import select
    from app.models.progress import UserProgress
    result = await db_session.execute(
        select(UserProgress).where(UserProgress.user_id == user_id, UserProgress.chapter_id == chapter_id)
    )
    row = result.scalars().first()
    assert row is not None
    assert row.resume_position_seconds == 142
    assert row.milestone_25 == True

# T-CO-82: milestone_100 + onEnded marks chapter complete
@pytest.mark.asyncio
async def test_video_milestone_100_marks_complete(client, db_session):
    from app.models.training import Training
    from app.models.chapter import Chapter
    from app.models.enrollment import TrainingAssignment

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    training_id = str(uuid.uuid4())
    chapter_id = str(uuid.uuid4())

    training = Training(id=training_id, tenant_id=tenant_id, title="T", category="IT", structure_type="flat", is_published=True, created_by_id=user_id, version=1)
    chapter = Chapter(id=chapter_id, training_id=training_id, title="Video", sequence_order=1, content_type="VIDEO", content_data={"url": "https://example.com/video.mp4"})
    assignment = TrainingAssignment(training_id=training_id, user_id=user_id, tenant_id=tenant_id, attempt_id=1)
    db_session.add_all([training, chapter, assignment])
    await db_session.commit()

    resp = await client.post("/api/v1/progress/video", json={
        "training_id": training_id,
        "chapter_id": chapter_id,
        "position_seconds": 600,
        "milestone_100": True,
        "video_ended": True,
    }, headers=auth(user_id, tenant_id))
    assert resp.status_code == 200

    from sqlalchemy import select
    from app.models.progress import UserProgress
    result = await db_session.execute(
        select(UserProgress).where(UserProgress.user_id == user_id, UserProgress.chapter_id == chapter_id)
    )
    row = result.scalars().first()
    assert row.status == "COMPLETED"
```

- [ ] **Step 2: Create `progress.py` endpoint**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

from app.db.session import get_db
from app.core.deps import get_current_user, get_current_tenant_id
from app.models.progress import UserProgress
from app.models.chapter import Chapter
from app.models.training import Training
from app.models.enrollment import TrainingAssignment

router = APIRouter()

class VideoProgressUpdate(BaseModel):
    training_id: str
    chapter_id: str
    position_seconds: int = 0
    milestone_25: bool = False
    milestone_50: bool = False
    milestone_75: bool = False
    milestone_100: bool = False
    video_ended: bool = False

@router.post("/video")
async def update_video_progress(
    update: VideoProgressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant_id),
):
    # Verify chapter belongs to this tenant's training
    chapter_result = await db.execute(
        select(Chapter).join(Training).where(
            Chapter.id == update.chapter_id,
            Training.id == update.training_id,
            Training.tenant_id == tenant_id,
        )
    )
    chapter = chapter_result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404)

    # Upsert UserProgress
    result = await db.execute(
        select(UserProgress).where(
            UserProgress.user_id == current_user.id,
            UserProgress.chapter_id == update.chapter_id,
            UserProgress.tenant_id == tenant_id,
        )
    )
    row = result.scalars().first()
    if not row:
        row = UserProgress(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            chapter_id=update.chapter_id,
            training_id=update.training_id,
            tenant_id=tenant_id,
            status="IN_PROGRESS",
            attempt_id=1,
        )
        db.add(row)

    row.resume_position_seconds = update.position_seconds
    if update.milestone_25:
        row.milestone_25 = True
    if update.milestone_50:
        row.milestone_50 = True
    if update.milestone_75:
        row.milestone_75 = True
    if update.milestone_100:
        row.milestone_100 = True
    if update.video_ended and update.milestone_100:
        row.status = "COMPLETED"
        row.completed_at = datetime.now(timezone.utc)

    await db.commit()
    return {"status": row.status, "resume_position_seconds": row.resume_position_seconds}
```

- [ ] **Step 3: Register in `api.py`**

```python
from app.api.v1.endpoints import progress
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])
```

- [ ] **Step 4: Run tests**

```bash
docker compose exec core-service pytest tests/api/test_video_progress.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/progress.py app/core_service/app/api/v1/api.py app/core_service/tests/
git commit -m "feat: add video progress endpoint with resume position and milestones (C-510, T-CO-81-83)"
```

---

### Task 9: Add dashboard endpoints

**Files:**
- Create: `app/core_service/app/api/v1/endpoints/dashboards.py`
- Modify: `app/core_service/app/api/v1/api.py`
- Create: `app/core_service/tests/api/test_dashboards.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest, uuid
from tests.conftest import auth

# T-DB-01: Manager dashboard returns overdue count, completion rate, quiz lockout count
@pytest.mark.asyncio
async def test_manager_dashboard(client, db_session):
    tenant_id = str(uuid.uuid4())
    manager_id = str(uuid.uuid4())
    resp = await client.get("/api/v1/dashboards/manager", headers=auth(manager_id, tenant_id, ["Business Manager"]))
    assert resp.status_code == 200
    data = resp.json()
    assert "total_employees" in data
    assert "overdue_assignments" in data
    assert "quiz_lockouts" in data
    assert "completion_rate" in data

# T-DB-05: Creator dashboard returns owned training stats
@pytest.mark.asyncio
async def test_creator_dashboard(client, db_session):
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    resp = await client.get("/api/v1/dashboards/creator", headers=auth(creator_id, tenant_id, ["Training Creator"]))
    assert resp.status_code == 200
    data = resp.json()
    assert "total_trainings" in data
    assert "published" in data
    assert "draft" in data

# T-DB-07: Employee dashboard returns in-progress and upcoming due trainings
@pytest.mark.asyncio
async def test_employee_dashboard(client, db_session):
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    resp = await client.get("/api/v1/dashboards/employee", headers=auth(user_id, tenant_id))
    assert resp.status_code == 200
    data = resp.json()
    assert "in_progress" in data
    assert "upcoming_due" in data
    assert "recently_completed" in data
```

- [ ] **Step 2: Create `dashboards.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timezone, timedelta

from app.db.session import get_db
from app.core.deps import get_current_user, get_current_tenant_id
from app.models.training import Training
from app.models.enrollment import TrainingAssignment
from app.models.progress import UserProgress
from app.models.quiz import QuizAttempt

router = APIRouter()

@router.get("/manager")
async def manager_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant_id),
):
    now = datetime.now(timezone.utc)

    # Overdue assignments (past due_date, not completed)
    overdue_result = await db.execute(
        select(func.count()).select_from(TrainingAssignment).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.due_date < now,
            TrainingAssignment.completed_at.is_(None),
            TrainingAssignment.deleted_at.is_(None),
        )
    )
    overdue = overdue_result.scalar()

    # Quiz lockouts
    lockout_result = await db.execute(
        select(func.count()).select_from(QuizAttempt).where(
            QuizAttempt.tenant_id == tenant_id,
            QuizAttempt.is_locked == True,
            QuizAttempt.deleted_at.is_(None),
        )
    )
    lockouts = lockout_result.scalar()

    # Total assignments / completed → completion rate
    total_result = await db.execute(
        select(func.count()).select_from(TrainingAssignment).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.deleted_at.is_(None),
        )
    )
    total = total_result.scalar()

    completed_result = await db.execute(
        select(func.count()).select_from(TrainingAssignment).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.completed_at.isnot(None),
            TrainingAssignment.deleted_at.is_(None),
        )
    )
    completed = completed_result.scalar()

    completion_rate = round((completed / total * 100) if total > 0 else 0, 1)

    return {
        "total_employees": 0,  # fetch from auth_service via internal call if needed
        "overdue_assignments": overdue,
        "quiz_lockouts": lockouts,
        "completion_rate": completion_rate,
        "total_assignments": total,
        "completed_assignments": completed,
    }

@router.get("/creator")
async def creator_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant_id),
):
    total_result = await db.execute(
        select(func.count()).select_from(Training).where(
            Training.tenant_id == tenant_id,
            Training.created_by_id == current_user.id,
            Training.deleted_at.is_(None),
        )
    )
    total = total_result.scalar()

    published_result = await db.execute(
        select(func.count()).select_from(Training).where(
            Training.tenant_id == tenant_id,
            Training.created_by_id == current_user.id,
            Training.is_published == True,
            Training.deleted_at.is_(None),
        )
    )
    published = published_result.scalar()

    return {
        "total_trainings": total,
        "published": published,
        "draft": total - published,
    }

@router.get("/employee")
async def employee_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant_id),
):
    now = datetime.now(timezone.utc)
    upcoming_cutoff = now + timedelta(days=7)

    in_progress_result = await db.execute(
        select(TrainingAssignment).where(
            TrainingAssignment.user_id == current_user.id,
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.completed_at.is_(None),
            TrainingAssignment.deleted_at.is_(None),
        ).limit(5)
    )
    in_progress = in_progress_result.scalars().all()

    upcoming_result = await db.execute(
        select(TrainingAssignment).where(
            TrainingAssignment.user_id == current_user.id,
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.due_date.isnot(None),
            TrainingAssignment.due_date <= upcoming_cutoff,
            TrainingAssignment.due_date >= now,
            TrainingAssignment.completed_at.is_(None),
            TrainingAssignment.deleted_at.is_(None),
        )
    )
    upcoming = upcoming_result.scalars().all()

    recent_result = await db.execute(
        select(TrainingAssignment).where(
            TrainingAssignment.user_id == current_user.id,
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.completed_at.isnot(None),
            TrainingAssignment.deleted_at.is_(None),
        ).order_by(TrainingAssignment.completed_at.desc()).limit(5)
    )
    recently_completed = recent_result.scalars().all()

    return {
        "in_progress": [{"training_id": a.training_id, "due_date": a.due_date} for a in in_progress],
        "upcoming_due": [{"training_id": a.training_id, "due_date": a.due_date} for a in upcoming],
        "recently_completed": [{"training_id": a.training_id, "completed_at": a.completed_at} for a in recently_completed],
    }
```

- [ ] **Step 3: Register in `api.py`**

```python
from app.api.v1.endpoints import dashboards
api_router.include_router(dashboards.router, prefix="/dashboards", tags=["dashboards"])
```

- [ ] **Step 4: Run tests**

```bash
docker compose exec core-service pytest tests/api/test_dashboards.py -v
```

- [ ] **Step 5: Add internal reminder query endpoints (required by notification-service scheduler)**

Add these two endpoints to `dashboards.py` for use by Plan 4's scheduler. They are protected by `INTERNAL_API_KEY` header (not JWT):

```python
from fastapi import Header
from app.core.config import settings

@router.get("/assignments-due")
async def assignments_due_for_reminder(
    due_after: str,
    due_before: str,
    x_internal_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403)
    from datetime import datetime
    from sqlalchemy import and_
    from app.models.user import User  # fetched via auth_service join or stored on assignment

    after = datetime.fromisoformat(due_after)
    before = datetime.fromisoformat(due_before)

    result = await db.execute(
        select(TrainingAssignment).where(
            TrainingAssignment.due_date >= after,
            TrainingAssignment.due_date <= before,
            TrainingAssignment.completed_at.is_(None),
            TrainingAssignment.deleted_at.is_(None),
        )
    )
    rows = result.scalars().all()
    return [
        {
            "user_id": r.user_id,
            "tenant_id": r.tenant_id,
            "training_id": r.training_id,
            "training_title": r.training_id,  # join with Training.title if needed
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "user_email": "",  # populated by auth_service lookup if needed
            "completion_lock": r.completion_lock,
        }
        for r in rows
    ]

@router.get("/assignments-overdue")
async def assignments_overdue_for_reminder(
    x_internal_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403)
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(TrainingAssignment).where(
            TrainingAssignment.due_date < now,
            TrainingAssignment.completed_at.is_(None),
            TrainingAssignment.deleted_at.is_(None),
        )
    )
    rows = result.scalars().all()
    return [
        {
            "user_id": r.user_id,
            "tenant_id": r.tenant_id,
            "training_id": r.training_id,
            "training_title": r.training_id,
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "user_email": "",
            "completion_lock": r.completion_lock,
        }
        for r in rows
    ]
```

- [ ] **Step 6: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/dashboards.py app/core_service/app/api/v1/api.py app/core_service/tests/api/test_dashboards.py
git commit -m "feat: add Manager, Creator, Employee dashboard endpoints + internal reminder query endpoints (T-DB-01-09)"
```

---

### Task 10: Add training list filter params and run full test suite

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/trainings.py`

- [ ] **Step 1: Write filter tests**

Add to `tests/api/test_trainings.py`:

```python
# T-CT-03: Filter trainings by category
@pytest.mark.asyncio
async def test_filter_trainings_by_category(client, db_session):
    from app.models.training import Training
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    t1 = Training(id=str(uuid.uuid4()), tenant_id=tenant_id, title="Safety", category="Safety", structure_type="flat", is_published=True, created_by_id=user_id, version=1)
    t2 = Training(id=str(uuid.uuid4()), tenant_id=tenant_id, title="IT", category="IT", structure_type="flat", is_published=True, created_by_id=user_id, version=1)
    db_session.add_all([t1, t2])
    await db_session.commit()

    resp = await client.get("/api/v1/trainings?category=Safety", headers=auth(user_id, tenant_id))
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()]
    assert "Safety" in titles
    assert "IT" not in titles
```

- [ ] **Step 2: Add filter params to the training list endpoint**

In `trainings.py`, find `GET /trainings` and add optional query parameters:

```python
from fastapi import Query as QP

@router.get("")
async def list_trainings(
    category: str | None = QP(default=None),
    tags: list[str] | None = QP(default=None),
    status: str | None = QP(default=None),  # "published", "draft", "archived"
    db: AsyncSession = Depends(get_db),
    ...
):
    query = select(Training).where(Training.tenant_id == tenant_id, Training.deleted_at.is_(None))
    if category:
        query = query.where(Training.category == category)
    if tags:
        # Filter trainings where any of the provided tags overlap
        # For PostgreSQL ARRAY: Training.tags.overlap(tags)
        # For JSON/SQLite fallback: skip or use LIKE
        query = query.where(Training.tags.overlap(tags))
    if status == "published":
        query = query.where(Training.is_published == True)
    elif status == "draft":
        query = query.where(Training.is_published == False, Training.is_archived == False)
    elif status == "archived":
        query = query.where(Training.is_archived == True)
    ...
```

- [ ] **Step 3: Run full core service test suite**

```bash
docker compose exec core-service pytest tests/ -v --tb=short 2>&1 | tail -50
```

Expected: all tests pass.

- [ ] **Step 4: Final commit**

```bash
git add app/core_service/
git commit -m "feat: add category/tags/status filter to training list; full core test suite green"
```
