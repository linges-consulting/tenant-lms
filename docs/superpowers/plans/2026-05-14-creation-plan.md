# Training Creation (Lifecycle, Categories, Ready Gate) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `is_published` boolean with a 4-state lifecycle (`draft → ready → published → archived`), add tenant-managed categories, enforce the Ready gate server-side, and correct role authority so Managers own publish/unpublish/archive while Creators own mark-ready/send-to-draft.

**Architecture:** Add `is_ready` boolean to `trainings` table (avoids touching the existing `is_published` column that many queries already reference). Derive `lifecycle_status` from `is_ready`/`is_published`/`is_archived` in the Pydantic schema. Introduce a `TrainingCategory` model and a `completion_mode` column on `chapters`. Wire new state-transition endpoints and fix role guards. Update frontend editor and manager list.

**Tech Stack:** FastAPI (async SQLAlchemy), Alembic, Pydantic v2, React + TypeScript, TanStack React Query, shadcn/ui, lucide-react, sonner toasts.

**Run tests:** `docker compose exec core-service pytest tests/ -v`
**Lint frontend:** `cd app/frontend && npm run lint`

---

## File Map

**Backend — new/changed:**
- `app/core_service/app/models/training.py` — add `is_ready` field
- `app/core_service/app/models/chapter.py` — add `completion_mode` field
- `app/core_service/app/models/category.py` — new `TrainingCategory` model
- `app/core_service/app/models/__init__.py` — import `TrainingCategory`
- `app/core_service/app/schemas/training.py` — add `lifecycle_status` derived property; add `is_ready` to `TrainingBase`
- `app/core_service/app/schemas/chapter.py` — add `completion_mode`
- `app/core_service/app/schemas/category.py` — new file: `Category`, `CategoryCreate`, `CategoryUpdate`
- `app/core_service/app/api/v1/endpoints/trainings.py` — add `mark-ready`, `send-to-draft`; fix `publish`, `unpublish`, `archive`, `get_training_structure`
- `app/core_service/app/api/v1/endpoints/categories.py` — new file: CRUD for tenant categories
- `app/core_service/app/api/v1/api.py` — register categories router
- `app/core_service/alembic/versions/<hash>_add_training_lifecycle_fields.py` — new migration

**Frontend — new/changed:**
- `app/frontend/src/api/trainings.ts` — add `lifecycle_status`, `is_ready`, `completion_mode` to types; add `markReady`, `sendToDraft`, `categories` API calls
- `app/frontend/src/pages/ManagerTrainingEditor.tsx` — remove Publish button, add Mark Ready / Send to Draft; category dropdown; completion mode toggle
- `app/frontend/src/pages/ManagerTrainings.tsx` — add Publish / Unpublish / Archive action buttons per training

**Tests:**
- `app/core_service/tests/api/test_trainings.py` — add tests for new endpoints and role guards

---

## Task 1: DB migration — add `is_ready`, `completion_mode`, `training_categories`

**Files:**
- Create: `app/core_service/alembic/versions/b8c9d0e1f2a3_add_training_lifecycle_fields.py`

- [ ] **Step 1: Generate the migration file**

```bash
cd app/core_service
alembic revision --autogenerate -m "add_training_lifecycle_fields"
```

Expected: new file created in `alembic/versions/`. Rename it to `b8c9d0e1f2a3_add_training_lifecycle_fields.py` if the hash differs — the name is just for clarity.

- [ ] **Step 2: Write the migration body**

Replace the generated `upgrade()` and `downgrade()` with:

```python
def upgrade() -> None:
    op.add_column('trainings', sa.Column('is_ready', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('chapters', sa.Column('completion_mode', sa.String(length=20), nullable=False, server_default='can_continue'))
    op.create_table(
        'training_categories',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(), nullable=False, index=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_training_categories_tenant_name'),
    )

def downgrade() -> None:
    op.drop_table('training_categories')
    op.drop_column('chapters', 'completion_mode')
    op.drop_column('trainings', 'is_ready')
```

- [ ] **Step 3: Apply the migration**

```bash
cd app/core_service
alembic upgrade head
```

Expected: `Running upgrade ... -> b8c9d0e1f2a3` with no errors.

- [ ] **Step 4: Verify columns exist**

```bash
docker compose exec postgres psql -U lms_user -d lms_db -c "\d trainings" | grep is_ready
docker compose exec postgres psql -U lms_user -d lms_db -c "\d chapters" | grep completion_mode
docker compose exec postgres psql -U lms_user -d lms_db -c "\dt training_categories"
```

Expected: each command returns a non-empty result.

- [ ] **Step 5: Commit**

```bash
git add app/core_service/alembic/versions/b8c9d0e1f2a3_add_training_lifecycle_fields.py
git commit -m "feat: migration — add is_ready, completion_mode, training_categories"
```

---

## Task 2: ORM models — Training, Chapter, TrainingCategory

**Files:**
- Modify: `app/core_service/app/models/training.py`
- Modify: `app/core_service/app/models/chapter.py`
- Create: `app/core_service/app/models/category.py`
- Modify: `app/core_service/app/models/__init__.py`

- [ ] **Step 1: Add `is_ready` to Training model**

In `app/core_service/app/models/training.py`, after the `is_archived` line add:

```python
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
```

- [ ] **Step 2: Add `completion_mode` to Chapter model**

In `app/core_service/app/models/chapter.py`, after the `sequence_order` line add:

```python
    completion_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="can_continue", server_default="can_continue")
```

- [ ] **Step 3: Create TrainingCategory model**

Create `app/core_service/app/models/category.py`:

```python
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base_class import Base

class TrainingCategory(Base):
    __tablename__ = "training_categories"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: Register model in `__init__.py`**

In `app/core_service/app/models/__init__.py`, add:

```python
from app.models.category import TrainingCategory
```

- [ ] **Step 5: Restart core service and verify no import errors**

```bash
docker compose restart core-service
docker compose logs core-service --tail=20
```

Expected: no `ImportError` or `AttributeError` lines; service starts on port 8000.

- [ ] **Step 6: Commit**

```bash
git add app/core_service/app/models/training.py app/core_service/app/models/chapter.py app/core_service/app/models/category.py app/core_service/app/models/__init__.py
git commit -m "feat: add is_ready to Training, completion_mode to Chapter, TrainingCategory model"
```

---

## Task 3: Pydantic schemas — lifecycle_status, completion_mode, Category

**Files:**
- Modify: `app/core_service/app/schemas/training.py`
- Modify: `app/core_service/app/schemas/chapter.py`
- Create: `app/core_service/app/schemas/category.py`

- [ ] **Step 1: Write failing test for lifecycle_status derivation**

In `app/core_service/tests/api/test_trainings.py`, add at top of file (or in a new test section):

```python
def test_lifecycle_status_draft():
    from app.schemas.training import Training as TrainingSchema
    t = TrainingSchema(
        id="x", tenant_id="t", title="T", category="C",
        is_published=False, is_archived=False, is_ready=False,
        tags=[], collaborators=[]
    )
    assert t.lifecycle_status == "draft"

def test_lifecycle_status_ready():
    from app.schemas.training import Training as TrainingSchema
    t = TrainingSchema(
        id="x", tenant_id="t", title="T", category="C",
        is_published=False, is_archived=False, is_ready=True,
        tags=[], collaborators=[]
    )
    assert t.lifecycle_status == "ready"

def test_lifecycle_status_published():
    from app.schemas.training import Training as TrainingSchema
    t = TrainingSchema(
        id="x", tenant_id="t", title="T", category="C",
        is_published=True, is_archived=False, is_ready=True,
        tags=[], collaborators=[]
    )
    assert t.lifecycle_status == "published"

def test_lifecycle_status_archived():
    from app.schemas.training import Training as TrainingSchema
    t = TrainingSchema(
        id="x", tenant_id="t", title="T", category="C",
        is_published=False, is_archived=True, is_ready=False,
        tags=[], collaborators=[]
    )
    assert t.lifecycle_status == "archived"
```

- [ ] **Step 2: Run tests — expect failure**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_lifecycle_status_draft -v
```

Expected: `FAILED` with `ValidationError` (field `is_ready` not on schema).

- [ ] **Step 3: Update `TrainingBase` and `Training` schemas**

In `app/core_service/app/schemas/training.py`:

Add `is_ready: Optional[bool] = False` to `TrainingBase` (after `is_archived`):

```python
class TrainingBase(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    duration: Optional[str] = None
    thumbnail: Optional[str] = None
    version: Optional[int] = 1
    is_published: Optional[bool] = False
    is_ready: Optional[bool] = False
    requires_certificate: Optional[bool] = True
    template_id: Optional[str] = None
    is_archived: Optional[bool] = False
    is_active: Optional[bool] = True
```

Add `lifecycle_status` computed property to `Training` schema (after `certificate_id`):

```python
class Training(TrainingInDBBase):
    created_by_id: Optional[str] = None
    creator_name: Optional[str] = None
    collaborators: List[TrainingCollaborator] = []

    progress_percentage: float = 0.0
    completed_chapters: int = 0
    total_chapters: int = 0
    status: str = "not_started"
    certificate_id: Optional[str] = None

    @property
    def lifecycle_status(self) -> str:
        if self.is_archived:
            return "archived"
        if self.is_published:
            return "published"
        if self.is_ready:
            return "ready"
        return "draft"

    model_config = ConfigDict(from_attributes=True)
```

Note: Pydantic v2 properties don't auto-serialize. Add `lifecycle_status` as a `computed_field` instead:

```python
from pydantic import BaseModel, ConfigDict, model_validator, field_validator, computed_field

class Training(TrainingInDBBase):
    created_by_id: Optional[str] = None
    creator_name: Optional[str] = None
    collaborators: List[TrainingCollaborator] = []

    progress_percentage: float = 0.0
    completed_chapters: int = 0
    total_chapters: int = 0
    status: str = "not_started"
    certificate_id: Optional[str] = None

    @computed_field
    @property
    def lifecycle_status(self) -> str:
        if self.is_archived:
            return "archived"
        if self.is_published:
            return "published"
        if self.is_ready:
            return "ready"
        return "draft"
```

Also update the import at the top of `training.py`:
```python
from pydantic import BaseModel, ConfigDict, model_validator, field_validator, computed_field
```

- [ ] **Step 4: Add `completion_mode` to Chapter schema**

In `app/core_service/app/schemas/chapter.py`, update `ChapterBase`:

```python
class ChapterBase(BaseModel):
    title: Optional[str] = None
    content_type: Optional[ContentType] = None
    content_data: Optional[dict] = None
    sequence_order: Optional[int] = None
    module_id: Optional[str] = None
    completion_mode: Optional[str] = "can_continue"
```

And update `Chapter` (return schema):

```python
class Chapter(ChapterInDBBase):
    is_completed: bool = False
    completion_mode: str = "can_continue"
```

- [ ] **Step 5: Create Category schemas**

Create `app/core_service/app/schemas/category.py`:

```python
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class CategoryBase(BaseModel):
    name: str

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: str

class Category(CategoryBase):
    id: str
    tenant_id: str
    is_active: bool
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 6: Run tests — expect pass**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_lifecycle_status_draft tests/api/test_trainings.py::test_lifecycle_status_ready tests/api/test_trainings.py::test_lifecycle_status_published tests/api/test_trainings.py::test_lifecycle_status_archived -v
```

Expected: 4 PASSED.

- [ ] **Step 7: Commit**

```bash
git add app/core_service/app/schemas/training.py app/core_service/app/schemas/chapter.py app/core_service/app/schemas/category.py app/core_service/tests/api/test_trainings.py
git commit -m "feat: add lifecycle_status computed field, completion_mode to chapter schema, Category schemas"
```

---

## Task 4: Category endpoints (CRUD, tenant-scoped)

**Files:**
- Create: `app/core_service/app/api/v1/endpoints/categories.py`
- Modify: `app/core_service/app/api/v1/api.py`

- [ ] **Step 1: Write failing test for list categories**

In `app/core_service/tests/api/test_trainings.py` add:

```python
async def test_list_categories_returns_tenant_categories(async_client, manager_headers, test_tenant_id):
    # Create a category first
    resp = await async_client.post(
        "/api/v1/categories",
        json={"name": "Safety"},
        headers=manager_headers
    )
    assert resp.status_code == 201

    resp2 = await async_client.get("/api/v1/categories", headers=manager_headers)
    assert resp2.status_code == 200
    names = [c["name"] for c in resp2.json()]
    assert "Safety" in names
```

- [ ] **Step 2: Run test — expect 404 (route not found)**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_list_categories_returns_tenant_categories -v
```

Expected: FAILED — `404` because the route doesn't exist yet.

- [ ] **Step 3: Create the categories endpoint file**

Create `app/core_service/app/api/v1/endpoints/categories.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.api import deps
from app.db.session import get_db
from app.models.category import TrainingCategory
from app.schemas.category import Category, CategoryCreate, CategoryUpdate

router = APIRouter()


@router.get("", response_model=List[Category])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """List all active categories for the current tenant. Creator + Manager."""
    result = await db.execute(
        select(TrainingCategory)
        .where(TrainingCategory.tenant_id == tenant_id, TrainingCategory.is_active == True)
        .order_by(TrainingCategory.name)
    )
    return result.scalars().all()


@router.post("", response_model=Category, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """Create a new category for this tenant. Manager only."""
    existing = await db.execute(
        select(TrainingCategory).where(
            TrainingCategory.tenant_id == tenant_id,
            TrainingCategory.name == data.name,
            TrainingCategory.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Category with this name already exists")

    cat = TrainingCategory(id=str(uuid.uuid4()), tenant_id=tenant_id, name=data.name)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@router.put("/{category_id}", response_model=Category)
async def update_category(
    category_id: str,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """Update a category name. Manager only."""
    result = await db.execute(
        select(TrainingCategory).where(
            TrainingCategory.id == category_id, TrainingCategory.tenant_id == tenant_id
        )
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.name = data.name
    await db.commit()
    await db.refresh(cat)
    return cat


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """Soft-delete a category. Manager only."""
    result = await db.execute(
        select(TrainingCategory).where(
            TrainingCategory.id == category_id, TrainingCategory.tenant_id == tenant_id
        )
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.is_active = False
    await db.commit()
    return None
```

- [ ] **Step 4: Register the categories router in `api.py`**

In `app/core_service/app/api/v1/api.py`:

```python
from fastapi import APIRouter
from app.api.v1.endpoints import trainings, users, certificates, progress, dashboards, categories

api_router = APIRouter()
api_router.include_router(trainings.router, prefix="/trainings", tags=["trainings"])
api_router.include_router(users.router, prefix="/user-report", tags=["user-report"])
api_router.include_router(certificates.router, prefix="/certificates", tags=["certificates"])
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])
api_router.include_router(dashboards.router, prefix="/dashboards", tags=["dashboards"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
```

- [ ] **Step 5: Restart and run test**

```bash
docker compose restart core-service
docker compose exec core-service pytest tests/api/test_trainings.py::test_list_categories_returns_tenant_categories -v
```

Expected: PASSED.

- [ ] **Step 6: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/categories.py app/core_service/app/api/v1/api.py
git commit -m "feat: category CRUD endpoints (tenant-scoped, Manager-managed)"
```

---

## Task 5: `mark-ready` endpoint (Creator owner only, enforces Ready gate)

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/trainings.py`

- [ ] **Step 1: Write failing test**

```python
async def test_mark_ready_enforces_gate(async_client, creator_headers, test_training_id_no_chapters):
    """mark-ready should 400 if training has no chapters."""
    resp = await async_client.post(
        f"/api/v1/trainings/{test_training_id_no_chapters}/mark-ready",
        headers=creator_headers
    )
    assert resp.status_code == 400
    assert "chapter" in resp.json()["detail"].lower()

async def test_mark_ready_success(async_client, creator_headers, test_training_id_with_chapter):
    resp = await async_client.post(
        f"/api/v1/trainings/{test_training_id_with_chapter}/mark-ready",
        headers=creator_headers
    )
    assert resp.status_code == 200
    assert resp.json()["lifecycle_status"] == "ready"
    assert resp.json()["is_ready"] is True
```

- [ ] **Step 2: Run tests — expect 404**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_mark_ready_enforces_gate -v
```

Expected: FAILED (404 route not found).

- [ ] **Step 3: Add `mark-ready` endpoint**

In `app/core_service/app/api/v1/endpoints/trainings.py`, after the `archive_training` endpoint (around line 804), add:

```python
@router.post("/{training_id}/mark-ready", response_model=TrainingSchema)
async def mark_training_ready(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Creator (owner) marks training as Ready. Enforces Ready gate (BR-305a).
    Draft → Ready transition only. Locks editing.
    """
    result = await db.execute(
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id, Training.deleted_at == None)
        .options(selectinload(Training.collaborators))
    )
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    if not await is_owner_or_admin(training, current_user):
        raise HTTPException(status_code=403, detail="Only the owner can mark a training as Ready")

    if training.is_published or training.is_archived:
        raise HTTPException(status_code=400, detail="Only draft trainings can be marked as Ready")

    if training.is_ready:
        raise HTTPException(status_code=400, detail="Training is already in Ready state")

    # Ready gate (BR-305a): title, description, category, at least one chapter
    if not training.title or not training.title.strip():
        raise HTTPException(status_code=400, detail="Training must have a title before marking Ready")
    if not training.description or not training.description.strip():
        raise HTTPException(status_code=400, detail="Training must have a description before marking Ready")
    if not training.category or not training.category.strip():
        raise HTTPException(status_code=400, detail="Training must have a category before marking Ready")

    chapter_count = await db.scalar(
        select(func.count(Chapter.id)).where(Chapter.training_id == training_id)
    )
    if not chapter_count or chapter_count < 1:
        raise HTTPException(status_code=400, detail="Training must have at least one chapter before marking Ready")

    training.is_ready = True
    await log_audit(db, tenant_id, current_user.id, "training_marked_ready", "training", training_id,
                    {"title": training.title})
    await db.commit()
    await db.refresh(training)
    await invalidate_cache("training_detail", training_id)
    return training
```

- [ ] **Step 4: Run tests — expect pass**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_mark_ready_enforces_gate tests/api/test_trainings.py::test_mark_ready_success -v
```

Expected: PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/trainings.py
git commit -m "feat: mark-ready endpoint with BR-305a Ready gate"
```

---

## Task 6: `send-to-draft` endpoint (Creator or Manager)

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/trainings.py`

- [ ] **Step 1: Write failing test**

```python
async def test_send_to_draft_from_ready(async_client, creator_headers, test_training_id_ready):
    resp = await async_client.post(
        f"/api/v1/trainings/{test_training_id_ready}/send-to-draft",
        headers=creator_headers
    )
    assert resp.status_code == 200
    assert resp.json()["lifecycle_status"] == "draft"
    assert resp.json()["is_ready"] is False

async def test_send_to_draft_from_published_requires_manager(async_client, creator_headers, test_training_id_published):
    """Only Manager (not Creator) can send a Published training back to Draft."""
    resp = await async_client.post(
        f"/api/v1/trainings/{test_training_id_published}/send-to-draft",
        headers=creator_headers
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run test — expect 404**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_send_to_draft_from_ready -v
```

Expected: FAILED (404).

- [ ] **Step 3: Add `send-to-draft` endpoint**

In `trainings.py`, after `mark_training_ready`:

```python
@router.post("/{training_id}/send-to-draft", response_model=TrainingSchema)
async def send_training_to_draft(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Return a Ready or Published training to Draft state.
    Ready → Draft: Creator (owner) OR Manager.
    Published → Draft (Unpublish): Manager only — resets all learner progress (BR-301a).
    """
    result = await db.execute(
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id, Training.deleted_at == None)
        .options(selectinload(Training.collaborators))
        .with_for_update()
    )
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    if training.is_archived:
        raise HTTPException(status_code=400, detail="Archived trainings cannot be returned to Draft")

    if not training.is_ready and not training.is_published:
        raise HTTPException(status_code=400, detail="Training is already in Draft state")

    is_manager = any(role in ["Business Manager", "Admin", "SysAdmin"] for role in current_user.roles)
    is_owner = await is_owner_or_admin(training, current_user)

    if training.is_published:
        # Published → Draft requires Manager
        if not is_manager:
            raise HTTPException(status_code=403, detail="Only a Business Manager can unpublish a training")
        # Reset all learner progress for this training
        now = datetime.now(timezone.utc)
        progress_rows_result = await db.execute(
            select(UserProgress)
            .where(UserProgress.training_id == training_id, UserProgress.deleted_at.is_(None))
        )
        for row in progress_rows_result.scalars().all():
            row.deleted_at = now
        # Reset enrollments
        enroll_rows_result = await db.execute(
            select(Enrollment)
            .where(Enrollment.training_id == training_id, Enrollment.deleted_at.is_(None))
        )
        for enr in enroll_rows_result.scalars().all():
            enr.is_completed = False
            enr.completed_at = None
        await log_audit(db, tenant_id, current_user.id, "training_unpublished", "training", training_id,
                        {"title": training.title})
    else:
        # Ready → Draft: Owner or Manager
        if not is_owner and not is_manager:
            raise HTTPException(status_code=403, detail="Only the owner or a Business Manager can return a Ready training to Draft")
        await log_audit(db, tenant_id, current_user.id, "training_sent_to_draft", "training", training_id,
                        {"title": training.title})

    training.is_published = False
    training.is_ready = False
    await db.commit()
    await db.refresh(training)
    await invalidate_cache("training_detail", training_id)
    await invalidate_cache("training_structure", training_id)
    await invalidate_cache("assigned_trainings", tenant_id)
    return training
```

- [ ] **Step 4: Run tests — expect pass**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_send_to_draft_from_ready -v
```

Expected: PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/trainings.py
git commit -m "feat: send-to-draft endpoint (Ready→Draft for Creator/Manager, Published→Draft for Manager only)"
```

---

## Task 7: Fix `publish` and `archive` endpoints — Manager-only authority

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/trainings.py`

- [ ] **Step 1: Write failing test for publish role guard**

```python
async def test_publish_requires_manager_not_creator(async_client, creator_headers, test_training_id_ready):
    """Creator cannot publish — only Manager can."""
    resp = await async_client.post(
        f"/api/v1/trainings/{test_training_id_ready}/publish",
        headers=creator_headers
    )
    assert resp.status_code == 403

async def test_publish_requires_ready_state(async_client, manager_headers, test_training_id_draft):
    """Cannot publish a Draft (must be Ready first)."""
    resp = await async_client.post(
        f"/api/v1/trainings/{test_training_id_draft}/publish",
        headers=manager_headers
    )
    assert resp.status_code == 400
    assert "ready" in resp.json()["detail"].lower()
```

- [ ] **Step 2: Run — expect 200 (currently wrong)**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_publish_requires_manager_not_creator -v
```

Expected: FAILED (currently returns 200 because creator can publish).

- [ ] **Step 3: Fix `publish_training` endpoint**

Find the `publish_training` function (around line 856). Change:
1. The dep from `deps.get_training_creator` to `deps.get_business_manager`
2. Remove the `is_owner_or_admin` check (Managers don't need to be owners)
3. Add a check that training must be in `is_ready=True` state before publishing

```python
@router.post("/{training_id}/publish", response_model=TrainingSchema)
async def publish_training(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),  # Manager only
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Publish a Ready training. Manager only (BR-301a).
    Writes version snapshot. Learners gain access.
    """
    result = await db.execute(
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id)
        .options(selectinload(Training.collaborators))
        .with_for_update()
    )
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    if training.is_archived:
        raise HTTPException(status_code=400, detail="Archived trainings cannot be published")

    if not training.is_ready and not training.is_published:
        raise HTTPException(
            status_code=400,
            detail="Training must be in Ready state before publishing. Ask the creator to mark it as Ready first."
        )
    # (rest of the existing publish logic continues unchanged)
```

Keep the existing version snapshot / progress reset / notification logic below this guard unchanged.

Also update the audit action string from `"PUBLISH_TRAINING"` to `"training_published"` (for consistent naming with new endpoints):

Find `await log_audit(db, tenant_id, current_user.id, "PUBLISH_TRAINING"` and change to:
```python
await log_audit(db, tenant_id, current_user.id, "training_published", "training", training_id,
                {"title": training.title, "version": training.version})
```

- [ ] **Step 4: Fix `archive_training` endpoint**

Find `archive_training` (around line 773). Change:
1. Dep from `deps.get_training_creator` to `deps.get_business_manager`
2. Remove the `is_owner_or_admin` check
3. Add archive gate: all learners completed OR all due dates passed (BR-503)

```python
@router.post("/{training_id}/archive", response_model=dict)
async def archive_training(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),  # Manager only
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Archive a Published training. Manager only (BR-301a, BR-503).
    Gate: all assigned learners completed OR all assignment due dates passed.
    """
    stmt = select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id)
    result = await db.execute(stmt)
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    if not training.is_published:
        raise HTTPException(status_code=400, detail="Only Published trainings can be archived")

    # Archive gate (BR-503)
    now = datetime.now(timezone.utc)
    assignments_result = await db.execute(
        select(TrainingAssignment).where(TrainingAssignment.training_id == training_id)
    )
    assignments = assignments_result.scalars().all()

    if assignments:
        all_due_passed = all(
            (a.due_date is not None and a.due_date < now) for a in assignments
        )
        if not all_due_passed:
            # Check if all learners completed
            user_ids_with_assignments = [a.user_id for a in assignments if a.user_id]
            if user_ids_with_assignments:
                incomplete_result = await db.execute(
                    select(func.count(Enrollment.id)).where(
                        Enrollment.training_id == training_id,
                        Enrollment.user_id.in_(user_ids_with_assignments),
                        Enrollment.is_completed == False,
                        Enrollment.deleted_at.is_(None),
                    )
                )
                incomplete_count = incomplete_result.scalar() or 0
                if incomplete_count > 0:
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot archive: some learners have not completed the training and due dates have not passed."
                    )

    training.is_archived = True
    training.is_active = False
    await log_audit(db, tenant_id, current_user.id, "training_archived", "training", training_id,
                    {"title": training.title})
    await db.commit()
    await invalidate_cache("assigned_trainings", tenant_id)
    await invalidate_cache("training_detail", training_id)
    return {"status": "success", "message": "Training archived successfully"}
```

- [ ] **Step 5: Run tests**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_publish_requires_manager_not_creator tests/api/test_trainings.py::test_publish_requires_ready_state -v
```

Expected: PASSED.

- [ ] **Step 6: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/trainings.py
git commit -m "fix: publish/archive require Manager role; publish requires Ready state; archive gate enforced"
```

---

## Task 8: Fix `get_training_structure` — include all Training fields

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/trainings.py`

**Problem:** Around line 1668, `TrainingStructure(...)` is constructed with only a handful of fields. Fields like `tags`, `category`, `requires_certificate`, `template_id`, `collaborators`, `is_ready`, `is_archived` default to Pydantic defaults — so the editor form resets on save.

- [ ] **Step 1: Write failing test**

```python
async def test_structure_includes_all_training_fields(async_client, creator_headers, test_training_id_with_tags):
    """Structure endpoint must return tags, category, is_ready, etc."""
    resp = await async_client.get(
        f"/api/v1/trainings/{test_training_id_with_tags}/structure",
        headers=creator_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tags"] != []
    assert data["category"] is not None
    assert "is_ready" in data
```

- [ ] **Step 2: Run — expect fail (tags is [])**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_structure_includes_all_training_fields -v
```

Expected: FAILED.

- [ ] **Step 3: Fix `get_training_structure` return statement**

Find the `return TrainingStructure(...)` call (around line 1668). Replace the manually-constructed object with one that derives from the `training` ORM object:

```python
    structure_schema = TrainingStructure.model_validate(training)
    structure_schema.modules = modules_out
    structure_schema.orphan_chapters = standalone_chaps
    structure_schema.total_chapters = len(chapters)
    structure_schema.status = (
        "completed" if (enroll and enroll.is_completed)
        else "in_progress" if enroll
        else "not_started"
    )
    structure_schema.certificate_id = enroll.certificate_id if enroll else None
    return structure_schema
```

Also ensure the `training` ORM object is loaded with `.options(selectinload(Training.collaborators))` in the structure query (add it if missing):

```python
    stmt = select(Training).where(
        Training.id == training_id,
        Training.tenant_id == tenant_id,
        Training.deleted_at == None
    ).options(selectinload(Training.collaborators))
```

- [ ] **Step 4: Run test — expect pass**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_structure_includes_all_training_fields -v
```

Expected: PASSED.

- [ ] **Step 5: Run full test suite**

```bash
docker compose exec core-service pytest tests/ -v
```

Expected: all tests pass (or pre-existing failures only — no regressions).

- [ ] **Step 6: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/trainings.py
git commit -m "fix: structure endpoint returns all Training fields via model_validate instead of manual construction"
```

---

## Task 9: Frontend API types and helper functions

**Files:**
- Modify: `app/frontend/src/api/trainings.ts`

- [ ] **Step 1: Add `lifecycle_status`, `is_ready`, `completion_mode` to types**

In `app/frontend/src/api/trainings.ts`, update the `Training` interface:

```typescript
export interface Training {
    id: string;
    title: string;
    description?: string;
    category?: string;
    duration?: string;
    thumbnail?: string;
    version: number;
    is_published: boolean;
    is_ready: boolean;
    is_archived?: boolean;
    lifecycle_status: 'draft' | 'ready' | 'published' | 'archived';
    requires_certificate: boolean;
    template_id?: string;
    tenant_id: string;
    created_by_id?: string;
    creator_name?: string;
    progress_percentage?: number;
    completed_chapters?: number;
    total_chapters?: number;
    status?: 'assigned' | 'in_progress' | 'completed' | 'expired';
    certificate_id?: string;
    tags: string[];
    collaborators: TrainingCollaborator[];
}
```

Update the `Chapter` interface to add `completion_mode`:

```typescript
export interface Chapter {
    id: string;
    title: string;
    content_type: string;
    content_data: any;
    sequence_order: number;
    module_id?: string;
    is_completed?: boolean;
    video_url?: string;
    content?: string;
    attempts_count?: number;
    completion_mode?: 'can_continue' | 'must_watch_full';
}
```

Add `Category` interface:

```typescript
export interface TrainingCategory {
    id: string;
    name: string;
    tenant_id: string;
    is_active: boolean;
}
```

- [ ] **Step 2: Add API calls to `managerTrainingsApi`**

In `managerTrainingsApi`, add:

```typescript
    markReady: (id: string) =>
        apiClient.post<Training>(`/trainings/${id}/mark-ready`),

    sendToDraft: (id: string) =>
        apiClient.post<Training>(`/trainings/${id}/send-to-draft`),

    getCategories: () =>
        apiClient.get<TrainingCategory[]>('/categories'),

    createCategory: (name: string) =>
        apiClient.post<TrainingCategory>('/categories', { name }),
```

- [ ] **Step 3: Lint check**

```bash
cd app/frontend && npm run lint
```

Expected: zero errors.

- [ ] **Step 4: Commit**

```bash
git add app/frontend/src/api/trainings.ts
git commit -m "feat: add lifecycle_status, is_ready, completion_mode types and markReady/sendToDraft/category API calls"
```

---

## Task 10: Frontend editor — lifecycle-aware buttons, category dropdown, completion mode

**Files:**
- Modify: `app/frontend/src/pages/ManagerTrainingEditor.tsx`

- [ ] **Step 1: Replace Publish button with Mark Ready / Send to Draft**

Find the Publish button in `ManagerTrainingEditor.tsx`. Replace the publish/unpublish block with:

```tsx
{/* Lifecycle actions — role-aware */}
{training?.lifecycle_status === 'draft' && isOwner && (
    <Button
        size="sm"
        onClick={handleMarkReady}
        disabled={isSaving}
    >
        Mark as Ready
    </Button>
)}
{training?.lifecycle_status === 'ready' && (isOwner || isManager) && (
    <Button
        size="sm"
        variant="outline"
        onClick={handleSendToDraft}
        disabled={isSaving}
    >
        Return to Draft
    </Button>
)}
```

Where `isOwner = training?.created_by_id === currentUser?.id` and `isManager = currentUser?.roles?.includes('Business Manager')`.

Add handlers:

```tsx
const handleMarkReady = async () => {
    if (!id) return;
    try {
        const updated = await managerTrainingsApi.markReady(id);
        setTraining(updated);
        toast.success('Training marked as Ready');
    } catch {
        toast.error('Failed to mark as Ready. Ensure title, description, category, and at least one chapter are set.');
    }
};

const handleSendToDraft = async () => {
    if (!id) return;
    try {
        const updated = await managerTrainingsApi.sendToDraft(id);
        setTraining(updated);
        toast.success('Training returned to Draft');
    } catch {
        toast.error('Failed to return to Draft');
    }
};
```

- [ ] **Step 2: Add lifecycle status badge to editor header**

In the editor header area, add a badge reflecting `training.lifecycle_status`:

```tsx
{training && (
    <Badge variant={
        training.lifecycle_status === 'published' ? 'default' :
        training.lifecycle_status === 'ready' ? 'secondary' :
        training.lifecycle_status === 'archived' ? 'destructive' : 'outline'
    }>
        {training.lifecycle_status.charAt(0).toUpperCase() + training.lifecycle_status.slice(1)}
    </Badge>
)}
```

- [ ] **Step 3: Add category dropdown to metadata form**

Add state: `const [categories, setCategories] = useState<TrainingCategory[]>([])`

Fetch in the existing `fetchStructure` / `useEffect`:
```tsx
const cats = await managerTrainingsApi.getCategories();
setCategories(cats);
```

Replace the category text input with a `<Select>`:

```tsx
<div className="space-y-1">
    <Label className="text-xs">Category *</Label>
    <Select value={category} onValueChange={setCategory}>
        <SelectTrigger className="h-8 text-sm">
            <SelectValue placeholder="Select category" />
        </SelectTrigger>
        <SelectContent>
            {categories.map(c => (
                <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>
            ))}
        </SelectContent>
    </Select>
</div>
```

Import `Select`, `SelectTrigger`, `SelectValue`, `SelectContent`, `SelectItem` from `'../components/ui/select'` and `TrainingCategory` from `'../api/trainings'`.

- [ ] **Step 4: Add completion mode toggle in video chapter form**

When a chapter with `content_type === 'VIDEO'` is being created/edited, show a toggle:

```tsx
{chapterContentType === 'VIDEO' && (
    <div className="space-y-1">
        <Label className="text-xs">Video Completion Mode</Label>
        <Select
            value={completionMode}
            onValueChange={(v) => setCompletionMode(v as 'can_continue' | 'must_watch_full')}
        >
            <SelectTrigger className="h-8 text-sm">
                <SelectValue />
            </SelectTrigger>
            <SelectContent>
                <SelectItem value="can_continue">Can Continue (button enabled immediately)</SelectItem>
                <SelectItem value="must_watch_full">Must Watch Full (button locked until 100%)</SelectItem>
            </SelectContent>
        </Select>
    </div>
)}
```

Add state: `const [completionMode, setCompletionMode] = useState<'can_continue' | 'must_watch_full'>('can_continue')`

Include `completion_mode` in the chapter create/update payload:
```tsx
content_data: { ...chapterContentData },
// add alongside other chapter fields:
completion_mode: completionMode,
```

Update `createChapter` / `updateChapter` API signatures in `trainings.ts` to accept `completion_mode?: string` in the data object.

- [ ] **Step 5: Lint check**

```bash
cd app/frontend && npm run lint
```

Expected: zero errors.

- [ ] **Step 6: Commit**

```bash
git add app/frontend/src/pages/ManagerTrainingEditor.tsx
git commit -m "feat: editor — Mark Ready/Send to Draft, lifecycle badge, category dropdown, video completion mode toggle"
```

---

## Task 11: Frontend manager list — Publish / Unpublish / Archive actions

**Files:**
- Modify: `app/frontend/src/pages/ManagerTrainings.tsx`

- [ ] **Step 1: Add Publish button for Ready trainings**

In the training card / row action menu in `ManagerTrainings.tsx`, add:

```tsx
{t.lifecycle_status === 'ready' && isManager && (
    <Button size="sm" onClick={() => handlePublish(t.id)}>
        Publish
    </Button>
)}
{t.lifecycle_status === 'published' && isManager && (
    <>
        <Button size="sm" variant="outline" onClick={() => handleUnpublish(t.id)}>
            Unpublish
        </Button>
        <Button size="sm" variant="ghost" onClick={() => handleArchive(t.id)}>
            Archive
        </Button>
    </>
)}
```

Add handlers (reuse `managerTrainingsApi.publishTraining` / `unpublishTraining` / `archiveTraining`):

```tsx
const handlePublish = async (trainingId: string) => {
    try {
        await managerTrainingsApi.publishTraining(trainingId);
        toast.success('Training published');
        refetch();
    } catch {
        toast.error('Failed to publish training');
    }
};

const handleUnpublish = async (trainingId: string) => {
    try {
        await managerTrainingsApi.unpublishTraining(trainingId);
        toast.success('Training unpublished. Learner progress has been reset.');
        refetch();
    } catch {
        toast.error('Failed to unpublish training');
    }
};

const handleArchive = async (trainingId: string) => {
    const confirmed = window.confirm(
        'Archive this training? All learner access will be closed. This cannot be undone unless you unpublish.'
    );
    if (!confirmed) return;
    try {
        await managerTrainingsApi.archiveTraining(trainingId);
        toast.success('Training archived');
        refetch();
    } catch (err: unknown) {
        const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        toast.error(msg || 'Failed to archive training');
    }
};
```

Where `unpublishTraining` now calls `POST /trainings/{id}/send-to-draft`. Update `managerTrainingsApi.unpublishTraining` in `trainings.ts` to call `/trainings/${id}/send-to-draft` instead of the old unpublish path (or add a new `sendToDraft` call).

- [ ] **Step 2: Update status filter to support `ready` state**

In the status filter dropdown, add the "Ready" option:

```tsx
<SelectItem value="ready">Ready</SelectItem>
```

Update the filter logic passed to the API:

```tsx
getManagerTrainings: (filters?: { category?: string; status?: string; tags?: string[] }) =>
    apiClient.get<Training[]>('/trainings/manager', { params: filters as Record<string, string> | undefined }),
```

And in the backend, ensure the `read_trainings_manager` endpoint supports `status=ready`:

```python
elif status == "ready":
    stmt = stmt.where(Training.is_ready.is_(True), Training.is_published.is_(False), Training.is_archived.is_(False))
```

Add this branch in `app/core_service/app/api/v1/endpoints/trainings.py` in the `read_trainings_manager` function.

- [ ] **Step 3: Lint check**

```bash
cd app/frontend && npm run lint
```

Expected: zero errors.

- [ ] **Step 4: Commit**

```bash
git add app/frontend/src/pages/ManagerTrainings.tsx app/core_service/app/api/v1/endpoints/trainings.py
git commit -m "feat: manager list — Publish/Unpublish/Archive action buttons, 'ready' status filter"
```

---

## Task 12: Full test run and validation

- [ ] **Step 1: Run full backend test suite**

```bash
docker compose exec core-service pytest tests/ -v
```

Expected: all tests pass. Investigate and fix any regressions before proceeding.

- [ ] **Step 2: Start the stack and smoke test**

```bash
docker compose up --build
```

- [ ] **Step 3: Manual verification checklist**

As a Training Creator:
- [ ] Create a training (verify `lifecycle_status === 'draft'` shown in editor)
- [ ] Add a chapter, set category, write description
- [ ] Click "Mark as Ready" → status changes to `ready`
- [ ] Try to create another chapter → should succeed (still can edit metadata, but check chapter creation)
- [ ] Log in as Manager → see training in "Ready" filter
- [ ] Click "Publish" as Manager → training becomes `published`
- [ ] Click "Unpublish" as Manager → back to `draft`, learner progress cleared
- [ ] Publish again → assign a learner
- [ ] Test archive gate: archive while learner hasn't completed → should 400
- [ ] Verify category dropdown shows tenant categories

- [ ] **Step 4: Final lint**

```bash
cd app/frontend && npm run lint
```

Expected: zero errors.
