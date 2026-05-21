import pytest
import uuid
from unittest.mock import patch, AsyncMock
from sqlalchemy import select
from app.models.notification import Notification
from tests.conftest import make_auth_overrides


# TC-NOT-08: Email is suppressed (returns True) when USE_MAILGUN=False
@pytest.mark.asyncio
async def test_email_suppressed_when_mailgun_disabled():
    from app.worker.email_client import send_email
    with patch("app.worker.email_client.settings") as mock_settings:
        mock_settings.USE_MAILGUN = False
        result = await send_email("user@example.com", "Subject", "registration_invite.html", {"name": "Test"})
        assert result is True


# TC-NOT-04: PROGRESS_RESET event creates in-app notification for the assigned Manager, not the learner
@pytest.mark.asyncio
async def test_progress_reset_notifies_manager_not_learner(db_session):
    from app.worker.consumer import handle_event

    tenant_id = str(uuid.uuid4())
    manager_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    await handle_event(db_session, {
        "type": "PROGRESS_RESET",
        "payload": {
            "manager_user_id": manager_id,
            "user_id": learner_id,
            "tenant_id": tenant_id,
            "training_id": str(uuid.uuid4()),
            "version_id": "v2",
        }
    })

    # Manager gets notified
    result = await db_session.execute(
        select(Notification).where(Notification.user_id == manager_id)
    )
    assert result.scalars().first() is not None

    # Learner does NOT get notified
    result2 = await db_session.execute(
        select(Notification).where(Notification.user_id == learner_id)
    )
    assert result2.scalars().first() is None


# TC-NOT-05: TRAINING_COMPLETED event creates in-app notification for learner
@pytest.mark.asyncio
async def test_training_completed_creates_inapp_notification_for_learner(db_session):
    from app.worker.consumer import handle_event

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    await handle_event(db_session, {
        "type": "TRAINING_COMPLETED",
        "payload": {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "training_title": "Workplace Safety",
        }
    })

    result = await db_session.execute(
        select(Notification).where(Notification.user_id == user_id)
    )
    notif = result.scalars().first()
    assert notif is not None
    assert notif.notification_type == "success"
    assert "Workplace Safety" in notif.message
    assert notif.tenant_id == tenant_id


# TC-NOT-06: TRAINING_COMPLETED does NOT send an email (in-app only)
@pytest.mark.asyncio
async def test_training_completed_no_email(db_session):
    from app.worker.consumer import handle_event

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    with patch("app.worker.consumer.send_email", new_callable=AsyncMock) as mock_send:
        await handle_event(db_session, {
            "type": "TRAINING_COMPLETED",
            "payload": {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "training_title": "Safety 101",
            }
        })
        mock_send.assert_not_called()

    # In-app notification created
    result = await db_session.execute(
        select(Notification).where(Notification.user_id == user_id)
    )
    notif = result.scalars().first()
    assert notif is not None
    assert notif.notification_type == "success"


# TC-NOT-07: EMPLOYEE_ACTIVATED event notifies the Manager
@pytest.mark.asyncio
async def test_employee_activated_notifies_manager(db_session):
    from app.worker.consumer import handle_event

    tenant_id = str(uuid.uuid4())
    manager_id = str(uuid.uuid4())

    await handle_event(db_session, {
        "type": "EMPLOYEE_ACTIVATED",
        "payload": {
            "manager_user_id": manager_id,
            "tenant_id": tenant_id,
            "employee_name": "Jane Smith",
        }
    })

    result = await db_session.execute(
        select(Notification).where(Notification.user_id == manager_id)
    )
    notif = result.scalars().first()
    assert notif is not None
    assert "Jane Smith" in notif.message


# TC-NOT-01: GET /notifications returns paginated results
@pytest.mark.asyncio
async def test_get_notifications_paginated(client, db_session):
    from app.main import app

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    for i in range(15):
        db_session.add(Notification(
            id=str(uuid.uuid4()), user_id=user_id, tenant_id=tenant_id,
            title=f"Notif {i}", message="body", is_read=False,
        ))
    await db_session.commit()

    app.dependency_overrides.update(make_auth_overrides(user_id, tenant_id))
    resp = await client.get("/api/v1/notifications?limit=10&offset=0")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 10
    assert data["total"] == 15
    assert data["limit"] == 10
    assert data["offset"] == 0


# TC-NOT-02: GET /notifications/unread-count returns correct count
@pytest.mark.asyncio
async def test_unread_count(client, db_session):
    from app.main import app

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    for i in range(3):
        db_session.add(Notification(
            id=str(uuid.uuid4()), user_id=user_id, tenant_id=tenant_id,
            title=f"Unread {i}", message="body", is_read=False,
        ))
    db_session.add(Notification(
        id=str(uuid.uuid4()), user_id=user_id, tenant_id=tenant_id,
        title="Read one", message="body", is_read=True,
    ))
    await db_session.commit()

    app.dependency_overrides.update(make_auth_overrides(user_id, tenant_id))
    resp = await client.get("/api/v1/notifications/unread-count")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["unread_count"] == 3


# TC-NOT-03: Duplicate event_id is silently ignored (idempotent)
@pytest.mark.asyncio
async def test_duplicate_event_id_ignored(db_session):
    from app.worker.consumer import handle_event

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())

    event = {
        "type": "TRAINING_COMPLETED",
        "event_id": event_id,
        "payload": {"user_id": user_id, "tenant_id": tenant_id, "training_title": "Safety 101"},
    }

    await handle_event(db_session, event)
    await handle_event(db_session, event)  # duplicate

    result = await db_session.execute(
        select(Notification).where(Notification.user_id == user_id)
    )
    assert len(result.scalars().all()) == 1
