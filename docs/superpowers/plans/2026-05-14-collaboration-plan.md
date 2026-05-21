# Training Collaboration (Audit Trail, Edit Lock, Notifications) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce that collaborators can only edit in Draft state, add In-App + Email notifications when collaborators are added, make the audit endpoint role-filtered (Managers see state transitions only; Creators see all), and surface collaborator names (not just IDs) in the UI.

**Architecture:** No DB schema changes needed — `training_collaborators` and `audit_logs` tables already exist. Work is purely in endpoint logic, notification event publishing, and frontend components. The collaborator modal (`ManageEditorsModal.tsx`) is renamed/updated. The audit timeline component (`TrainingAuditTimeline.tsx`) already exists and needs human-readable label mapping.

**Prerequisite:** Subsystem 1 (Creation) plan must be complete — specifically, `is_ready` field and `lifecycle_status` must exist on the `Training` model and schema before the edit-lock check here will work correctly.

**Tech Stack:** FastAPI (async SQLAlchemy), Redis event publisher, React + TypeScript, shadcn/ui, lucide-react.

**Run tests:** `docker compose exec core-service pytest tests/ -v`
**Lint frontend:** `cd app/frontend && npm run lint`

---

## File Map

**Backend — changed:**
- `app/core_service/app/api/v1/endpoints/trainings.py`
  - `add_collaborators`: remove Draft-only restriction on adding; send notification event; audit log already exists
  - `check_training_edit_permission`: block editing if `is_ready=True` or `is_published=True` (not just `is_published`)
  - `get_training_audit`: add role-filtered response

**Frontend — changed:**
- `app/frontend/src/components/ManageEditorsModal.tsx` → show collaborator names
- `app/frontend/src/components/TrainingAuditTimeline.tsx` → human-readable action labels
- `app/frontend/src/pages/ManagerTrainingEditor.tsx` → edit-lock banner when training is not Draft

---

## Task 1: Fix `check_training_edit_permission` — lock on `is_ready` or `is_published`

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/trainings.py`

**Problem:** The helper currently returns `False` only when `training.is_published`. After Subsystem 1, there is also `is_ready = True` state where content editing should be locked (only metadata/collaborators remain editable).

- [ ] **Step 1: Write failing test**

```python
async def test_chapter_create_blocked_when_ready(async_client, creator_headers, test_training_id_ready):
    """Chapters cannot be added to a Ready training."""
    resp = await async_client.post(
        f"/api/v1/trainings/{test_training_id_ready}/chapters",
        json={"title": "New Chapter", "content_type": "RICH_TEXT", "content_data": {}, "sequence_order": 99},
        headers=creator_headers,
    )
    assert resp.status_code == 403
    assert "draft" in resp.json()["detail"].lower()
```

- [ ] **Step 2: Run test — expect FAIL (currently 201)**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_chapter_create_blocked_when_ready -v
```

Expected: FAILED — currently returns 201 because only `is_published` is checked.

- [ ] **Step 3: Update `check_training_edit_permission`**

Find `check_training_edit_permission` (around line 84) and change the guard:

```python
async def check_training_edit_permission(
    training: Training,
    current_user: deps.UserAuth,
    db: AsyncSession
) -> bool:
    """
    Check if user has permission to edit a training's content.
    Content editing (chapters, modules) is only allowed in Draft state.
    """
    # Lock on is_ready OR is_published OR is_archived
    if training.is_ready or training.is_published or training.is_archived:
        return False

    # Admins and Business Managers can edit metadata, but not content when locked
    if any(role in ["Business Manager", "Admin", "SysAdmin"] for role in current_user.roles):
        return True

    if training.created_by_id == current_user.id:
        return True

    # Check if collaborator
    stmt = select(TrainingCollaborator).where(
        TrainingCollaborator.training_id == training.id,
        TrainingCollaborator.user_id == current_user.id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None
```

Also update the error message in endpoints that call this helper. In `update_training` (around line 362), change the existing published check to use `lifecycle_status` awareness:

```python
    if training.is_ready or training.is_published or training.is_archived:
        raise HTTPException(
            status_code=400,
            detail="Training must be in Draft state to edit content. Return it to Draft first."
        )
```

- [ ] **Step 4: Run test — expect pass**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_chapter_create_blocked_when_ready -v
```

Expected: PASSED.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
docker compose exec core-service pytest tests/ -v
```

Expected: no regressions. Fix any before continuing.

- [ ] **Step 6: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/trainings.py
git commit -m "fix: lock chapter/module editing when training is Ready, Published, or Archived (not just Published)"
```

---

## Task 2: `add_collaborators` — allow at any state, send notification event

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/trainings.py`

**Current state:** `add_collaborators` calls `check_training_edit_permission` which would fail for Ready/Published trainings after Task 1. We want to allow adding collaborators at any state (BR-302), but the notification event dispatch is missing.

- [ ] **Step 1: Write failing test for notification**

```python
async def test_add_collaborator_to_ready_training_allowed(async_client, creator_headers, test_training_id_ready, collaborator_user_id):
    """Collaborators can be added to a Ready training (not just Draft)."""
    resp = await async_client.post(
        f"/api/v1/trainings/{test_training_id_ready}/collaborators",
        json=[collaborator_user_id],
        headers=creator_headers,
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test — expect FAIL (403 from edit lock)**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_add_collaborator_to_ready_training_allowed -v
```

Expected: FAILED — 403 because the old check was inherited.

- [ ] **Step 3: Fix `add_collaborators` endpoint**

Find `add_collaborators` (around line 703). Replace the permission check so it uses `is_owner_or_admin` directly instead of `check_training_edit_permission` (which would block at Ready state), and add notification event publishing:

```python
@router.post("/{training_id}/collaborators", response_model=List[TrainingCollaboratorSchema])
async def add_collaborators(
    training_id: str,
    collaborators_in: List[str],
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Add collaborators to a training at any state. Owner or Admin only (BR-302).
    Collaborators receive an In-App + Email notification.
    """
    result = await db.execute(
        select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id)
    )
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    if not await is_owner_or_admin(training, current_user):
        raise HTTPException(status_code=403, detail="Only the owner or an admin can manage collaborators")

    if training.is_archived:
        raise HTTPException(status_code=400, detail="Cannot add collaborators to an archived training")

    added = []
    for uid in collaborators_in:
        existing = await db.execute(
            select(TrainingCollaborator).where(
                TrainingCollaborator.training_id == training_id,
                TrainingCollaborator.user_id == uid,
            )
        )
        if not existing.scalar_one_or_none():
            collab = TrainingCollaborator(training_id=training_id, user_id=uid)
            db.add(collab)
            added.append(uid)
            await log_audit(db, tenant_id, current_user.id, "collaborator_added", "training", training_id,
                            {"collaborator_id": uid})
            # Notify the added collaborator
            from app.core.events import publisher
            await publisher.publish_event(
                "COLLABORATOR_ADDED",
                {
                    "tenant_id": tenant_id,
                    "recipient_user_id": uid,
                    "training_id": training_id,
                    "training_title": training.title,
                    "added_by_name": current_user.full_name or "A trainer",
                }
            )

    await db.commit()
    result2 = await db.execute(
        select(TrainingCollaborator).where(TrainingCollaborator.training_id == training_id)
    )
    return result2.scalars().all()
```

- [ ] **Step 4: Run test — expect pass**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_add_collaborator_to_ready_training_allowed -v
```

Expected: PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/trainings.py
git commit -m "fix: allow adding collaborators at any state; add COLLABORATOR_ADDED notification event"
```

---

## Task 3: Role-filtered audit endpoint

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/trainings.py`

**Current state:** `get_training_audit` returns all logs to anyone with any management role. Per BR-309a, Managers see state-transition events only; Creators (owner) and collaborators see all events.

State-transition action strings (after Tasks 5-7 in the Creation plan): `training_marked_ready`, `training_sent_to_draft`, `training_published`, `training_unpublished`, `training_archived`.

- [ ] **Step 1: Write failing test**

```python
async def test_audit_manager_sees_state_transitions_only(async_client, manager_headers, creator_headers, test_training_id_published):
    """Manager sees only state-transition audit events, not chapter edits."""
    # First add a chapter edit event via creator
    await async_client.post(
        f"/api/v1/trainings/{test_training_id_published}/chapters",
        json={"title": "Ch", "content_type": "RICH_TEXT", "content_data": {}, "sequence_order": 1},
        headers=creator_headers,
    )
    resp = await async_client.get(
        f"/api/v1/trainings/{test_training_id_published}/audit",
        headers=manager_headers
    )
    assert resp.status_code == 200
    actions = [e["action"] for e in resp.json()]
    # Manager should see state transition events
    assert any(a in actions for a in [
        "training_published", "training_unpublished", "training_archived",
        "training_marked_ready", "training_sent_to_draft"
    ])
    # Manager should NOT see chapter-level events
    assert "CREATE_CHAPTER" not in actions
    assert "UPDATE_CHAPTER" not in actions
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_audit_manager_sees_state_transitions_only -v
```

Expected: FAILED — Manager currently sees all events.

- [ ] **Step 3: Update `get_training_audit` with role filtering**

Find `get_training_audit` (around line 1080). Replace the body with:

```python
@router.get("/{training_id}/audit", response_model=List[TrainingAuditLog])
async def get_training_audit(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Get audit log for a training. Role-filtered per BR-309a:
    - Manager: state transitions only
    - Creator (owner) / Collaborator / SysAdmin: all events
    """
    is_manager_only = (
        any(role in ["Business Manager"] for role in current_user.roles)
        and not any(role in ["SysAdmin", "Admin"] for role in current_user.roles)
    )
    is_creator = any(role in ["Training Creator"] for role in current_user.roles)

    # Verify training exists and user has access
    training_result = await db.execute(
        select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id)
    )
    training = training_result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    if is_creator and not any(role in ["Business Manager", "Admin", "SysAdmin"] for role in current_user.roles):
        # Creator must be owner or active collaborator
        is_owner = training.created_by_id == current_user.id
        collab_result = await db.execute(
            select(TrainingCollaborator).where(
                TrainingCollaborator.training_id == training_id,
                TrainingCollaborator.user_id == current_user.id,
            )
        )
        if not is_owner and not collab_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not authorized to view this training's audit log")

    STATE_TRANSITION_ACTIONS = {
        "training_marked_ready", "training_sent_to_draft",
        "training_published", "training_unpublished", "training_archived",
        "PUBLISH_TRAINING", "ARCHIVE_TRAINING",  # legacy action names
    }

    from sqlalchemy import cast, TEXT
    stmt = (
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .where(
            or_(
                AuditLog.entity_id == training_id,
                AuditLog.metadata_json["training_id"].as_string() == training_id,
            )
        )
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    )

    result = await db.execute(stmt)
    logs = result.scalars().all()

    # Filter by role
    if is_manager_only:
        logs = [l for l in logs if l.action in STATE_TRANSITION_ACTIONS]

    # Enrich with user names
    user_ids = list(set(l.user_id for l in logs))
    users_data = await deps.get_users_batch(user_ids)

    enriched = []
    for l in logs:
        schema = TrainingAuditLog.model_validate(l)
        if l.user_id in users_data:
            schema.user_name = users_data[l.user_id].get("full_name")
        enriched.append(schema)

    return enriched
```

- [ ] **Step 4: Run test — expect pass**

```bash
docker compose exec core-service pytest tests/api/test_trainings.py::test_audit_manager_sees_state_transitions_only -v
```

Expected: PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/trainings.py
git commit -m "feat: role-filtered audit endpoint — Managers see state transitions only (BR-309a)"
```

---

## Task 4: Frontend — ManageEditorsModal shows collaborator names

**Files:**
- Modify: `app/frontend/src/components/ManageEditorsModal.tsx`

**Problem:** The modal currently displays collaborator `user_id` values only. The `deps.get_users_batch` helper exists on the backend — the collaborator list endpoint needs to return enriched data, OR the frontend fetches names separately.

The simpler path: have the collaborators list endpoint return enriched data. The `add_collaborators` endpoint already returns the list, but without names. The backend `deps.get_users_batch` can be called after fetching collaborators.

- [ ] **Step 1: Enrich collaborator list endpoint**

Find `list_collaborators` (around line 520) in `trainings.py`. After fetching the list, enrich with user names:

```python
@router.get("/{training_id}/collaborators", response_model=List[schemas.training.TrainingCollaborator])
async def list_collaborators(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """List all collaborators for a training with enriched user names."""
    result = await db.execute(
        select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id)
    )
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # Allow owner, collaborator, or manager to list collaborators
    is_manager = any(role in ["Business Manager", "Admin", "SysAdmin"] for role in current_user.roles)
    is_owner = training.created_by_id == current_user.id
    collab_result = await db.execute(
        select(TrainingCollaborator).where(
            TrainingCollaborator.training_id == training_id,
            TrainingCollaborator.user_id == current_user.id,
        )
    )
    if not is_manager and not is_owner and not collab_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not enough permissions")

    stmt = select(TrainingCollaborator).where(TrainingCollaborator.training_id == training_id)
    result2 = await db.execute(stmt)
    collabs = result2.scalars().all()

    user_ids = [c.user_id for c in collabs]
    users_data = await deps.get_users_batch(user_ids)

    enriched = []
    for c in collabs:
        schema = TrainingCollaboratorSchema.model_validate(c)
        schema.user_name = users_data.get(c.user_id, {}).get("full_name")
        enriched.append(schema)

    return enriched
```

Also update `TrainingCollaborator` Pydantic schema in `training.py` to include `user_name`:

```python
class TrainingCollaborator(TrainingCollaboratorBase):
    user_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
```

And update the TypeScript `TrainingCollaborator` interface in `trainings.ts`:

```typescript
export interface TrainingCollaborator {
    user_id: string;
    user_name?: string;
}
```

- [ ] **Step 2: Update ManageEditorsModal to show names**

In `app/frontend/src/components/ManageEditorsModal.tsx`, find where collaborators are listed. Replace the display of `user_id` with `user_name` (falling back to truncated `user_id`):

```tsx
<span className="text-sm font-medium">
    {collaborator.user_name || collaborator.user_id.slice(0, 8) + '…'}
</span>
```

- [ ] **Step 3: Add state-lock informational message**

In the modal, check the training state. If not Draft, show a note:

```tsx
{training && training.lifecycle_status !== 'draft' && (
    <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800">
        This training is <strong>{training.lifecycle_status}</strong>. Collaborators can view but not edit content — the owner must return the training to Draft to enable editing.
    </div>
)}
```

The modal already receives a `training` prop (or `trainingId`). Ensure the `lifecycle_status` field is available via the `Training` type (updated in Task 9 of the Creation plan).

- [ ] **Step 4: Lint check**

```bash
cd app/frontend && npm run lint
```

Expected: zero errors.

- [ ] **Step 5: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/trainings.py app/core_service/app/schemas/training.py app/frontend/src/components/ManageEditorsModal.tsx app/frontend/src/api/trainings.ts
git commit -m "feat: collaborator modal shows user names; add state-lock informational message"
```

---

## Task 5: Frontend — audit timeline human-readable labels and editor edit-lock banner

**Files:**
- Modify: `app/frontend/src/components/TrainingAuditTimeline.tsx`
- Modify: `app/frontend/src/pages/ManagerTrainingEditor.tsx`

- [ ] **Step 1: Add human-readable labels to `TrainingAuditTimeline`**

Open `app/frontend/src/components/TrainingAuditTimeline.tsx`. Find where `log.action` is displayed. Add a label mapping function:

```tsx
function formatAuditAction(action: string, metadata?: Record<string, unknown>): string {
    const map: Record<string, string> = {
        training_marked_ready: 'Marked as Ready',
        training_sent_to_draft: 'Returned to Draft',
        training_published: 'Published',
        training_unpublished: 'Unpublished',
        training_archived: 'Archived',
        collaborator_added: 'Collaborator added',
        collaborator_removed: 'Collaborator removed',
        CREATE_CHAPTER: 'Chapter added',
        UPDATE_CHAPTER: 'Chapter updated',
        DELETE_CHAPTER: 'Chapter deleted',
        CREATE_TRAINING: 'Training created',
        UPDATE_TRAINING: 'Training details updated',
        ADD_COLLABORATOR: 'Collaborator added',
        REMOVE_COLLABORATOR: 'Collaborator removed',
        PUBLISH_TRAINING: 'Published',
        ARCHIVE_TRAINING: 'Archived',
        progress_reset: 'Learner progress reset',
        SUBMIT_QUIZ: 'Quiz submitted',
    };
    return map[action] ?? action.toLowerCase().replace(/_/g, ' ');
}
```

Replace `{log.action}` in the rendered timeline with:

```tsx
{formatAuditAction(log.action, log.metadata_json)}
```

- [ ] **Step 2: Add edit-lock banner in `ManagerTrainingEditor.tsx`**

When `training.lifecycle_status` is `'ready'` or `'published'` and the current user is a collaborator (not owner), show a banner:

```tsx
{training && training.lifecycle_status !== 'draft' && !isOwner && (
    <div className="mb-4 flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
        <AlertCircle className="h-4 w-4 shrink-0" />
        <span>
            This training is <strong>{training.lifecycle_status}</strong> and locked for editing.
            The owner must return it to Draft before content can be changed.
        </span>
    </div>
)}
```

Import `AlertCircle` from `'lucide-react'` if not already imported.

Also disable the "Add Chapter" button and chapter edit inputs when the training is not in Draft:

```tsx
<Button
    size="sm"
    onClick={handleAddChapter}
    disabled={training?.lifecycle_status !== 'draft'}
>
    Add Chapter
</Button>
```

- [ ] **Step 3: Lint check**

```bash
cd app/frontend && npm run lint
```

Expected: zero errors.

- [ ] **Step 4: Run full test suite**

```bash
docker compose exec core-service pytest tests/ -v
```

Expected: all passing.

- [ ] **Step 5: Commit**

```bash
git add app/frontend/src/components/TrainingAuditTimeline.tsx app/frontend/src/pages/ManagerTrainingEditor.tsx
git commit -m "feat: human-readable audit event labels; edit-lock banner in editor for non-Draft trainings"
```

---

## Task 6: Final validation

- [ ] **Step 1: Smoke test collaboration flow**

```bash
docker compose up
```

As Training Creator (owner):
- [ ] Create a training in Draft
- [ ] Add a collaborator via the modal → verify collaborator's name is shown (not just ID)
- [ ] Mark training as Ready
- [ ] Open modal again → verify the state-lock message appears
- [ ] Log in as collaborator → open training editor → verify lock banner appears, "Add Chapter" is disabled

As Business Manager:
- [ ] Open audit timeline for a training → verify only state transitions show (not chapter edits)

As Training Creator (owner):
- [ ] Open audit timeline → verify all events including chapter creates are visible

- [ ] **Step 2: Final lint**

```bash
cd app/frontend && npm run lint
```

Expected: zero errors.
