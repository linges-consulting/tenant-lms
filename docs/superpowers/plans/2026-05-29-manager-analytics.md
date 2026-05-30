# Manager Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-level Training Analytics section for Business Managers: a list page with per-training stats, a detail page with quiz performance and per-employee drill-down, PDF/CSV exports, a proactive lockout card on the dashboard, and a Trainings tab on ProfilePage.

**Architecture:** New `analytics.py` router on core_service handles all data aggregation from existing tables (no migrations). Two new frontend pages (`ManagerAnalytics`, `ManagerAnalyticsDetail`) plus extensions to Dashboard, ProfilePage, and ManagerEmployees. Group filtering and "approaching limit" calculations are client-side.

**Tech Stack:** FastAPI + SQLAlchemy 2.x (async), WeasyPrint (PDF), Python csv (CSV), React + TanStack Query, Vitest + RTL (frontend tests), pytest + httpx (backend tests)

---

## File Map

**Create:**
- `app/core_service/app/api/v1/endpoints/analytics.py`
- `app/notification_service/app/worker/templates/training_reminder.html`
- `app/frontend/src/api/analytics.ts`
- `app/frontend/src/pages/ManagerAnalytics.tsx`
- `app/frontend/src/pages/ManagerAnalyticsDetail.tsx`
- `app/core_service/tests/api/test_analytics.py`

**Modify:**
- `app/core_service/app/api/v1/api.py` — register analytics router
- `app/notification_service/app/worker/consumer.py` — add TRAINING_REMINDER handler
- `app/frontend/src/App.tsx` — add two analytics routes
- `app/frontend/src/components/layout/Sidebar.tsx` — add Analytics nav item
- `app/frontend/src/pages/ManagerDashboard.tsx` — add lockout stat card
- `app/frontend/src/pages/ManagerEmployees.tsx` — make rows clickable
- `app/frontend/src/pages/ProfilePage.tsx` — add Trainings tab

---

## Task 1: Backend — Analytics router + training list endpoint

**Files:**
- Create: `app/core_service/app/api/v1/endpoints/analytics.py`
- Create: `app/core_service/tests/api/test_analytics.py`

- [ ] **Step 1: Write the failing test**

```python
# app/core_service/tests/api/test_analytics.py
import pytest
import uuid
from unittest.mock import patch, AsyncMock
from app.main import app
from app.api.deps import get_current_user, get_current_tenant_id
from app.models.training import Training
from app.models.assignment import TrainingAssignment
from app.models.enrollment import Enrollment
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
    # Seed a training and one assignment
    training = Training(
        id=str(uuid.uuid4()), tenant_id=tid, title="Safety 101",
        category="Safety", is_published=True, created_by_id=user.id,
    )
    db_session.add(training)
    assignment = TrainingAssignment(
        id=str(uuid.uuid4()), tenant_id=tid,
        training_id=training.id, user_id=str(uuid.uuid4()),
    )
    db_session.add(assignment)
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
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd app/core_service && pytest tests/api/test_analytics.py::test_analytics_list_returns_trainings -v
```
Expected: `FAILED` — `404 Not Found` (route doesn't exist yet)

- [ ] **Step 3: Create the analytics router with the list endpoint**

```python
# app/core_service/app/api/v1/endpoints/analytics.py
from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, and_, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.session import get_db
from app.models.assignment import TrainingAssignment
from app.models.chapter import Chapter, ContentType
from app.models.enrollment import Enrollment
from app.models.progress import UserProgress
from app.models.quiz_attempt import QuizAttempt
from app.models.training import Training
from app.utils.pdf import render_certificate_pdf

router = APIRouter()


@router.get("/trainings")
async def analytics_training_list(
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """All trainings for this tenant with pre-computed analytics stats."""
    now = datetime.now(timezone.utc)

    trainings_result = await db.execute(
        select(Training).where(
            Training.tenant_id == tenant_id,
            Training.deleted_at.is_(None),
        )
    )
    trainings = trainings_result.scalars().all()
    if not trainings:
        return []

    training_ids = [t.id for t in trainings]

    # Enrolled counts (non-deleted assignments with user_id)
    enrolled_q = await db.execute(
        select(TrainingAssignment.training_id, func.count(TrainingAssignment.id))
        .where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.training_id.in_(training_ids),
            TrainingAssignment.deleted_at.is_(None),
            TrainingAssignment.user_id.isnot(None),
        )
        .group_by(TrainingAssignment.training_id)
    )
    enrolled_map: dict[str, int] = {row[0]: row[1] for row in enrolled_q.all()}

    # Completed counts
    completed_q = await db.execute(
        select(Enrollment.training_id, func.count(Enrollment.id))
        .where(
            Enrollment.tenant_id == tenant_id,
            Enrollment.training_id.in_(training_ids),
            Enrollment.is_completed.is_(True),
        )
        .group_by(Enrollment.training_id)
    )
    completed_map: dict[str, int] = {row[0]: row[1] for row in completed_q.all()}

    # Overdue: due_date < now, user not completed
    overdue_q = await db.execute(
        select(TrainingAssignment.training_id, func.count(TrainingAssignment.id))
        .where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.training_id.in_(training_ids),
            TrainingAssignment.deleted_at.is_(None),
            TrainingAssignment.user_id.isnot(None),
            TrainingAssignment.due_date.isnot(None),
            TrainingAssignment.due_date < now,
            ~exists(
                select(Enrollment.id).where(
                    Enrollment.tenant_id == tenant_id,
                    Enrollment.training_id == TrainingAssignment.training_id,
                    Enrollment.user_id == TrainingAssignment.user_id,
                    Enrollment.is_completed.is_(True),
                )
            ),
        )
        .group_by(TrainingAssignment.training_id)
    )
    overdue_map: dict[str, int] = {row[0]: row[1] for row in overdue_q.all()}

    # Lockout counts per training: users with attempt_number >= max_attempts and not passed
    # max_attempts from chapter content_data; we use 10 as fallback (same as dashboards.py)
    quiz_chapters_q = await db.execute(
        select(Chapter).where(
            Chapter.tenant_id == tenant_id,
            Chapter.training_id.in_(training_ids),
            Chapter.content_type == ContentType.QUIZ,
            Chapter.deleted_at.is_(None),
        )
    )
    quiz_chapters = quiz_chapters_q.scalars().all()
    chapter_to_training = {c.id: c.training_id for c in quiz_chapters}
    chapter_max = {c.id: (c.content_data or {}).get("max_attempts", 10) for c in quiz_chapters}

    lockout_map: dict[str, int] = defaultdict(int)
    if quiz_chapters:
        chapter_ids = [c.id for c in quiz_chapters]
        attempts_q = await db.execute(
            select(
                QuizAttempt.chapter_id,
                QuizAttempt.user_id,
                func.max(QuizAttempt.attempt_number).label("max_att"),
                func.sum(QuizAttempt.passed.cast(deps.Integer)).label("pass_count"),
            )
            .where(
                QuizAttempt.tenant_id == tenant_id,
                QuizAttempt.chapter_id.in_(chapter_ids),
                QuizAttempt.deleted_at.is_(None),
            )
            .group_by(QuizAttempt.chapter_id, QuizAttempt.user_id)
        )
        for row in attempts_q.all():
            cid, uid, max_att, pass_cnt = row
            max_allowed = chapter_max.get(cid, 10)
            if max_allowed and max_att >= max_allowed and not pass_cnt:
                tid_for_chapter = chapter_to_training.get(cid)
                if tid_for_chapter:
                    lockout_map[tid_for_chapter] += 1

    # Enrich creator names
    creator_ids = list({t.created_by_id for t in trainings if t.created_by_id})
    users_data = await deps.get_users_batch(creator_ids)

    result = []
    for t in trainings:
        enrolled = enrolled_map.get(t.id, 0)
        completed = completed_map.get(t.id, 0)
        creator_info = users_data.get(t.created_by_id or "", {})
        result.append({
            "id": t.id,
            "title": t.title,
            "category": t.category,
            "is_published": t.is_published,
            "creator_id": t.created_by_id,
            "creator_name": creator_info.get("full_name", ""),
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            "enrolled_count": enrolled,
            "completed_count": completed,
            "completion_pct": round(completed / enrolled * 100, 1) if enrolled else 0.0,
            "overdue_count": overdue_map.get(t.id, 0),
            "lockout_count": lockout_map.get(t.id, 0),
        })
    return result
```

Also add this import at the top of the file (SQLAlchemy Integer for cast):
```python
from sqlalchemy import Integer
```

- [ ] **Step 4: Register the router in api.py**

```python
# app/core_service/app/api/v1/api.py  — add these two lines
from app.api.v1.endpoints import analytics   # add to imports

api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd app/core_service && pytest tests/api/test_analytics.py::test_analytics_list_returns_trainings -v
```
Expected: `PASSED`

- [ ] **Step 6: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/analytics.py \
        app/core_service/app/api/v1/api.py \
        app/core_service/tests/api/test_analytics.py
git commit -m "feat(analytics): add training analytics list endpoint"
```

---

## Task 2: Backend — Training detail analytics endpoint

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/analytics.py`
- Modify: `app/core_service/tests/api/test_analytics.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_analytics.py`:

```python
@pytest.mark.asyncio
async def test_analytics_detail_overview(client, db_session):
    """Detail endpoint returns overview stats for a training."""
    from datetime import timedelta
    tid = str(uuid.uuid4())
    user = _make_manager(tid)
    learner_id = str(uuid.uuid4())
    _set_user(user)

    training = Training(
        id=str(uuid.uuid4()), tenant_id=tid, title="Health & Safety",
        category="HR", is_published=True, created_by_id=user.id,
    )
    db_session.add(training)

    # One assignment, one enrollment (completed)
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
        content_data={"max_attempts": 3, "questions": []}, order=1,
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
```

- [ ] **Step 2: Run to see fail**

```bash
cd app/core_service && pytest tests/api/test_analytics.py::test_analytics_detail_overview tests/api/test_analytics.py::test_analytics_detail_quiz_stats -v
```
Expected: `FAILED` — 404 (route not yet defined)

- [ ] **Step 3: Implement the detail endpoint**

Append to `analytics.py` after the list endpoint:

```python
@router.get("/trainings/{training_id}")
async def analytics_training_detail(
    training_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    now = datetime.now(timezone.utc)

    training = await db.get(Training, training_id)
    if not training or training.tenant_id != tenant_id or training.deleted_at:
        raise HTTPException(status_code=404, detail="Training not found")

    # All user-level assignments for this training
    asgn_q = await db.execute(
        select(TrainingAssignment).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.training_id == training_id,
            TrainingAssignment.deleted_at.is_(None),
            TrainingAssignment.user_id.isnot(None),
        )
    )
    assignments = asgn_q.scalars().all()
    user_ids = list({a.user_id for a in assignments})
    enrolled_count = len(assignments)

    if not assignments:
        return _empty_detail(training, enrolled_count)

    # Enrollments
    enroll_q = await db.execute(
        select(Enrollment).where(
            Enrollment.tenant_id == tenant_id,
            Enrollment.training_id == training_id,
        )
    )
    enrollments = {e.user_id: e for e in enroll_q.scalars().all()}

    # Quiz chapters
    ch_q = await db.execute(
        select(Chapter).where(
            Chapter.tenant_id == tenant_id,
            Chapter.training_id == training_id,
            Chapter.content_type == ContentType.QUIZ,
            Chapter.deleted_at.is_(None),
        )
    )
    quiz_chapters = ch_q.scalars().all()
    chapter_ids = [c.id for c in quiz_chapters]
    chapter_max = {c.id: (c.content_data or {}).get("max_attempts", 10) for c in quiz_chapters}

    # Quiz attempts
    attempt_rows = []
    if chapter_ids:
        att_q = await db.execute(
            select(QuizAttempt).where(
                QuizAttempt.tenant_id == tenant_id,
                QuizAttempt.chapter_id.in_(chapter_ids),
                QuizAttempt.deleted_at.is_(None),
            )
        )
        attempt_rows = att_q.scalars().all()

    # Group attempts by (chapter_id, user_id)
    att_by_chapter_user: dict[tuple, list] = defaultdict(list)
    for a in attempt_rows:
        att_by_chapter_user[(a.chapter_id, a.user_id)].append(a)

    # Per-user attempt summary: {user_id: {chapter_id: {count, passed}}}
    user_quiz_summary: dict[str, dict] = defaultdict(dict)
    for (cid, uid), atts in att_by_chapter_user.items():
        max_att_num = max(a.attempt_number for a in atts)
        passed = any(a.passed for a in atts)
        user_quiz_summary[uid][cid] = {
            "attempt_count": max_att_num,
            "max_attempts": chapter_max.get(cid, 10),
            "passed": passed,
        }

    # Quiz chapter aggregate stats
    quiz_stats = []
    for ch in quiz_chapters:
        cid = ch.id
        max_allowed = chapter_max.get(cid, 10)
        users_attempted = {uid for (c, uid) in att_by_chapter_user if c == cid}
        attempted_count = len(users_attempted)
        pass_users = {uid for uid in users_attempted if user_quiz_summary[uid].get(cid, {}).get("passed")}
        pass_count = len(pass_users)
        locked_users = {
            uid for uid in users_attempted
            if user_quiz_summary[uid][cid]["attempt_count"] >= max_allowed
            and not user_quiz_summary[uid][cid]["passed"]
        }
        all_scores = [a.score for a in attempt_rows if a.chapter_id == cid]
        avg_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0.0
        pass_attempt_numbers = [
            min(a.attempt_number for a in att_by_chapter_user[(cid, uid)] if a.passed)
            for uid in pass_users
            if any(a.passed for a in att_by_chapter_user[(cid, uid)])
        ]
        avg_attempts_to_pass = round(
            sum(pass_attempt_numbers) / len(pass_attempt_numbers), 1
        ) if pass_attempt_numbers else 0.0

        quiz_stats.append({
            "chapter_id": cid,
            "chapter_title": ch.title,
            "max_attempts": max_allowed,
            "attempted_count": attempted_count,
            "pass_count": pass_count,
            "pass_rate": round(pass_count / attempted_count * 100, 1) if attempted_count else 0.0,
            "avg_score": avg_score,
            "avg_attempts_to_pass": avg_attempts_to_pass,
            "locked_count": len(locked_users),
        })

    # Overdue, due-soon counts
    assignment_map = {a.user_id: a for a in assignments}
    overdue_count = sum(
        1 for a in assignments
        if a.due_date and a.due_date.replace(tzinfo=timezone.utc) < now
        and a.user_id not in enrollments or not enrollments.get(a.user_id, Enrollment()).is_completed
    )
    completed_count = sum(1 for e in enrollments.values() if e.is_completed)

    def _due_soon(days: int) -> int:
        cutoff = now + timedelta(days=days)
        return sum(
            1 for a in assignments
            if a.due_date
            and now <= a.due_date.replace(tzinfo=timezone.utc) <= cutoff
            and not enrollments.get(a.user_id, Enrollment()).is_completed
        )

    lockout_count = sum(
        1 for uid in user_ids
        if any(
            info["attempt_count"] >= info["max_attempts"] and not info["passed"]
            for info in user_quiz_summary.get(uid, {}).values()
        )
    )

    # Enrich users
    all_user_ids = user_ids + ([training.created_by_id] if training.created_by_id else [])
    users_data = await deps.get_users_batch(list(set(all_user_ids)))

    # Progress records to detect "in_progress"
    prog_q = await db.execute(
        select(UserProgress.user_id).where(
            UserProgress.tenant_id == tenant_id,
            UserProgress.training_id == training_id,
        ).distinct()
    )
    users_with_progress = {row[0] for row in prog_q.all()}

    def _employee_status(uid: str, asgn: TrainingAssignment) -> str:
        enroll = enrollments.get(uid)
        if enroll and enroll.is_completed:
            return "completed"
        locked = any(
            info["attempt_count"] >= info["max_attempts"] and not info["passed"]
            for info in user_quiz_summary.get(uid, {}).values()
        )
        if locked:
            return "locked"
        due = asgn.due_date
        if due and due.replace(tzinfo=timezone.utc) < now:
            return "overdue"
        if uid in users_with_progress:
            return "in_progress"
        return "not_started"

    employees = []
    for uid in user_ids:
        asgn = assignment_map[uid]
        uinfo = users_data.get(uid, {})
        enroll = enrollments.get(uid)
        locked_count = sum(
            1 for info in user_quiz_summary.get(uid, {}).values()
            if info["attempt_count"] >= info["max_attempts"] and not info["passed"]
        )
        employees.append({
            "user_id": uid,
            "username": uinfo.get("username", ""),
            "full_name": uinfo.get("full_name", ""),
            "email": uinfo.get("email", ""),
            "status": _employee_status(uid, asgn),
            "due_date": asgn.due_date.isoformat() if asgn.due_date else None,
            "completed_at": enroll.completed_at.isoformat() if enroll and enroll.completed_at else None,
            "locked_quiz_count": locked_count,
            "quiz_attempts": [
                {
                    "chapter_id": cid,
                    "attempt_count": info["attempt_count"],
                    "max_attempts": info["max_attempts"],
                    "passed": info["passed"],
                }
                for cid, info in user_quiz_summary.get(uid, {}).items()
            ],
        })

    creator_info = users_data.get(training.created_by_id or "", {})
    return {
        "training_id": training_id,
        "title": training.title,
        "category": training.category,
        "is_published": training.is_published,
        "creator_name": creator_info.get("full_name", ""),
        "enrolled_count": enrolled_count,
        "completed_count": completed_count,
        "completion_pct": round(completed_count / enrolled_count * 100, 1) if enrolled_count else 0.0,
        "overdue_count": overdue_count,
        "lockout_count": lockout_count,
        "due_soon_7d": _due_soon(7),
        "due_soon_14d": _due_soon(14),
        "due_soon_30d": _due_soon(30),
        "quiz_chapters": quiz_stats,
        "employees": employees,
    }


def _empty_detail(training: Training, enrolled_count: int) -> dict:
    return {
        "training_id": training.id,
        "title": training.title,
        "category": training.category,
        "is_published": training.is_published,
        "creator_name": "",
        "enrolled_count": enrolled_count,
        "completed_count": 0,
        "completion_pct": 0.0,
        "overdue_count": 0,
        "lockout_count": 0,
        "due_soon_7d": 0,
        "due_soon_14d": 0,
        "due_soon_30d": 0,
        "quiz_chapters": [],
        "employees": [],
    }
```

- [ ] **Step 4: Run tests**

```bash
cd app/core_service && pytest tests/api/test_analytics.py -v
```
Expected: all tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/analytics.py \
        app/core_service/tests/api/test_analytics.py
git commit -m "feat(analytics): add training detail analytics endpoint"
```

---

## Task 3: Backend — Employee drill-down + send-reminder endpoints

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/analytics.py`
- Modify: `app/notification_service/app/worker/consumer.py`
- Create: `app/notification_service/app/worker/templates/training_reminder.html`
- Modify: `app/core_service/tests/api/test_analytics.py`

- [ ] **Step 1: Write failing tests**

Append to `test_analytics.py`:

```python
@pytest.mark.asyncio
async def test_employee_drill_down(client, db_session):
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
    chapter = Chapter(
        id=str(uuid.uuid4()), tenant_id=tid, training_id=training.id,
        title="Quiz 1", content_type=ContentType.QUIZ,
        content_data={"max_attempts": 3, "questions": []}, order=1,
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
```

- [ ] **Step 2: Run to verify failure**

```bash
cd app/core_service && pytest tests/api/test_analytics.py::test_employee_drill_down tests/api/test_analytics.py::test_send_reminder_publishes_event -v
```
Expected: `FAILED` — 404

- [ ] **Step 3: Add the two endpoints to analytics.py**

Append to `analytics.py`:

```python
@router.get("/trainings/{training_id}/employees/{user_id}")
async def analytics_employee_detail(
    training_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """Full quiz attempt history for one employee in a training (lazy-loaded on expand)."""
    ch_q = await db.execute(
        select(Chapter).where(
            Chapter.tenant_id == tenant_id,
            Chapter.training_id == training_id,
            Chapter.content_type == ContentType.QUIZ,
            Chapter.deleted_at.is_(None),
        )
    )
    quiz_chapters = {c.id: c for c in ch_q.scalars().all()}
    if not quiz_chapters:
        return []

    att_q = await db.execute(
        select(QuizAttempt).where(
            QuizAttempt.tenant_id == tenant_id,
            QuizAttempt.user_id == user_id,
            QuizAttempt.chapter_id.in_(list(quiz_chapters.keys())),
            QuizAttempt.deleted_at.is_(None),
        ).order_by(QuizAttempt.chapter_id, QuizAttempt.attempt_number)
    )
    attempts = att_q.scalars().all()

    grouped: dict[str, list] = defaultdict(list)
    for a in attempts:
        grouped[a.chapter_id].append({
            "attempt_number": a.attempt_number,
            "score": a.score,
            "passed": a.passed,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })

    result = []
    for cid, chapter in quiz_chapters.items():
        max_allowed = (chapter.content_data or {}).get("max_attempts", 10)
        atts = grouped.get(cid, [])
        result.append({
            "chapter_id": cid,
            "chapter_title": chapter.title,
            "max_attempts": max_allowed,
            "attempts": atts,
            "is_locked": bool(atts) and max(a["attempt_number"] for a in atts) >= max_allowed and not any(a["passed"] for a in atts),
        })
    return result


@router.post("/trainings/{training_id}/send-reminder")
async def send_training_reminder(
    training_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """Send a manual on-demand training reminder to one or more employees."""
    from app.core.events import publisher

    user_ids: list[str] = body.get("user_ids", [])
    if not user_ids:
        raise HTTPException(status_code=422, detail="user_ids required")

    training = await db.get(Training, training_id)
    if not training or training.tenant_id != tenant_id or training.deleted_at:
        raise HTTPException(status_code=404, detail="Training not found")

    # Get assignment due dates
    asgn_q = await db.execute(
        select(TrainingAssignment).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.training_id == training_id,
            TrainingAssignment.user_id.in_(user_ids),
            TrainingAssignment.deleted_at.is_(None),
        )
    )
    asgn_map = {a.user_id: a for a in asgn_q.scalars().all()}
    users_data = await deps.get_users_batch(user_ids)

    for uid in user_ids:
        uinfo = users_data.get(uid, {})
        asgn = asgn_map.get(uid)
        await publisher.publish_event(
            "TRAINING_REMINDER",
            {
                "tenant_id": tenant_id,
                "user_id": uid,
                "user_email": uinfo.get("email", ""),
                "training_id": training_id,
                "training_title": training.title,
                "due_date": asgn.due_date.strftime("%B %d, %Y") if asgn and asgn.due_date else "No due date",
                "manager_name": current_user.full_name or "Your manager",
            },
        )
    return {"sent": len(user_ids)}
```

- [ ] **Step 4: Add TRAINING_REMINDER handler to notification consumer**

In `app/notification_service/app/worker/consumer.py`, add after the `COLLABORATOR_ADDED` block:

```python
    elif event_type == "TRAINING_REMINDER":
        # In-app + email to learner — manager-initiated manual reminder
        notified_user_id = payload.get("user_id")
        if notified_user_id:
            db.add(Notification(
                id=str(uuid.uuid4()),
                event_id=event_id,
                user_id=notified_user_id,
                tenant_id=payload["tenant_id"],
                title="Training Reminder",
                message=f"Reminder: please complete '{payload.get('training_title', 'your training')}'.",
                notification_type="info",
            ))
        await send_email(
            to=payload.get("user_email", ""),
            subject=f"Training Reminder: {payload.get('training_title', '')}",
            template_name="training_reminder.html",
            context={
                "training_title": payload.get("training_title"),
                "due_date": payload.get("due_date"),
                "manager_name": payload.get("manager_name"),
                "frontend_url": settings.FRONTEND_URL,
            },
        )
```

- [ ] **Step 5: Create the reminder email template**

```html
<!-- app/notification_service/app/worker/templates/training_reminder.html -->
{% extends "base.html" %}

{% block title %}Training Reminder — Training Portal{% endblock %}
{% block header_title %}Training Reminder{% endblock %}
{% block header_subtitle %}You have an outstanding training to complete{% endblock %}

{% block content %}
<p>Hi there,</p>
<p>{{ manager_name }} has sent you a reminder to complete the following training.</p>

<div class="info-box">
  <strong>Training:</strong> {{ training_title }}<br>
  <strong>Due date:</strong> {{ due_date }}
</div>

<div class="btn-wrap">
  <a href="{{ frontend_url | default('#') }}/dashboard" class="btn">Go to My Trainings</a>
</div>
{% endblock %}
```

- [ ] **Step 6: Run all analytics tests**

```bash
cd app/core_service && pytest tests/api/test_analytics.py -v
```
Expected: all `PASSED`

- [ ] **Step 7: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/analytics.py \
        app/core_service/tests/api/test_analytics.py \
        app/notification_service/app/worker/consumer.py \
        app/notification_service/app/worker/templates/training_reminder.html
git commit -m "feat(analytics): add employee drill-down, send-reminder, and TRAINING_REMINDER notification"
```

---

## Task 4: Backend — PDF and CSV report downloads

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/analytics.py`
- Modify: `app/core_service/tests/api/test_analytics.py`

- [ ] **Step 1: Write failing tests**

Append to `test_analytics.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
cd app/core_service && pytest tests/api/test_analytics.py::test_list_report_csv tests/api/test_analytics.py::test_detail_report_csv -v
```
Expected: `FAILED` — 404

- [ ] **Step 3: Add report endpoints to analytics.py**

Append to `analytics.py`:

```python
_LIST_CSV_HEADERS = [
    "Title", "Category", "Creator", "Status", "Enrolled",
    "Completed", "Completion %", "Overdue", "Lockouts", "Last Updated",
]

_DETAIL_CSV_HEADERS = [
    "Name", "Email", "Status", "Due Date", "Completed At",
    "Locked Quizzes", "Quiz Attempts Summary",
]

_LIST_REPORT_HTML = """
<!DOCTYPE html><html><head><meta charset="utf-8"/>
<style>
  body {{ font-family: sans-serif; font-size: 11px; }}
  h1 {{ font-size: 16px; margin-bottom: 4px; }}
  p.meta {{ color: #666; margin-bottom: 12px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th {{ background: #f0f0f0; border: 1px solid #ccc; padding: 4px 8px; text-align: left; }}
  td {{ border: 1px solid #ddd; padding: 4px 8px; }}
  @page {{ size: A4 landscape; margin: 1.5cm; }}
</style></head><body>
<h1>Training Analytics Report</h1>
<p class="meta">Generated {date}</p>
<table><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>
</body></html>
"""


@router.get("/report")
async def analytics_list_report(
    format: str = Query("csv", regex="^(csv|pdf)$"),
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    # Reuse list data
    from fastapi import Request
    trainings_data = await analytics_training_list.__wrapped__(db, current_user, tenant_id) \
        if hasattr(analytics_training_list, "__wrapped__") \
        else await _get_list_data(db, tenant_id)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(_LIST_CSV_HEADERS)
        for row in trainings_data:
            writer.writerow([
                row["title"], row["category"], row["creator_name"],
                "Published" if row["is_published"] else "Draft",
                row["enrolled_count"], row["completed_count"],
                row["completion_pct"], row["overdue_count"],
                row["lockout_count"], row.get("updated_at", ""),
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=training-analytics-{date_str}.csv"},
        )

    # PDF
    header_cells = "".join(f"<th>{h}</th>" for h in _LIST_CSV_HEADERS)
    body_rows = ""
    for row in trainings_data:
        cells = "".join(f"<td>{v}</td>" for v in [
            row["title"], row["category"], row["creator_name"],
            "Published" if row["is_published"] else "Draft",
            row["enrolled_count"], row["completed_count"],
            f"{row['completion_pct']}%", row["overdue_count"],
            row["lockout_count"], (row.get("updated_at") or "")[:10],
        ])
        body_rows += f"<tr>{cells}</tr>"
    html = _LIST_REPORT_HTML.format(date=date_str, headers=header_cells, rows=body_rows)
    pdf_bytes = render_certificate_pdf(html, {})
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=training-analytics-{date_str}.pdf"},
    )


@router.get("/trainings/{training_id}/report")
async def analytics_detail_report(
    training_id: str,
    format: str = Query("csv", regex="^(csv|pdf)$"),
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    detail = await analytics_training_detail(training_id, db, current_user, tenant_id)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    safe_title = detail["title"].replace(" ", "-")[:30]

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(_DETAIL_CSV_HEADERS)
        for emp in detail["employees"]:
            quiz_summary = "; ".join(
                f"{qa['attempt_count']}/{qa['max_attempts']} {'✓' if qa['passed'] else '✗'}"
                for qa in emp.get("quiz_attempts", [])
            )
            writer.writerow([
                emp["full_name"], emp["email"], emp["status"],
                emp.get("due_date", ""), emp.get("completed_at", ""),
                emp["locked_quiz_count"], quiz_summary,
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={safe_title}-analytics-{date_str}.csv"},
        )

    # PDF
    header_cells = "".join(f"<th>{h}</th>" for h in _DETAIL_CSV_HEADERS)
    body_rows = ""
    for emp in detail["employees"]:
        quiz_summary = ", ".join(
            f"{qa['attempt_count']}/{qa['max_attempts']}"
            for qa in emp.get("quiz_attempts", [])
        )
        cells = "".join(f"<td>{v}</td>" for v in [
            emp["full_name"], emp["email"], emp["status"],
            (emp.get("due_date") or "")[:10], (emp.get("completed_at") or "")[:10],
            emp["locked_quiz_count"], quiz_summary,
        ])
        body_rows += f"<tr>{cells}</tr>"
    html = _LIST_REPORT_HTML.format(
        date=date_str,
        headers=header_cells,
        rows=body_rows,
    ).replace(
        "Training Analytics Report",
        f"Analytics: {detail['title']}",
    )
    pdf_bytes = render_certificate_pdf(html, {})
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={safe_title}-analytics-{date_str}.pdf"},
    )
```

Also add a helper function `_get_list_data` that the report endpoint uses — this avoids calling the route function directly:

```python
async def _get_list_data(db: AsyncSession, tenant_id: str) -> list:
    """Extract list data from analytics_training_list without a full request context."""
    # Delegate to the same logic — inline the core queries
    return await analytics_training_list.__call__(db=db, current_user=None, tenant_id=tenant_id)
```

Actually the simpler approach: call `analytics_training_list` passing the already-resolved dependencies. Replace the report body:

```python
# In analytics_list_report, replace the trainings_data line with:
trainings_data = await analytics_training_list(db=db, current_user=current_user, tenant_id=tenant_id)
```

And in `analytics_detail_report`:
```python
detail = await analytics_training_detail(training_id=training_id, db=db, current_user=current_user, tenant_id=tenant_id)
```

Remove the `_get_list_data` helper — it's not needed.

- [ ] **Step 4: Run tests**

```bash
cd app/core_service && pytest tests/api/test_analytics.py -v
```
Expected: all `PASSED`

- [ ] **Step 5: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/analytics.py \
        app/core_service/tests/api/test_analytics.py
git commit -m "feat(analytics): add PDF and CSV report download endpoints"
```

---

## Task 5: Backend — Profile training history endpoint

**Files:**
- Modify: `app/core_service/app/api/v1/endpoints/analytics.py`
- Modify: `app/core_service/tests/api/test_analytics.py`

- [ ] **Step 1: Write failing test**

Append to `test_analytics.py`:

```python
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
```

- [ ] **Step 2: Run to see failure**

```bash
cd app/core_service && pytest tests/api/test_analytics.py::test_profile_training_history -v
```
Expected: `FAILED` — 404

- [ ] **Step 3: Implement the profile endpoint**

Append to `analytics.py`:

```python
@router.get("/profile/{user_id}")
async def analytics_profile_history(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Training history for a specific user (scoped to tenant).
    Accessible by: the user themselves, Business Managers, Training Creators, SysAdmins.
    """
    is_self = current_user.id == user_id
    is_authorized = is_self or any(
        r in ["Business Manager", "Training Creator", "SysAdmin"]
        for r in current_user.roles
    )
    if not is_authorized:
        raise HTTPException(status_code=403, detail="Not authorised to view this profile")

    now = datetime.now(timezone.utc)

    # All assignments for this user in this tenant
    asgn_q = await db.execute(
        select(TrainingAssignment).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.user_id == user_id,
            TrainingAssignment.deleted_at.is_(None),
        )
    )
    assignments = asgn_q.scalars().all()
    if not assignments:
        return []

    training_ids = [a.training_id for a in assignments]
    asgn_map = {a.training_id: a for a in assignments}

    # Trainings
    tr_q = await db.execute(
        select(Training).where(
            Training.id.in_(training_ids),
            Training.tenant_id == tenant_id,
            Training.deleted_at.is_(None),
        )
    )
    trainings = {t.id: t for t in tr_q.scalars().all()}

    # Enrollments
    enroll_q = await db.execute(
        select(Enrollment).where(
            Enrollment.tenant_id == tenant_id,
            Enrollment.user_id == user_id,
            Enrollment.training_id.in_(training_ids),
        )
    )
    enrollments = {e.training_id: e for e in enroll_q.scalars().all()}

    # Quiz counts (total chapters per training, passed chapters)
    ch_q = await db.execute(
        select(Chapter).where(
            Chapter.tenant_id == tenant_id,
            Chapter.training_id.in_(training_ids),
            Chapter.content_type == ContentType.QUIZ,
            Chapter.deleted_at.is_(None),
        )
    )
    quiz_chs = ch_q.scalars().all()
    quiz_total: dict[str, int] = defaultdict(int)
    chapter_to_tr: dict[str, str] = {}
    for c in quiz_chs:
        quiz_total[c.training_id] += 1
        chapter_to_tr[c.id] = c.training_id

    if quiz_chs:
        att_q = await db.execute(
            select(QuizAttempt.chapter_id, func.bool_or(QuizAttempt.passed))
            .where(
                QuizAttempt.tenant_id == tenant_id,
                QuizAttempt.user_id == user_id,
                QuizAttempt.chapter_id.in_(list(chapter_to_tr.keys())),
                QuizAttempt.deleted_at.is_(None),
            )
            .group_by(QuizAttempt.chapter_id)
        )
        quiz_passed_by_tr: dict[str, int] = defaultdict(int)
        for cid, passed in att_q.all():
            if passed:
                quiz_passed_by_tr[chapter_to_tr[cid]] += 1

    # Progress for "in_progress" detection
    prog_q = await db.execute(
        select(UserProgress.training_id).where(
            UserProgress.tenant_id == tenant_id,
            UserProgress.user_id == user_id,
            UserProgress.training_id.in_(training_ids),
        ).distinct()
    )
    in_progress_ids = {row[0] for row in prog_q.all()}

    result = []
    for tid_tr in training_ids:
        training = trainings.get(tid_tr)
        if not training:
            continue
        asgn = asgn_map[tid_tr]
        enroll = enrollments.get(tid_tr)

        if enroll and enroll.is_completed:
            status = "completed"
        elif asgn.due_date and asgn.due_date.replace(tzinfo=timezone.utc) < now and not (enroll and enroll.is_completed):
            status = "overdue"
        elif tid_tr in in_progress_ids:
            status = "in_progress"
        else:
            status = "not_started"

        result.append({
            "training_id": tid_tr,
            "title": training.title,
            "category": training.category,
            "status": status,
            "due_date": asgn.due_date.isoformat() if asgn.due_date else None,
            "completed_at": enroll.completed_at.isoformat() if enroll and enroll.completed_at else None,
            "quiz_total": quiz_total.get(tid_tr, 0),
            "quiz_passed": quiz_passed_by_tr.get(tid_tr, 0) if quiz_chs else 0,
            "certificate_id": enroll.certificate_id if enroll else None,
        })
    return result
```

Note: `func.bool_or` is PostgreSQL-specific. For SQLite test compatibility, replace the quiz-passed aggregation with Python-side grouping:

```python
    # Replace the bool_or query with a Python-side approach:
    if quiz_chs:
        att_q = await db.execute(
            select(QuizAttempt.chapter_id, QuizAttempt.passed).where(
                QuizAttempt.tenant_id == tenant_id,
                QuizAttempt.user_id == user_id,
                QuizAttempt.chapter_id.in_(list(chapter_to_tr.keys())),
                QuizAttempt.deleted_at.is_(None),
            )
        )
        quiz_passed_by_tr: dict[str, int] = defaultdict(int)
        passed_chapters: set[str] = set()
        for cid, passed in att_q.all():
            if passed and cid not in passed_chapters:
                passed_chapters.add(cid)
                quiz_passed_by_tr[chapter_to_tr[cid]] += 1
    else:
        quiz_passed_by_tr = defaultdict(int)
```

- [ ] **Step 4: Run all analytics tests**

```bash
cd app/core_service && pytest tests/api/test_analytics.py -v
```
Expected: all `PASSED`

- [ ] **Step 5: Commit**

```bash
git add app/core_service/app/api/v1/endpoints/analytics.py \
        app/core_service/tests/api/test_analytics.py
git commit -m "feat(analytics): add profile training history endpoint"
```

---

## Task 6: Frontend — API client

**Files:**
- Create: `app/frontend/src/api/analytics.ts`

- [ ] **Step 1: Create the API client**

```typescript
// app/frontend/src/api/analytics.ts
import { client } from './client';

export interface TrainingListItem {
  id: string;
  title: string;
  category: string;
  is_published: boolean;
  creator_id: string | null;
  creator_name: string;
  updated_at: string | null;
  enrolled_count: number;
  completed_count: number;
  completion_pct: number;
  overdue_count: number;
  lockout_count: number;
}

export interface QuizChapterStat {
  chapter_id: string;
  chapter_title: string;
  max_attempts: number;
  attempted_count: number;
  pass_count: number;
  pass_rate: number;
  avg_score: number;
  avg_attempts_to_pass: number;
  locked_count: number;
}

export interface EmployeeQuizAttempt {
  chapter_id: string;
  attempt_count: number;
  max_attempts: number;
  passed: boolean;
}

export interface EmployeeSummary {
  user_id: string;
  username: string;
  full_name: string;
  email: string;
  status: 'completed' | 'in_progress' | 'overdue' | 'not_started' | 'locked';
  due_date: string | null;
  completed_at: string | null;
  locked_quiz_count: number;
  quiz_attempts: EmployeeQuizAttempt[];
}

export interface TrainingDetailAnalytics {
  training_id: string;
  title: string;
  category: string;
  is_published: boolean;
  creator_name: string;
  enrolled_count: number;
  completed_count: number;
  completion_pct: number;
  overdue_count: number;
  lockout_count: number;
  due_soon_7d: number;
  due_soon_14d: number;
  due_soon_30d: number;
  quiz_chapters: QuizChapterStat[];
  employees: EmployeeSummary[];
}

export interface EmployeeAttemptDetail {
  chapter_id: string;
  chapter_title: string;
  max_attempts: number;
  attempts: { attempt_number: number; score: number; passed: boolean; created_at: string | null }[];
  is_locked: boolean;
}

export interface ProfileTrainingItem {
  training_id: string;
  title: string;
  category: string;
  status: 'completed' | 'in_progress' | 'overdue' | 'not_started';
  due_date: string | null;
  completed_at: string | null;
  quiz_total: number;
  quiz_passed: number;
  certificate_id: string | null;
}

export const analyticsApi = {
  getTrainingList: () =>
    client.get<TrainingListItem[]>('/analytics/trainings'),

  getTrainingDetail: (trainingId: string) =>
    client.get<TrainingDetailAnalytics>(`/analytics/trainings/${trainingId}`),

  getEmployeeDetail: (trainingId: string, userId: string) =>
    client.get<EmployeeAttemptDetail[]>(`/analytics/trainings/${trainingId}/employees/${userId}`),

  sendReminder: (trainingId: string, userIds: string[]) =>
    client.post<{ sent: number }>(`/analytics/trainings/${trainingId}/send-reminder`, { user_ids: userIds }),

  getProfileHistory: (userId: string) =>
    client.get<ProfileTrainingItem[]>(`/analytics/profile/${userId}`),

  getListReportUrl: (format: 'pdf' | 'csv') =>
    `/api/v1/analytics/report?format=${format}`,

  getDetailReportUrl: (trainingId: string, format: 'pdf' | 'csv') =>
    `/api/v1/analytics/trainings/${trainingId}/report?format=${format}`,
};
```

- [ ] **Step 2: Run lint**

```bash
cd app/frontend && npm run lint
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add app/frontend/src/api/analytics.ts
git commit -m "feat(analytics): add frontend analytics API client"
```

---

## Task 7: Frontend — Routes, sidebar, and dashboard lockout card

**Files:**
- Modify: `app/frontend/src/App.tsx`
- Modify: `app/frontend/src/components/layout/Sidebar.tsx`
- Modify: `app/frontend/src/pages/ManagerDashboard.tsx`

- [ ] **Step 1: Add routes to App.tsx**

In `App.tsx`, find the `/manage` route block and add after the `reports` route:

```tsx
// Add import at top of file
import { ManagerAnalytics } from './pages/ManagerAnalytics';
import { ManagerAnalyticsDetail } from './pages/ManagerAnalyticsDetail';

// Inside the /manage Routes block, after the reports route:
<Route path="analytics" element={<AuthGuard requireBusinessManager><ManagerAnalytics /></AuthGuard>} />
<Route path="analytics/:trainingId" element={<AuthGuard requireBusinessManager><ManagerAnalyticsDetail /></AuthGuard>} />
```

Note: `ManagerAnalytics` and `ManagerAnalyticsDetail` pages don't exist yet — they'll be created in Tasks 8 and 9. The app will fail to build until those tasks are done. Create stub files now:

```tsx
// app/frontend/src/pages/ManagerAnalytics.tsx (stub)
export function ManagerAnalytics() { return <div>Analytics List</div>; }
```

```tsx
// app/frontend/src/pages/ManagerAnalyticsDetail.tsx (stub)
export function ManagerAnalyticsDetail() { return <div>Analytics Detail</div>; }
```

- [ ] **Step 2: Add Analytics nav item to Sidebar**

In `app/frontend/src/components/layout/Sidebar.tsx`, find the `MANAGEMENT_LINKS` array and add after the Reports entry:

```tsx
{ to: '/manage/analytics', icon: TrendingUp, label: 'Analytics' },
```

Import `TrendingUp` from `lucide-react` (add to the existing lucide import line).

- [ ] **Step 3: Add Quiz Lockouts card to ManagerDashboard**

In `app/frontend/src/pages/ManagerDashboard.tsx`:

1. Import `useManagerDashboard` from the queries:

```tsx
import { useManagerDashboard } from '../queries/dashboards';
```

2. Inside the component, add:

```tsx
const { data: dashboardData } = useManagerDashboard();
const lockoutCount = dashboardData?.quiz_lockouts ?? 0;
```

3. Add a fourth metric card inside the metrics grid (after the Draft Trainings card), visible only to managers:

```tsx
{isManager && (
  <Card
    className={cn(
      'border-border/50 shadow-sm cursor-pointer transition-colors',
      lockoutCount > 0 ? 'border-destructive/40 hover:border-destructive/60' : 'hover:border-border'
    )}
    onClick={() => navigate('/manage/analytics')}
  >
    <CardContent className="p-6">
      <p className={cn(
        'text-sm font-medium mb-1',
        lockoutCount > 0 ? 'text-destructive' : 'text-muted-foreground'
      )}>
        Quiz Lockouts
      </p>
      <div className="flex items-baseline gap-3">
        <p className={cn('text-3xl font-bold', lockoutCount > 0 ? 'text-destructive' : '')}>
          {isLoading ? '—' : lockoutCount}
        </p>
        <AlertCircle className={cn('w-4 h-4', lockoutCount > 0 ? 'text-destructive' : 'text-muted-foreground')} />
      </div>
      {lockoutCount > 0 && (
        <p className="text-xs text-destructive mt-1">Click to view → Analytics</p>
      )}
    </CardContent>
  </Card>
)}
```

- [ ] **Step 4: Run lint**

```bash
cd app/frontend && npm run lint
```
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add app/frontend/src/App.tsx \
        app/frontend/src/components/layout/Sidebar.tsx \
        app/frontend/src/pages/ManagerDashboard.tsx \
        app/frontend/src/pages/ManagerAnalytics.tsx \
        app/frontend/src/pages/ManagerAnalyticsDetail.tsx
git commit -m "feat(analytics): add routes, sidebar nav, and dashboard lockout card"
```

---

## Task 8: Frontend — ManagerAnalytics list page

**Files:**
- Modify: `app/frontend/src/pages/ManagerAnalytics.tsx` (replace stub)

- [ ] **Step 1: Implement the list page**

```tsx
// app/frontend/src/pages/ManagerAnalytics.tsx
import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { analyticsApi, type TrainingListItem } from '../api/analytics';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { PageLoader } from '../components/ui/PageLoader';
import { AlertCircle, BarChart3, Download, FileText } from 'lucide-react';
import { cn } from '../lib/utils';

type StatusFilter = 'all' | 'published' | 'draft';

export function ManagerAnalytics() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<StatusFilter>('all');
  const [creator, setCreator] = useState('');
  const [category, setCategory] = useState('');

  const { data: trainings = [], isLoading, isError } = useQuery({
    queryKey: ['analytics', 'list'],
    queryFn: analyticsApi.getTrainingList,
  });

  const creators = useMemo(
    () => Array.from(new Set(trainings.map(t => t.creator_name).filter(Boolean))).sort(),
    [trainings]
  );
  const categories = useMemo(
    () => Array.from(new Set(trainings.map(t => t.category).filter(Boolean))).sort(),
    [trainings]
  );

  const filtered = useMemo(() => {
    return trainings.filter(t => {
      if (search && !t.title.toLowerCase().includes(search.toLowerCase())) return false;
      if (status === 'published' && !t.is_published) return false;
      if (status === 'draft' && t.is_published) return false;
      if (creator && t.creator_name !== creator) return false;
      if (category && t.category !== category) return false;
      return true;
    });
  }, [trainings, search, status, creator, category]);

  const handleDownload = (format: 'pdf' | 'csv') => {
    window.open(analyticsApi.getListReportUrl(format), '_blank');
  };

  if (isLoading) return <PageLoader />;
  if (isError) return (
    <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
      <AlertCircle className="h-8 w-8 text-destructive" />
      <p className="text-sm">Failed to load analytics.</p>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
              <BarChart3 className="w-6 h-6 text-primary" />
            </div>
            Training Analytics
          </h1>
          <p className="text-muted-foreground mt-1">
            Select a training to view completion stats, quiz performance, and employee progress.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => handleDownload('csv')}>
            <Download className="h-4 w-4 mr-1" /> CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleDownload('pdf')}>
            <FileText className="h-4 w-4 mr-1" /> PDF
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <Input
          placeholder="Search trainings…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="max-w-xs h-9"
        />
        <select
          value={status}
          onChange={e => setStatus(e.target.value as StatusFilter)}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">All Statuses</option>
          <option value="published">Published</option>
          <option value="draft">Draft</option>
        </select>
        <select
          value={creator}
          onChange={e => setCreator(e.target.value)}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All Creators</option>
          {creators.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select
          value={category}
          onChange={e => setCategory(e.target.value)}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All Categories</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      <Card>
        <CardHeader className="border-b border-border/50 pb-3">
          <CardTitle className="text-base">
            {filtered.length} training{filtered.length !== 1 ? 's' : ''}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-sm">No trainings match the current filters.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Creator</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Enrolled</TableHead>
                  <TableHead className="text-right">Completion %</TableHead>
                  <TableHead className="text-right">Overdue</TableHead>
                  <TableHead className="text-right">Lockouts</TableHead>
                  <TableHead className="text-right">Last Updated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map(t => (
                  <TableRow
                    key={t.id}
                    className="cursor-pointer hover:bg-muted/30"
                    onClick={() => navigate(`/manage/analytics/${t.id}`)}
                  >
                    <TableCell className="font-medium">{t.title}</TableCell>
                    <TableCell className="text-muted-foreground">{t.creator_name || '—'}</TableCell>
                    <TableCell className="text-muted-foreground">{t.category}</TableCell>
                    <TableCell>
                      <Badge className={cn(
                        t.is_published
                          ? 'bg-primary/10 text-primary border-primary/20'
                          : 'bg-muted text-muted-foreground border-border'
                      )}>
                        {t.is_published ? 'Published' : 'Draft'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">{t.enrolled_count}</TableCell>
                    <TableCell className="text-right">{t.completion_pct}%</TableCell>
                    <TableCell className="text-right">
                      {t.overdue_count > 0
                        ? <span className="text-destructive font-medium">{t.overdue_count}</span>
                        : t.overdue_count}
                    </TableCell>
                    <TableCell className="text-right">
                      {t.lockout_count > 0
                        ? <Badge className="bg-destructive/10 text-destructive border-destructive/20">{t.lockout_count}</Badge>
                        : <span className="text-muted-foreground">0</span>}
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground text-sm">
                      {t.updated_at ? new Date(t.updated_at).toLocaleDateString() : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Run lint**

```bash
cd app/frontend && npm run lint
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add app/frontend/src/pages/ManagerAnalytics.tsx
git commit -m "feat(analytics): implement analytics list page"
```

---

## Task 9: Frontend — ManagerAnalyticsDetail page

**Files:**
- Modify: `app/frontend/src/pages/ManagerAnalyticsDetail.tsx` (replace stub)

- [ ] **Step 1: Implement the detail page**

```tsx
// app/frontend/src/pages/ManagerAnalyticsDetail.tsx
import { useState, useMemo, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { analyticsApi, type EmployeeAttemptDetail, type EmployeeSummary } from '../api/analytics';
import { managerTrainingsApi } from '../api/trainings';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { PageLoader } from '../components/ui/PageLoader';
import {
  AlertCircle, ArrowLeft, BarChart3, CheckCircle2, ChevronDown, ChevronRight,
  Clock, Download, FileText, RotateCcw, Send, Users, XCircle,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../lib/utils';

type StatusFilter = 'all' | 'completed' | 'in_progress' | 'overdue' | 'not_started' | 'locked';
type DueSoonWindow = 7 | 14 | 30;

const STATUS_LABELS: Record<string, string> = {
  completed: 'Completed',
  in_progress: 'In Progress',
  overdue: 'Overdue',
  not_started: 'Not Started',
  locked: 'Locked',
};

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: 'bg-primary/10 text-primary border-primary/20',
    in_progress: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
    overdue: 'bg-destructive/10 text-destructive border-destructive/20',
    not_started: 'bg-muted text-muted-foreground border-border',
    locked: 'bg-orange-500/10 text-orange-600 border-orange-500/20',
  };
  return (
    <Badge className={cn(colors[status] ?? 'bg-muted text-muted-foreground')}>
      {STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

function EmployeeDrillDown({ trainingId, userId }: { trainingId: string; userId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['analytics', 'employee-detail', trainingId, userId],
    queryFn: () => analyticsApi.getEmployeeDetail(trainingId, userId),
  });

  if (isLoading) return <div className="px-4 py-3 text-sm text-muted-foreground">Loading attempts…</div>;
  if (!data?.length) return <div className="px-4 py-3 text-sm text-muted-foreground">No quiz attempts recorded.</div>;

  return (
    <div className="px-4 py-3 bg-muted/20 space-y-3">
      {data.map(ch => (
        <div key={ch.chapter_id}>
          <p className="text-sm font-medium mb-1">
            {ch.chapter_title}
            {ch.is_locked && <span className="ml-2 text-xs text-orange-600">(locked)</span>}
            <span className="ml-2 text-xs text-muted-foreground">max {ch.max_attempts} attempts</span>
          </p>
          <div className="flex gap-3 flex-wrap">
            {ch.attempts.map(a => (
              <div key={a.attempt_number} className={cn(
                'text-xs rounded px-2 py-1 border',
                a.passed
                  ? 'bg-primary/10 text-primary border-primary/20'
                  : 'bg-muted text-muted-foreground border-border'
              )}>
                #{a.attempt_number} — {a.score.toFixed(0)}% {a.passed ? '✓' : '✗'}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function ManagerAnalyticsDetail() {
  const { trainingId } = useParams<{ trainingId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [search, setSearch] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [dueSoonWindow, setDueSoonWindow] = useState<DueSoonWindow>(7);
  const [reminderLoading, setReminderLoading] = useState<string | null>(null);
  const [resettingKey, setResettingKey] = useState('');

  // Warning threshold from localStorage, default 1
  const thresholdKey = `analytics_warning_threshold_${trainingId}`;
  const [warningThreshold, setWarningThreshold] = useState<number>(() => {
    const saved = localStorage.getItem(thresholdKey);
    return saved ? Math.max(1, parseInt(saved, 10)) : 1;
  });
  useEffect(() => {
    localStorage.setItem(thresholdKey, String(warningThreshold));
  }, [warningThreshold, thresholdKey]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['analytics', 'detail', trainingId],
    queryFn: () => analyticsApi.getTrainingDetail(trainingId!),
    enabled: !!trainingId,
  });

  // Load lockout summary (reuses existing trainings endpoint)
  const { data: lockoutSummary = [], refetch: refetchLockouts } = useQuery({
    queryKey: ['quiz-lockouts', trainingId],
    queryFn: () => managerTrainingsApi.getQuizAttemptsSummary(trainingId!),
    enabled: !!trainingId,
  });

  const employees = useMemo(() => {
    if (!data) return [];
    return data.employees.filter(emp => {
      if (statusFilter !== 'all' && emp.status !== statusFilter) return false;
      if (search && !emp.full_name.toLowerCase().includes(search.toLowerCase()) &&
          !emp.email.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    }).map(emp => {
      const approaching = emp.quiz_attempts.filter(qa =>
        !qa.passed &&
        qa.attempt_count < qa.max_attempts &&
        qa.attempt_count >= qa.max_attempts - warningThreshold
      ).length;
      return { ...emp, approaching_count: approaching };
    });
  }, [data, statusFilter, search, warningThreshold]);

  const toggleRow = (userId: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      next.has(userId) ? next.delete(userId) : next.add(userId);
      return next;
    });
  };

  const handleSendReminder = async (userId: string) => {
    if (!trainingId) return;
    setReminderLoading(userId);
    try {
      await analyticsApi.sendReminder(trainingId, [userId]);
      toast.success('Reminder sent');
    } catch {
      toast.error('Failed to send reminder');
    } finally {
      setReminderLoading(null);
    }
  };

  const handleReset = async (chapterId: string, userId: string) => {
    if (!trainingId) return;
    const key = `${chapterId}:${userId}`;
    setResettingKey(key);
    try {
      await managerTrainingsApi.resetUserQuizAttempts(trainingId, chapterId, userId);
      toast.success('Quiz attempts reset');
      refetchLockouts();
      queryClient.invalidateQueries({ queryKey: ['analytics', 'detail', trainingId] });
    } catch {
      toast.error('Failed to reset attempts');
    } finally {
      setResettingKey('');
    }
  };

  const handleDownload = (format: 'pdf' | 'csv') => {
    if (trainingId) window.open(analyticsApi.getDetailReportUrl(trainingId, format), '_blank');
  };

  if (isLoading) return <PageLoader />;
  if (isError || !data) return (
    <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
      <AlertCircle className="h-8 w-8 text-destructive" />
      <p className="text-sm">Failed to load analytics.</p>
    </div>
  );

  const dueSoonCount = dueSoonWindow === 7
    ? data.due_soon_7d
    : dueSoonWindow === 14 ? data.due_soon_14d : data.due_soon_30d;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <button
            onClick={() => navigate('/manage/analytics')}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-2"
          >
            <ArrowLeft className="h-4 w-4" /> Back to Analytics
          </button>
          <h1 className="text-2xl font-bold tracking-tight">{data.title}</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            {data.category} · {data.creator_name}
            <Badge className={cn('ml-2 text-xs', data.is_published ? 'bg-primary/10 text-primary border-primary/20' : 'bg-muted text-muted-foreground')}>
              {data.is_published ? 'Published' : 'Draft'}
            </Badge>
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={() => handleDownload('csv')}>
            <Download className="h-4 w-4 mr-1" /> CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleDownload('pdf')}>
            <FileText className="h-4 w-4 mr-1" /> PDF
          </Button>
        </div>
      </div>

      {/* Overview stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Card><CardContent className="p-4">
          <p className="text-xs text-muted-foreground">Enrolled</p>
          <p className="text-2xl font-bold mt-1">{data.enrolled_count}</p>
        </CardContent></Card>

        <Card><CardContent className="p-4">
          <p className="text-xs text-muted-foreground">Completion</p>
          <p className="text-2xl font-bold mt-1 text-primary">{data.completion_pct}%</p>
          <p className="text-xs text-muted-foreground">{data.completed_count} completed</p>
        </CardContent></Card>

        <Card><CardContent className="p-4">
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            Due Soon
            <select
              value={dueSoonWindow}
              onChange={e => setDueSoonWindow(Number(e.target.value) as DueSoonWindow)}
              className="ml-1 text-xs border rounded px-1 bg-background"
              onClick={e => e.stopPropagation()}
            >
              <option value={7}>7d</option>
              <option value={14}>14d</option>
              <option value={30}>30d</option>
            </select>
          </p>
          <p className={cn('text-2xl font-bold mt-1', dueSoonCount > 0 ? 'text-amber-600' : '')}>
            {dueSoonCount}
          </p>
        </CardContent></Card>

        <Card><CardContent className="p-4">
          <p className="text-xs text-muted-foreground">Overdue</p>
          <p className={cn('text-2xl font-bold mt-1', data.overdue_count > 0 ? 'text-destructive' : '')}>
            {data.overdue_count}
          </p>
        </CardContent></Card>

        <Card
          className={cn('cursor-pointer', data.lockout_count > 0 ? 'border-destructive/40' : '')}
          onClick={() => setStatusFilter('locked')}
        >
          <CardContent className="p-4">
            <p className={cn('text-xs', data.lockout_count > 0 ? 'text-destructive' : 'text-muted-foreground')}>
              Quiz Lockouts
            </p>
            <p className={cn('text-2xl font-bold mt-1', data.lockout_count > 0 ? 'text-destructive' : '')}>
              {data.lockout_count}
            </p>
            {data.lockout_count > 0 && <p className="text-xs text-destructive">Click to filter ↓</p>}
          </CardContent>
        </Card>
      </div>

      {/* Quiz Performance */}
      {data.quiz_chapters.length > 0 && (
        <Card>
          <CardHeader className="border-b border-border/50 pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-primary" /> Quiz Performance
              </CardTitle>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                Warning threshold:
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={warningThreshold}
                  onChange={e => setWarningThreshold(Math.max(1, parseInt(e.target.value, 10) || 1))}
                  className="w-14 h-7 text-center border rounded text-sm bg-background"
                />
                attempts remaining
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Quiz</TableHead>
                  <TableHead className="text-right">Attempted</TableHead>
                  <TableHead className="text-right">Pass Rate</TableHead>
                  <TableHead className="text-right">Avg Score</TableHead>
                  <TableHead className="text-right">Avg Attempts to Pass</TableHead>
                  <TableHead className="text-right">Locked</TableHead>
                  <TableHead className="text-right">Approaching</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.quiz_chapters.map(ch => {
                  const approachingCount = data.employees.filter(emp =>
                    emp.quiz_attempts.some(qa =>
                      qa.chapter_id === ch.chapter_id &&
                      !qa.passed &&
                      qa.attempt_count < qa.max_attempts &&
                      qa.attempt_count >= qa.max_attempts - warningThreshold
                    )
                  ).length;
                  return (
                    <TableRow key={ch.chapter_id}>
                      <TableCell className="font-medium">{ch.chapter_title}</TableCell>
                      <TableCell className="text-right">{ch.attempted_count}</TableCell>
                      <TableCell className="text-right">
                        <span className={cn(ch.pass_rate < 60 ? 'text-destructive' : 'text-primary')}>
                          {ch.pass_rate}%
                        </span>
                      </TableCell>
                      <TableCell className="text-right">{ch.avg_score}%</TableCell>
                      <TableCell className="text-right">{ch.avg_attempts_to_pass || '—'}</TableCell>
                      <TableCell className="text-right">
                        {ch.locked_count > 0
                          ? <span className="text-destructive font-medium">{ch.locked_count}</span>
                          : <span className="text-muted-foreground">0</span>}
                      </TableCell>
                      <TableCell className="text-right">
                        {approachingCount > 0
                          ? <span className="text-amber-600 font-medium">{approachingCount}</span>
                          : <span className="text-muted-foreground">0</span>}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Employee Status Table */}
      <Card>
        <CardHeader className="border-b border-border/50 pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Users className="h-4 w-4 text-primary" /> Employee Status
          </CardTitle>
          <div className="flex flex-wrap gap-3 mt-2">
            <Input
              placeholder="Search by name or email…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="max-w-xs h-8 text-sm"
            />
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value as StatusFilter)}
              className="h-8 rounded-md border border-input bg-background px-3 text-sm focus:outline-none"
            >
              <option value="all">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="in_progress">In Progress</option>
              <option value="overdue">Overdue</option>
              <option value="not_started">Not Started</option>
              <option value="locked">Locked</option>
            </select>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {employees.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-sm">No employees match the current filters.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8"></TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Due Date</TableHead>
                  <TableHead>Completed</TableHead>
                  <TableHead className="text-right">Locked</TableHead>
                  <TableHead className="text-right">Approaching</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {employees.map(emp => {
                  const isExpanded = expandedRows.has(emp.user_id);
                  const canRemind = ['in_progress', 'overdue', 'not_started'].includes(emp.status);
                  return (
                    <>
                      <TableRow key={emp.user_id} className="hover:bg-muted/20">
                        <TableCell>
                          <button
                            onClick={() => toggleRow(emp.user_id)}
                            className="text-muted-foreground hover:text-foreground"
                          >
                            {isExpanded
                              ? <ChevronDown className="h-4 w-4" />
                              : <ChevronRight className="h-4 w-4" />}
                          </button>
                        </TableCell>
                        <TableCell>
                          <div>
                            <Link
                              to={`/profile/${emp.username}`}
                              className="text-sm font-medium hover:text-primary hover:underline"
                              onClick={e => e.stopPropagation()}
                            >
                              {emp.full_name || emp.email}
                            </Link>
                            <p className="text-xs text-muted-foreground">{emp.email}</p>
                          </div>
                        </TableCell>
                        <TableCell><StatusBadge status={emp.status} /></TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {emp.due_date ? new Date(emp.due_date).toLocaleDateString() : '—'}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {emp.completed_at ? new Date(emp.completed_at).toLocaleDateString() : '—'}
                        </TableCell>
                        <TableCell className="text-right">
                          {emp.locked_quiz_count > 0
                            ? <span className="text-destructive font-medium">{emp.locked_quiz_count}</span>
                            : <span className="text-muted-foreground">0</span>}
                        </TableCell>
                        <TableCell className="text-right">
                          {(emp as typeof emp & { approaching_count: number }).approaching_count > 0
                            ? <span className="text-amber-600 font-medium">{(emp as typeof emp & { approaching_count: number }).approaching_count}</span>
                            : <span className="text-muted-foreground">0</span>}
                        </TableCell>
                        <TableCell className="text-right">
                          {canRemind && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 text-xs"
                              disabled={reminderLoading === emp.user_id}
                              onClick={() => handleSendReminder(emp.user_id)}
                            >
                              <Send className="h-3 w-3 mr-1" />
                              {reminderLoading === emp.user_id ? 'Sending…' : 'Remind'}
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                      {isExpanded && (
                        <TableRow key={`${emp.user_id}-detail`}>
                          <TableCell colSpan={8} className="p-0">
                            <EmployeeDrillDown trainingId={trainingId!} userId={emp.user_id} />
                          </TableCell>
                        </TableRow>
                      )}
                    </>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Lockout Management — reset section */}
      {lockoutSummary.length > 0 && (
        <Card>
          <CardHeader className="border-b border-border/50 pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-destructive" /> Lockout Management
            </CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              Reset quiz attempts for locked-out employees.
            </p>
          </CardHeader>
          <CardContent className="pt-4 space-y-4">
            {lockoutSummary.map(chapter => (
              <div key={chapter.chapter_id}>
                <p className="text-sm font-medium mb-2">
                  {chapter.chapter_title}
                  <span className="ml-2 text-xs text-muted-foreground">(max {chapter.max_attempts} attempts)</span>
                </p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Employee</TableHead>
                      <TableHead>Attempts</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {chapter.users_at_limit.map(u => {
                      const key = `${chapter.chapter_id}:${u.user_id}`;
                      return (
                        <TableRow key={u.user_id}>
                          <TableCell>
                            <div className="flex flex-col">
                              <span className="text-sm font-medium">{u.name}</span>
                              <span className="text-xs text-muted-foreground">{u.email}</span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <span className="text-sm text-destructive font-medium">
                              {u.attempts} / {chapter.max_attempts}
                            </span>
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={resettingKey === key}
                              onClick={() => handleReset(chapter.chapter_id, u.user_id)}
                              className="h-7 text-xs"
                            >
                              <RotateCcw className="h-3 w-3 mr-1" />
                              {resettingKey === key ? 'Resetting…' : 'Reset'}
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Run lint**

```bash
cd app/frontend && npm run lint
```
Fix any errors before proceeding.

- [ ] **Step 3: Commit**

```bash
git add app/frontend/src/pages/ManagerAnalyticsDetail.tsx
git commit -m "feat(analytics): implement analytics detail page with quiz stats, employee table, drill-down, and lockout management"
```

---

## Task 10: Frontend — ProfilePage Trainings tab

**Files:**
- Modify: `app/frontend/src/pages/ProfilePage.tsx`

- [ ] **Step 1: Add the Trainings tab**

In `ProfilePage.tsx`:

1. Add the import at top:

```tsx
import { analyticsApi, type ProfileTrainingItem } from '../api/analytics';
```

2. Add state for the profile training history (inside the component):

```tsx
const [profileTrainings, setProfileTrainings] = useState<ProfileTrainingItem[]>([]);
const [loadingTrainings, setLoadingTrainings] = useState(false);
```

3. Add a `useEffect` that loads when the "trainings" tab is selected:

```tsx
const handleTrainingsTabActivate = async () => {
  if (!user || loadingTrainings || profileTrainings.length > 0) return;
  setLoadingTrainings(true);
  try {
    const data = await analyticsApi.getProfileHistory(user.id);
    setProfileTrainings(data);
  } catch {
    // silently fail — tab shows empty state
  } finally {
    setLoadingTrainings(false);
  }
};
```

4. Add the `"trainings"` tab trigger in the `<TabsList>`:

```tsx
<TabsTrigger
  value="trainings"
  onClick={handleTrainingsTabActivate}
  className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-0 h-12 font-semibold"
>
  Trainings
</TabsTrigger>
```

5. Add the `<TabsContent value="trainings">` block after the Activity tab content:

```tsx
<TabsContent value="trainings" className="pt-6">
  <Card>
    <CardHeader>
      <CardTitle>Training History</CardTitle>
      <CardDescription>All assigned trainings and their completion status</CardDescription>
    </CardHeader>
    <CardContent className="p-0">
      {loadingTrainings ? (
        <div className="p-8 flex justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : profileTrainings.length === 0 ? (
        <div className="p-8 text-center text-muted-foreground text-sm italic">
          No trainings assigned.
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Training</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Due Date</TableHead>
              <TableHead>Completed</TableHead>
              <TableHead>Quizzes</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {profileTrainings.map(t => (
              <TableRow key={t.training_id}>
                <TableCell className="font-medium">{t.title}</TableCell>
                <TableCell className="text-muted-foreground text-sm">{t.category}</TableCell>
                <TableCell>
                  <Badge className={cn({
                    'bg-primary/10 text-primary border-primary/20': t.status === 'completed',
                    'bg-blue-500/10 text-blue-600 border-blue-500/20': t.status === 'in_progress',
                    'bg-destructive/10 text-destructive border-destructive/20': t.status === 'overdue',
                    'bg-muted text-muted-foreground border-border': t.status === 'not_started',
                  })}>
                    {{ completed: 'Completed', in_progress: 'In Progress', overdue: 'Overdue', not_started: 'Not Started' }[t.status]}
                  </Badge>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {t.due_date ? new Date(t.due_date).toLocaleDateString() : '—'}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {t.completed_at ? new Date(t.completed_at).toLocaleDateString() : '—'}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {t.quiz_total > 0 ? `${t.quiz_passed}/${t.quiz_total} passed` : '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </CardContent>
  </Card>
</TabsContent>
```

6. Also add `Table, TableBody, TableCell, TableHead, TableHeader, TableRow` to the existing shadcn/ui imports from `../components/ui/table` if not already present.

7. Replace the "In Progress Trainings" card placeholder text in the Overview tab with a prompt:

Find this block in the overview tab:
```tsx
<div className="flex items-center justify-center h-20 border border-dashed rounded-lg bg-muted/30">
  <p className="text-sm text-muted-foreground">Loading course details...</p>
</div>
```
Replace with:
```tsx
<div className="flex items-center justify-center h-20 border border-dashed rounded-lg bg-muted/30">
  <p className="text-sm text-muted-foreground">
    See the <button onClick={() => {}} className="underline text-primary">Trainings tab</button> for full history.
  </p>
</div>
```

- [ ] **Step 2: Run lint**

```bash
cd app/frontend && npm run lint
```

- [ ] **Step 3: Commit**

```bash
git add app/frontend/src/pages/ProfilePage.tsx
git commit -m "feat(analytics): add Trainings tab to ProfilePage with cross-training history"
```

---

## Task 11: Frontend — ManagerEmployees clickable rows

**Files:**
- Modify: `app/frontend/src/pages/ManagerEmployees.tsx`

- [ ] **Step 1: Read the current file to find the employee row**

```bash
grep -n "TableRow\|onClick\|navigate\|cursor" app/frontend/src/pages/ManagerEmployees.tsx | head -20
```

- [ ] **Step 2: Make rows clickable**

1. Add `useNavigate` import if not present:
```tsx
import { useNavigate } from 'react-router-dom';
```

2. Add inside the component:
```tsx
const navigate = useNavigate();
```

3. Find the `<TableRow>` that renders each employee and add `onClick` and cursor:
```tsx
<TableRow
  key={emp.id}
  className="cursor-pointer hover:bg-muted/30"
  onClick={() => navigate(`/profile/${emp.username}`)}
>
```

Note: `emp.username` must be available on the `User` type from `../api/users`. Verify by checking the `User` interface in `users.ts`. It already has `username: string | null` — use `emp.username ?? emp.id` as fallback if username is null.

- [ ] **Step 3: Run lint**

```bash
cd app/frontend && npm run lint
```

- [ ] **Step 4: Commit**

```bash
git add app/frontend/src/pages/ManagerEmployees.tsx
git commit -m "feat(analytics): make employee rows clickable to profile page"
```

---

## Task 12: Verify auth service batch endpoint returns username

**This is a dependency verification step** — the analytics employee list passes usernames to the frontend for profile links. The `get_users_batch` call in `deps.py` calls `/api/v1/users/internal/batch` on the auth service.

- [ ] **Step 1: Check the auth service batch endpoint**

```bash
grep -rn "internal/batch\|batch\|username" app/auth_service/ --include="*.py" | grep -v "__pycache__" | head -30
```

- [ ] **Step 2: Verify or add username to the response**

If the endpoint returns `{"full_name": ..., "email": ...}` but NOT `username`, find the handler and add it:

```python
# In auth_service, find the /internal/batch endpoint handler
# Ensure each user dict includes "username":
return {
    str(user.id): {
        "full_name": user.full_name,
        "email": user.email,
        "username": user.username,  # add this
    }
    for user in users
}
```

- [ ] **Step 3: Run the auth service tests to verify no regression**

```bash
docker compose exec auth-service pytest tests/ -v -x
```

- [ ] **Step 4: Commit if changed**

```bash
# Only if the auth service file was modified:
git add app/auth_service/
git commit -m "feat(analytics): include username in users internal batch response"
```

---

## Task 13: Integration smoke test

Run the full stack and verify the golden paths work in the browser.

- [ ] **Step 1: Start the stack**

```bash
docker compose up --build
```

- [ ] **Step 2: Verify backend endpoints**

```bash
# Get a manager token (log in via the UI, copy from browser DevTools Network tab)
TOKEN="<paste token here>"

curl -s -H "Authorization: Bearer $TOKEN" http://localhost/api/v1/analytics/trainings | python3 -m json.tool | head -40
```
Expected: JSON array of training objects with `enrolled_count`, `completion_pct`, etc.

- [ ] **Step 3: Verify frontend golden path**

1. Log in as a Business Manager
2. Sidebar shows "Analytics" under Management
3. Click "Analytics" → list page loads with training table
4. Click a training row → detail page loads with stat cards and employee table
5. Expand an employee row → quiz attempt history appears
6. Click "Remind" on an overdue employee → success toast appears
7. Click employee name → navigates to `/profile/:username`
8. Profile page has a "Trainings" tab → click it → training history loads
9. Manager Dashboard shows "Quiz Lockouts" card → if > 0, it's red and clickable
10. Download CSV from list page → file downloads
11. Download PDF from detail page → PDF opens in new tab

- [ ] **Step 4: Run lint one final time**

```bash
cd app/frontend && npm run lint
```

- [ ] **Step 5: Run backend tests**

```bash
docker compose exec core-service pytest tests/api/test_analytics.py -v
```

---

## Notes for Implementer

**`Integer` import in analytics.py:** The list endpoint uses `QuizAttempt.passed.cast(Integer)`. Import `Integer` from SQLAlchemy:
```python
from sqlalchemy import Integer, func, select, and_, exists
```

**`get_current_tenant_user` vs `get_business_manager`:** The profile endpoint uses `get_current_tenant_user` (not `get_business_manager`) because it needs to be accessible by the user themselves. Both are in `app.api.deps`.

**Overdue calculation in detail endpoint:** The `_employee_status` function checks `asgn.due_date` — due dates from `TrainingAssignment` are stored as timezone-aware datetimes. Use `.replace(tzinfo=timezone.utc)` only if the value is naive; if already tz-aware, comparison works directly. Check the actual ORM column definition — it uses `DateTime(timezone=True)`, so values from the DB will be tz-aware.

**Warning threshold approaching count on employee rows:** The `approaching_count` is computed in the `useMemo` but the TypeScript type for `EmployeeSummary` doesn't include it. Cast the spread result as `typeof emp & { approaching_count: number }` or add it to the type explicitly in `analytics.ts`.

**React key warning in ManagerAnalyticsDetail:** The employee table uses `<>` fragment for the expand row pair. Fragments don't accept `key` props — wrap in `<React.Fragment key={emp.user_id}>` instead.
