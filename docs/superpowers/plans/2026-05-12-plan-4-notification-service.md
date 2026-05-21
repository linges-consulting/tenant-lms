# Notification Service Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `email_worker` into `notification_service`, fix all incorrect notification targets, add missing event handlers, add pagination + unread-count endpoint, and implement the 3-step reminder scheduler. Write the full T-NO-* test suite.

**Architecture:** The standalone `email_worker` (a pure asyncio script) is dissolved into `notification_service` as a second background task. The merged service owns both the in-app HTTP API and email delivery. All Jinja2 templates, Mailgun client code, and event handler logic move into `notification_service`. A new `APScheduler` async job scheduler runs inside the same FastAPI process, firing due-date reminder and overdue queries on a configurable interval.

**Tech Stack:** FastAPI, SQLAlchemy (async), Redis pub/sub, APScheduler, Jinja2, Mailgun API, pytest, httpx

**Run tests:** `docker compose exec notification-service pytest tests/ -v`

---

## File Map

| File | Action |
|---|---|
| `app/notification_service/app/core/config.py` | Modify — add Mailgun vars, FRONTEND_URL, scheduler interval |
| `app/notification_service/app/worker/consumer.py` | Modify — fix PROGRESS_RESET target, TRAINING_COMPLETED remove email, add missing event types |
| `app/notification_service/app/worker/email_client.py` | Create — Mailgun send function (moved from email_worker) |
| `app/notification_service/app/worker/scheduler.py` | Create — APScheduler jobs for 14d/7d/1d reminders and daily overdue |
| `app/notification_service/app/worker/templates/` | Create — copy all Jinja2 templates from email_worker; fix 7-day → 48h in invite template |
| `app/notification_service/app/api/v1/endpoints/notifications.py` | Modify — add pagination, add unread-count endpoint |
| `app/notification_service/app/main.py` | Modify — start scheduler in lifespan, remove reference to separate email worker |
| `app/notification_service/requirements.txt` | Modify — add jinja2, apscheduler, mailgun client |
| `app/notification_service/tests/conftest.py` | Create — test DB, mock Redis, JWT helpers |
| `app/notification_service/tests/api/test_notifications.py` | Create — T-NO-01 to T-NO-14 |
| `app/notification_service/tests/api/test_scheduler.py` | Create — T-NO-15 to T-NO-17 |

---

### Task 1: Set up test infrastructure

**Files:**
- Create: `app/notification_service/tests/conftest.py`
- Create: `app/notification_service/tests/__init__.py`
- Create: `app/notification_service/tests/api/__init__.py`

- [ ] **Step 1: Create `tests/conftest.py`**

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone
import jwt, uuid
from unittest.mock import AsyncMock, patch

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

def make_jwt(user_id: str, tenant_id: str, roles: list[str] = None) -> str:
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": roles or ["Employee"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, EXTERNAL_JWT_SECRET, algorithm="HS256")

def auth(user_id: str, tenant_id: str, roles: list[str] = None) -> dict:
    return {"Authorization": f"Bearer {make_jwt(user_id, tenant_id, roles)}"}
```

- [ ] **Step 2: Update `requirements.txt`**

Ensure present:
```
pytest==7.4.3
pytest-asyncio==0.23.5
httpx==0.26.0
aiosqlite==0.19.0
jinja2==3.1.3
apscheduler==3.10.4
requests==2.31.0
```

- [ ] **Step 3: Commit**

```bash
git add app/notification_service/tests/
git commit -m "test: add notification service test infrastructure"
```

---

### Task 2: Add Mailgun vars to config and move email client into notification_service

**Files:**
- Modify: `app/notification_service/app/core/config.py`
- Create: `app/notification_service/app/worker/email_client.py`
- Create: `app/notification_service/app/worker/templates/` (copy from email_worker)

- [ ] **Step 1: Add Mailgun settings to `config.py`**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # existing fields...
    DB_URL: str
    REDIS_URL: str
    EXTERNAL_JWT_SECRET: str
    INTERNAL_JWT_SECRET: str
    ENVIRONMENT: str = "dev"

    # Add these:
    MAILGUN_API_KEY: str = ""
    MAILGUN_DOMAIN: str = ""
    MAILGUN_BASE_URL: str = "https://api.mailgun.net"
    FROM_EMAIL: str = "noreply@example.com"
    USE_MAILGUN: bool = False
    MAILGUN_AUTHORIZED_RECIPIENT: str = ""
    FRONTEND_URL: str = "http://localhost"

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 2: Create `email_client.py`** (ported from `email_worker/main.py`)

```python
import requests
from jinja2 import Environment, FileSystemLoader
import os
from app.core.config import settings

_template_dir = os.path.join(os.path.dirname(__file__), "templates")
_jinja_env = Environment(loader=FileSystemLoader(_template_dir))

async def send_email(to: str, subject: str, template_name: str, context: dict) -> bool:
    """Send an email via Mailgun. Returns True on success. No-op if USE_MAILGUN=False."""
    if not settings.USE_MAILGUN:
        return True

    recipient = to
    if settings.ENVIRONMENT == "dev" and settings.MAILGUN_AUTHORIZED_RECIPIENT:
        recipient = settings.MAILGUN_AUTHORIZED_RECIPIENT

    template = _jinja_env.get_template(template_name)
    html_body = template.render(**context)

    response = requests.post(
        f"{settings.MAILGUN_BASE_URL}/v3/{settings.MAILGUN_DOMAIN}/messages",
        auth=("api", settings.MAILGUN_API_KEY),
        data={
            "from": settings.FROM_EMAIL,
            "to": recipient,
            "subject": subject,
            "html": html_body,
        },
        timeout=10,
    )
    return response.status_code == 200
```

- [ ] **Step 3: Copy templates from `email_worker` and fix the invite template**

```bash
cp -r app/email_worker/templates/* app/notification_service/app/worker/templates/
```

Fix the 7-day expiry bug in `registration_invite.html`:

```bash
grep -n "7 days\|7days\|seven days" app/notification_service/app/worker/templates/registration_invite.html
```

Find and replace `7 days` with `48 hours`:
```html
<!-- Before: -->
This link will expire in 7 days.

<!-- After: -->
This link will expire in 48 hours.
```

- [ ] **Step 4: Write test for email suppression when USE_MAILGUN=False**

Add to `tests/api/test_notifications.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock

# T-NO-13: Email send is suppressed when USE_MAILGUN=False
@pytest.mark.asyncio
async def test_email_suppressed_when_mailgun_disabled():
    from app.worker.email_client import send_email
    from unittest.mock import patch
    with patch("app.worker.email_client.settings") as mock_settings:
        mock_settings.USE_MAILGUN = False
        result = await send_email("user@example.com", "Subject", "registration_invite.html", {"name": "Test"})
        assert result == True  # succeeds silently without making HTTP call
```

- [ ] **Step 5: Run test**

```bash
docker compose exec notification-service pytest tests/api/test_notifications.py::test_email_suppressed_when_mailgun_disabled -v
```

- [ ] **Step 6: Commit**

```bash
git add app/notification_service/app/core/config.py app/notification_service/app/worker/ app/notification_service/tests/
git commit -m "feat: merge Mailgun email client and templates into notification_service (C-512)"
```

---

### Task 3: Fix consumer — correct notification targets, remove wrong email sends

**Files:**
- Modify: `app/notification_service/app/worker/consumer.py`

- [ ] **Step 1: Write failing tests**

Create `app/notification_service/tests/api/test_notifications.py`:

```python
import pytest, uuid, json
from tests.conftest import auth

# T-NO-XX: PROGRESS_RESET in-app notification goes to manager, not learner
@pytest.mark.asyncio
async def test_progress_reset_notifies_manager(client, db_session):
    from app.worker.consumer import handle_event
    from app.models.notification import Notification
    from sqlalchemy import select

    tenant_id = str(uuid.uuid4())
    manager_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    training_id = str(uuid.uuid4())

    await handle_event(db_session, {
        "type": "PROGRESS_RESET",
        "payload": {
            "manager_user_id": manager_id,
            "user_id": learner_id,
            "tenant_id": tenant_id,
            "training_id": training_id,
            "version_id": "v2",
        }
    })
    await db_session.commit()

    result = await db_session.execute(
        select(Notification).where(Notification.user_id == manager_id)
    )
    notif = result.scalars().first()
    assert notif is not None
    assert notif.user_id == manager_id

    # Learner must NOT be notified
    result2 = await db_session.execute(
        select(Notification).where(Notification.user_id == learner_id)
    )
    assert result2.scalars().first() is None

# T-NO-XX: TRAINING_COMPLETED creates in-app but does NOT send email
@pytest.mark.asyncio
async def test_training_completed_no_email(client, db_session):
    from app.worker.consumer import handle_event
    from unittest.mock import patch, AsyncMock

    with patch("app.worker.consumer.send_email", new_callable=AsyncMock) as mock_send:
        await handle_event(db_session, {
            "type": "TRAINING_COMPLETED",
            "payload": {
                "user_id": str(uuid.uuid4()),
                "tenant_id": str(uuid.uuid4()),
                "training_id": str(uuid.uuid4()),
                "training_title": "Test Training",
            }
        })
        mock_send.assert_not_called()
```

- [ ] **Step 2: Run to confirm failures**

```bash
docker compose exec notification-service pytest tests/api/test_notifications.py -v 2>&1 | tail -20
```

- [ ] **Step 3: Fix `consumer.py`**

Refactor the consumer into a single `handle_event(db, event)` async function that can be tested directly. Fix each handler:

```python
from app.worker.email_client import send_email
from app.models.notification import Notification
import uuid

async def handle_event(db, event: dict):
    event_type = event.get("type")
    payload = event.get("payload", {})

    if event_type == "TRAINING_COMPLETED":
        # In-app only — NO email (spec says in-app only)
        db.add(Notification(
            id=str(uuid.uuid4()),
            user_id=payload["user_id"],
            tenant_id=payload["tenant_id"],
            title="Training Completed",
            body=f"You completed {payload.get('training_title', 'a training')}.",
            is_read=False,
        ))

    elif event_type == "NEW_TRAINING_ASSIGNED":
        # In-app + Email
        db.add(Notification(
            id=str(uuid.uuid4()),
            user_id=payload["user_id"],
            tenant_id=payload["tenant_id"],
            title="New Training Assigned",
            body=f"You have been assigned: {payload.get('training_title', 'a training')}.",
            is_read=False,
        ))
        await send_email(
            to=payload.get("user_email", ""),
            subject="New Training Assigned",
            template_name="new_training_assigned.html",
            context={"training_title": payload.get("training_title"), "due_date": payload.get("due_date"), "frontend_url": settings.FRONTEND_URL},
        )

    elif event_type == "PROGRESS_RESET":
        # In-app to MANAGER only — employee is NOT notified
        manager_id = payload.get("manager_user_id")
        if manager_id:
            db.add(Notification(
                id=str(uuid.uuid4()),
                user_id=manager_id,
                tenant_id=payload["tenant_id"],
                title="Training Progress Reset",
                body=f"An employee's progress was reset due to a content update in version {payload.get('version_id')}.",
                is_read=False,
            ))

    elif event_type == "QUIZ_LOCKOUT":
        # In-app to manager + Email to manager
        manager_id = payload.get("manager_user_id")
        if manager_id:
            db.add(Notification(
                id=str(uuid.uuid4()),
                user_id=manager_id,
                tenant_id=payload["tenant_id"],
                title="Quiz Lockout",
                body=f"{payload.get('learner_name', 'A learner')} has been locked out of a quiz.",
                is_read=False,
            ))
            await send_email(
                to=payload.get("manager_email", ""),
                subject="Quiz Lockout — Action Required",
                template_name="quiz_lockout.html",
                context=payload,
            )

    elif event_type == "USER_INVITED":
        # Email only — Magic Link to new user
        await send_email(
            to=payload.get("email", ""),
            subject="You're invited!",
            template_name="registration_invite.html",
            context={"invite_url": payload.get("invite_url"), "tenant_name": payload.get("tenant_name")},
        )

    elif event_type == "PASSWORD_RESET_REQUESTED":
        await send_email(
            to=payload.get("email", ""),
            subject="Reset your password",
            template_name="password_reset.html",
            context={"reset_url": payload.get("reset_url")},
        )

    elif event_type == "EMPLOYEE_ACTIVATED":
        # In-app to manager
        manager_id = payload.get("manager_user_id")
        if manager_id:
            db.add(Notification(
                id=str(uuid.uuid4()),
                user_id=manager_id,
                tenant_id=payload["tenant_id"],
                title="Employee Activated",
                body=f"{payload.get('employee_name', 'A new employee')} has activated their account.",
                is_read=False,
            ))

    await db.commit()
```

- [ ] **Step 4: Run tests**

```bash
docker compose exec notification-service pytest tests/api/test_notifications.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/notification_service/app/worker/consumer.py
git commit -m "fix: correct notification targets (PROGRESS_RESET → manager, TRAINING_COMPLETED no email), add missing event handlers"
```

---

### Task 4: Fix in-app notifications API — add pagination and unread-count endpoint

**Files:**
- Modify: `app/notification_service/app/api/v1/endpoints/notifications.py` (or `main.py` if routes are inline)

- [ ] **Step 1: Write failing tests**

Add to `tests/api/test_notifications.py`:

```python
# T-NO-01: GET /notifications returns paginated results
@pytest.mark.asyncio
async def test_get_notifications_paginated(client, db_session):
    from app.models.notification import Notification
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    # Insert 15 notifications
    for i in range(15):
        db_session.add(Notification(
            id=str(uuid.uuid4()), user_id=user_id, tenant_id=tenant_id,
            title=f"Notif {i}", body="body", is_read=False,
        ))
    await db_session.commit()

    resp = await client.get("/api/v1/notifications?limit=10&offset=0", headers=auth(user_id, tenant_id))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 10
    assert data["total"] == 15

# T-NO-02: GET /notifications/unread-count returns correct count
@pytest.mark.asyncio
async def test_unread_count(client, db_session):
    from app.models.notification import Notification
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    for i in range(3):
        db_session.add(Notification(id=str(uuid.uuid4()), user_id=user_id, tenant_id=tenant_id, title=f"N{i}", body="b", is_read=False))
    db_session.add(Notification(id=str(uuid.uuid4()), user_id=user_id, tenant_id=tenant_id, title="Read", body="b", is_read=True))
    await db_session.commit()

    resp = await client.get("/api/v1/notifications/unread-count", headers=auth(user_id, tenant_id))
    assert resp.status_code == 200
    assert resp.json()["unread_count"] == 3
```

- [ ] **Step 2: Run to confirm failures**

```bash
docker compose exec notification-service pytest tests/api/test_notifications.py::test_get_notifications_paginated tests/api/test_notifications.py::test_unread_count -v
```

- [ ] **Step 3: Fix the `GET /notifications` endpoint to support pagination**

In the notifications endpoint:

```python
from fastapi import Query as QP
from sqlalchemy import select, func

@router.get("")
async def get_notifications(
    limit: int = QP(default=20, ge=1, le=100),
    offset: int = QP(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant_id),
):
    count_result = await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == current_user.id,
            Notification.tenant_id == tenant_id,
        )
    )
    total = count_result.scalar()

    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.tenant_id == tenant_id,
        ).order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    )
    items = result.scalars().all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}
```

- [ ] **Step 4: Add `GET /notifications/unread-count` endpoint**

```python
@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant_id),
):
    result = await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == current_user.id,
            Notification.tenant_id == tenant_id,
            Notification.is_read == False,
        )
    )
    return {"unread_count": result.scalar()}
```

Note: register this route **before** any `/{id}` routes to avoid routing conflicts.

- [ ] **Step 5: Run tests**

```bash
docker compose exec notification-service pytest tests/api/test_notifications.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/notification_service/app/
git commit -m "fix: add pagination to GET /notifications, add unread-count endpoint (T-NO-01, T-NO-02)"
```

---

### Task 5: Add reminder scheduler (14d/7d/1d due-date reminders + daily overdue)

**Files:**
- Create: `app/notification_service/app/worker/scheduler.py`
- Modify: `app/notification_service/app/main.py`

- [ ] **Step 1: Write failing tests**

Create `app/notification_service/tests/api/test_scheduler.py`:

```python
import pytest, uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

# T-NO-15: Due-date reminder job sends emails for assignments due in exactly 14 days
@pytest.mark.asyncio
async def test_due_date_reminder_14d(db_session):
    from app.worker.scheduler import send_due_date_reminders
    from app.models.assignment_reminder import AssignmentForReminder  # or use raw query mock

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Mock the DB query to return one assignment due in 14 days
    mock_assignment = type("A", (), {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "training_id": str(uuid.uuid4()),
        "training_title": "Safety Training",
        "due_date": now + timedelta(days=14),
        "user_email": "user@example.com",
    })()

    with patch("app.worker.scheduler.get_assignments_due_in_days", new_callable=AsyncMock, return_value=[mock_assignment]) as mock_query, \
         patch("app.worker.scheduler.send_email", new_callable=AsyncMock) as mock_send:
        await send_due_date_reminders(db_session, days_before=14)
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args.kwargs["template_name"] == "due_date_reminder.html"

# T-NO-16: Daily overdue job sends emails for assignments past due date with completion_lock=False
@pytest.mark.asyncio
async def test_daily_overdue_reminder(db_session):
    from app.worker.scheduler import send_overdue_reminders

    mock_assignment = type("A", (), {
        "user_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "training_title": "HR Training",
        "due_date": datetime.now(timezone.utc) - timedelta(days=2),
        "user_email": "late@example.com",
        "completion_lock": False,
    })()

    with patch("app.worker.scheduler.get_overdue_assignments", new_callable=AsyncMock, return_value=[mock_assignment]) as _, \
         patch("app.worker.scheduler.send_email", new_callable=AsyncMock) as mock_send:
        await send_overdue_reminders(db_session)
        mock_send.assert_called_once()
```

- [ ] **Step 2: Run to confirm failures**

```bash
docker compose exec notification-service pytest tests/api/test_scheduler.py -v 2>&1 | tail -20
```

- [ ] **Step 3: Create `scheduler.py`**

```python
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.worker.email_client import send_email
from app.core.config import settings

# These models belong to core_service — for notification_service to query them,
# either use an internal HTTP call to core_service or duplicate the minimal model definition.
# Recommended: internal HTTP call to core_service /api/v1/dashboards/reminders endpoint.

async def get_assignments_due_in_days(db: AsyncSession, days: int) -> list:
    """Query core_service for assignments due in `days` days."""
    import httpx
    now = datetime.now(timezone.utc)
    target_start = now + timedelta(days=days) - timedelta(hours=12)
    target_end = now + timedelta(days=days) + timedelta(hours=12)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.CORE_SERVICE_URL}/api/v1/dashboards/assignments-due",
            params={"due_after": target_start.isoformat(), "due_before": target_end.isoformat()},
            headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
    return []

async def get_overdue_assignments(db: AsyncSession) -> list:
    now = datetime.now(timezone.utc)
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.CORE_SERVICE_URL}/api/v1/dashboards/assignments-overdue",
            headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
    return []

async def send_due_date_reminders(db: AsyncSession, days_before: int):
    assignments = await get_assignments_due_in_days(db, days_before)
    for a in assignments:
        await send_email(
            to=a["user_email"],
            subject=f"Reminder: Training due in {days_before} days",
            template_name="due_date_reminder.html",
            context={
                "training_title": a["training_title"],
                "due_date": a["due_date"],
                "days_before": days_before,
                "frontend_url": settings.FRONTEND_URL,
            },
        )

async def send_overdue_reminders(db: AsyncSession):
    assignments = await get_overdue_assignments(db)
    for a in assignments:
        if not a.get("completion_lock"):
            await send_email(
                to=a["user_email"],
                subject="Overdue: Training past due date",
                template_name="overdue_reminder.html",
                context={"training_title": a["training_title"], "due_date": a["due_date"], "frontend_url": settings.FRONTEND_URL},
            )

def create_scheduler(db_factory) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    async def run_reminders_14d():
        async with db_factory() as db:
            await send_due_date_reminders(db, 14)

    async def run_reminders_7d():
        async with db_factory() as db:
            await send_due_date_reminders(db, 7)

    async def run_reminders_1d():
        async with db_factory() as db:
            await send_due_date_reminders(db, 1)

    async def run_overdue():
        async with db_factory() as db:
            await send_overdue_reminders(db)

    scheduler.add_job(run_reminders_14d, "cron", hour=8, minute=0, id="reminder_14d")
    scheduler.add_job(run_reminders_7d, "cron", hour=8, minute=5, id="reminder_7d")
    scheduler.add_job(run_reminders_1d, "cron", hour=8, minute=10, id="reminder_1d")
    scheduler.add_job(run_overdue, "cron", hour=9, minute=0, id="overdue_daily")

    return scheduler
```

- [ ] **Step 4: Add `CORE_SERVICE_URL` to `config.py`**

```python
CORE_SERVICE_URL: str = "http://core-service:8000"
INTERNAL_API_KEY: str = ""
```

- [ ] **Step 5: Start scheduler in `main.py` lifespan**

In `main.py`, inside the FastAPI lifespan context manager:

```python
from contextlib import asynccontextmanager
from app.worker.scheduler import create_scheduler
from app.db.session import AsyncSessionLocal
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start Redis consumer (existing)
    if os.getenv("ENVIRONMENT") != "test":
        asyncio.create_task(consume_events())

        # Start reminder scheduler
        scheduler = create_scheduler(AsyncSessionLocal)
        scheduler.start()

    yield

    if os.getenv("ENVIRONMENT") != "test":
        scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
```

- [ ] **Step 6: Create missing email templates**

Create these Jinja2 templates in `app/notification_service/app/worker/templates/`:

`new_training_assigned.html`:
```html
{% extends "base.html" %}
{% block content %}
<h2>New Training Assigned</h2>
<p>You have been assigned: <strong>{{ training_title }}</strong></p>
{% if due_date %}<p>Due date: {{ due_date }}</p>{% endif %}
<a href="{{ frontend_url }}/dashboard">Start Training</a>
{% endblock %}
```

`due_date_reminder.html`:
```html
{% extends "base.html" %}
{% block content %}
<h2>Training Due in {{ days_before }} Day{{ 's' if days_before != 1 }}</h2>
<p><strong>{{ training_title }}</strong> is due on {{ due_date }}.</p>
<a href="{{ frontend_url }}/dashboard">Continue Training</a>
{% endblock %}
```

`overdue_reminder.html`:
```html
{% extends "base.html" %}
{% block content %}
<h2>Overdue Training</h2>
<p><strong>{{ training_title }}</strong> was due on {{ due_date }}.</p>
<a href="{{ frontend_url }}/dashboard">Complete Now</a>
{% endblock %}
```

`quiz_lockout.html`:
```html
{% extends "base.html" %}
{% block content %}
<h2>Quiz Lockout — Action Required</h2>
<p>{{ learner_name }} has been locked out of a quiz and requires a reset.</p>
<a href="{{ frontend_url }}/manage/employees">Manage Employees</a>
{% endblock %}
```

- [ ] **Step 7: Run tests**

```bash
docker compose exec notification-service pytest tests/api/test_scheduler.py -v
```

- [ ] **Step 8: Commit**

```bash
git add app/notification_service/app/worker/scheduler.py app/notification_service/app/worker/templates/ app/notification_service/app/main.py app/notification_service/app/core/config.py
git commit -m "feat: add APScheduler for 14d/7d/1d due-date reminders and daily overdue emails (BR-601, BR-603)"
```

---

### Task 6: Run full notification test suite

- [ ] **Step 1: Run all tests**

```bash
docker compose exec notification-service pytest tests/ -v --tb=short 2>&1 | tail -50
```

Expected: T-NO-01 through T-NO-17 all pass.

- [ ] **Step 2: Verify email_worker service is removed from docker-compose.yml** (covered in Plan 1)

```bash
grep "email.worker" docker-compose.yml
```

Expected: no output.

- [ ] **Step 3: Final commit**

```bash
git add app/notification_service/
git commit -m "test: full notification service test suite green (T-NO-01 to T-NO-17)"
```
