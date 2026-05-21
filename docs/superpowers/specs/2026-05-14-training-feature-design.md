# Training Feature Design — Creation, Collaboration & Execution

**Date:** 2026-05-14
**Status:** Approved
**Subsystems:** 3 (independent implementation plans)

---

## Overview

This document specifies the full design for the training lifecycle, covering three subsystems:

1. **Creation** — training state machine, categories, Ready gate, role-based publishing
2. **Collaboration** — collaborator management, audit trail, notifications
3. **Execution** — learner video progress, flat-structure viewer, rich text rendering, completion flow

These subsystems are independent and can be planned and implemented separately.

---

## Subsystem 1: Creation

### Goal

Replace the current `is_published` boolean with a 4-state training lifecycle. Give Managers exclusive publish/unpublish/archive authority. Enforce the Ready gate server-side. Add tenant-managed category system.

### Training States

| State | Description | Who can transition in |
|---|---|---|
| `draft` | Being actively built by Creator | Initial state; Manager unpublishes; Manager sends back to Draft |
| `ready` | Contents complete, available for assignment | Creator (owner) marks Ready |
| `published` | Assigned and visible to learners | Manager publishes |
| `archived` | Closed; history preserved | Manager archives (gate applies) |

State machine rules (BR-301, BR-301a):
- **Draft → Ready**: Creator (owner only). Locks editing.
- **Ready → Draft**: Creator (owner) OR Manager. Unlocks editing.
- **Ready → Published**: Manager only. Writes version snapshot.
- **Published → Draft (Unpublish)**: Manager only. Assignments preserved; learner progress reset.
- **Published → Archived**: Manager only. Gate: all learners completed OR all due dates passed (BR-503).

### Database Changes

**`trainings` table:**
- Add `status` column: `VARCHAR(20)` default `'draft'` — values: `draft | ready | published | archived`
- Keep `is_published` in sync for backward compatibility (derive from status)
- Add `requires_recertification BOOLEAN DEFAULT FALSE`
- Add `recertification_period_days INTEGER NULL`

**`training_categories` table (new):**
```sql
id UUID PRIMARY KEY
tenant_id UUID NOT NULL REFERENCES tenants(id)
name VARCHAR(255) NOT NULL
is_active BOOLEAN DEFAULT TRUE
created_at TIMESTAMPTZ DEFAULT now()
UNIQUE(tenant_id, name)
```

**`chapters` table:**
- Add `completion_mode VARCHAR(20) DEFAULT 'can_continue'` — values: `can_continue | must_watch_full`
- Only meaningful for `content_type = 'video'`

### API Changes

**New endpoints on `/api/v1/trainings`:**

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/{id}/mark-ready` | Creator (owner) | Draft → Ready; enforces Ready gate |
| POST | `/{id}/send-to-draft` | Creator (owner) OR Manager | Ready → Draft |
| POST | `/{id}/publish` | Manager | Ready → Published; writes version snapshot |
| POST | `/{id}/unpublish` | Manager | Published → Draft; resets learner progress |
| POST | `/{id}/archive` | Manager | Published → Archived; gate enforced |

**Ready gate** (BR-305a) — server-side validation in `mark-ready`:
- title is set
- description is set
- category is set (exists in tenant's category list)
- at least one chapter/lesson exists

**Categories endpoints (tenant-scoped via JWT):**

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/categories` | Creator + Manager | List tenant categories |
| POST | `/categories` | Manager | Create category |
| PUT | `/categories/{id}` | Manager | Update category |
| DELETE | `/categories/{id}` | Manager | Soft-delete category |

All category endpoints extract `tenant_id` from JWT — never from URL or body.

**Structure endpoint fix:**
`GET /trainings/{id}/structure` currently omits `tags`, `category`, `requires_certificate`, `template_id`, `collaborators` from the response. Fix: include all Training fields in the response so the editor form does not revert on load.

### UI Changes

**ManagerTrainingEditor.tsx:**
- Remove Publish button from editor (Creators cannot publish)
- Add "Mark as Ready" button (visible when status is `draft`, owner only)
- Add "Send to Draft" button (visible when status is `ready`)
- Add category dropdown (populated from `GET /categories`)
- Add completion mode toggle on video chapter form: "Must Watch Full" / "Can Continue"
- Show status badge in editor header (Draft / Ready / Published / Archived)

**ManagerTrainings.tsx (Manager view):**
- Add "Publish" button on Ready-status trainings
- Add "Unpublish" button on Published trainings
- Add "Archive" button on Published trainings (with confirmation dialog showing gate conditions)
- Filter/tab support for status: All / Draft / Ready / Published / Archived

---

## Subsystem 2: Collaboration

### Goal

Allow training owners to add/remove Training Creators as collaborators at any state. Enforce that collaborators can only edit in Draft state. Track all collaborator and state changes in the audit log with role-filtered visibility.

### Database Changes

None. `training_collaborators` table and `audit_logs` table already exist.

### API Changes

**Collaborator endpoints (no change to paths, update logic):**
- `POST /trainings/{id}/collaborators` — allow at any state (not just Draft). Audit the addition. Trigger In-App + Email notification to added user.
- `DELETE /trainings/{id}/collaborators/{user_id}` — allow at any state. Audit the removal.

**Audit endpoint:**
- `GET /trainings/{id}/audit` — role-filtered response:
  - **SysAdmin**: all events (state transitions + collaborator changes + chapter edits)
  - **Creator (owner)**: all events on their trainings
  - **Collaborator**: all events on trainings they are active on
  - **Manager**: state transitions only (published, unpublished, archived events); no chapter-level diffs

**Edit lock enforcement:**
- All chapter create/update/delete endpoints must check: if training status is not `draft`, return 403 with message "Training must be in Draft state to edit content."
- Collaborator check: if the requesting user is a collaborator (not owner) and status is not `draft`, block edit.

### Notification Logic

When a collaborator is added:
1. Create in-app notification via notification service
2. Enqueue email notification via Redis queue (notification service handles delivery)

Notification content: "You've been added as a collaborator on [Training Title]."

### UI Changes

**ManageCollaboratorsModal (rename from ManageEditorsModal):**
- Display collaborator names alongside user IDs (currently shows only IDs)
- Show current training status; if not Draft, show informational note: "Collaborators can view but not edit — training must be in Draft state to edit content."
- Add/remove collaborator UI unchanged

**Training editor — edit lock:**
- If training status is not `draft` and current user is a collaborator (not owner), disable all content-editing controls and show a banner: "This training is locked for editing. The owner must return it to Draft."

**Audit timeline panel:**
- Add audit log tab/drawer in the editor
- Display events chronologically with human-readable labels:
  - `training_marked_ready` → "Marked as Ready by [name]"
  - `training_published` → "Published by [name]"
  - `training_unpublished` → "Unpublished by [name]"
  - `collaborator_added` → "[name] added as collaborator by [name]"
  - `collaborator_removed` → "[name] removed as collaborator by [name]"
  - `chapter_created` → "Chapter added: [title]"
  - `chapter_updated` → "Chapter edited: [title]"

---

## Subsystem 3: Execution

### Goal

Fix the learner training viewer so video progress is tracked correctly, flat-structure trainings show their chapters, rich text renders properly, and the completion flow is clean (no redundant API calls).

### Database Changes

None beyond `completion_mode` from Subsystem 1.

### API Changes

**Video progress endpoint** (`POST /progress/video`) — already exists but not called from frontend. Frontend must call it:
- On play: `{ chapter_id, position: 0, event: "play" }`
- On pause/seek: `{ chapter_id, position: currentTime, event: "pause" }`
- On ended (100% watched): `{ chapter_id, position: duration, event: "complete" }`

**Remove redundant `POST /trainings/{id}/complete-training` call:**
The backend `complete_chapter` endpoint already calls `_process_training_completion`. The explicit frontend `completeTraining()` call after completing the last chapter is redundant and causes a double-completion attempt. Remove it from the frontend.

### UI Changes

**Viewer sidebar — flat structure fix:**
Currently `TrainingViewer.tsx` renders `structure.modules` only. For flat-structure trainings, chapters live in `structure.orphan_chapters`. Fix: render `orphan_chapters` when `structure.modules` is empty or when `structure_type === 'flat'`.

**ReactPlayer — correct event wiring:**
- Replace native video `onTimeUpdate` with ReactPlayer's `onProgress` callback (fires every ~0.5s with `{ playedSeconds, played }`)
- Use `onEnded` for 100% completion
- Use `onPause` for pause/seek events
- Ref type: `ReactPlayer` (not `HTMLVideoElement`)

**Video completion mode:**
- If `completion_mode === 'must_watch_full'`: disable "Mark Complete" / "Next" button until `onEnded` fires
- If `completion_mode === 'can_continue'`: button is enabled immediately on load

**Rich text rendering:**
- Wrap TipTap HTML output in a `div` with Tailwind Typography `prose` class for proper heading/paragraph/list styling
- Use a sanitization approach: pass TipTap-generated HTML through a whitelist-based sanitizer (e.g., DOMPurify in browser) before rendering

**Expired training banner:**
- If `training.status === 'expired'` or enrollment is overdue with Completion Lock active, show a full-width banner: "Access to this training has expired. Contact your manager."
- Disable all chapter navigation controls

---

## Cross-Cutting Concerns

### Tenant Scoping
Every new endpoint (categories, status transitions) must extract `tenant_id` from the JWT, never from the request body or URL. All DB queries filter by `tenant_id`.

### Audit Log (BR-309)
Append-only. Events to log:
- `training_marked_ready`, `training_sent_to_draft`, `training_published`, `training_unpublished`, `training_archived`
- `collaborator_added`, `collaborator_removed`
- `chapter_created`, `chapter_updated`, `chapter_deleted`
- `progress_reset` (on unpublish or pushback)

### Alembic Migrations
Each DB change requires an Alembic migration in `core_service/alembic/versions/`. Migrations are additive — never drop columns.

### Frontend Lint Policy
`npm run lint` must pass with zero errors after every frontend change (project policy).

---

## Out of Scope

- SCORM execution (Phase 8)
- Re-certification auto-enrollment (separate trigger, Phase 7)
- Bulk user import (auth service concern)
- SysAdmin audit cross-tenant view (admin panel, separate feature)
