import json
import logging
import uuid
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.notification import Notification
from app.worker.email_client import send_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def handle_event(db: AsyncSession, event: dict):
    """Process a single event dict. Testable without Redis."""
    event_type = event.get("type") or event.get("event_type")
    payload = event.get("payload", {})
    event_id = event.get("event_id")

    # Idempotency check
    if event_id:
        existing = await db.execute(
            select(Notification).where(Notification.event_id == event_id)
        )
        if existing.scalar_one_or_none():
            logger.info("Skipping duplicate event %s", event_id)
            return

    notified_user_id: str | None = None  # set only when an in-app notification is created

    if event_type == "TRAINING_COMPLETED":
        # In-app only — NO email (spec: in-app notification only)
        notified_user_id = payload["user_id"]
        cert_id = payload.get("certificate_id")
        db.add(Notification(
            id=str(uuid.uuid4()),
            event_id=event_id,
            user_id=notified_user_id,
            tenant_id=payload["tenant_id"],
            title="Training Completed",
            message=f"Congratulations! You completed: {payload.get('training_title', 'a training')}.",
            notification_type="success",
            data={"certificate_id": cert_id} if cert_id else None,
        ))

    elif event_type == "NEW_TRAINING_ASSIGNED":
        # In-app + email to learner
        notified_user_id = payload["user_id"]
        db.add(Notification(
            id=str(uuid.uuid4()),
            event_id=event_id,
            user_id=notified_user_id,
            tenant_id=payload["tenant_id"],
            title="New Training Assigned",
            message=f"You have been assigned: {payload.get('training_title', 'a training')}.",
            notification_type="info",
        ))
        await send_email(
            to=payload.get("user_email", ""),
            subject="New Training Assigned",
            template_name="new_training_assigned.html",
            context={
                "training_title": payload.get("training_title"),
                "due_date": payload.get("due_date"),
                "frontend_url": settings.FRONTEND_URL,
            },
        )

    elif event_type == "PROGRESS_RESET":
        # In-app to MANAGER only — learner is NOT notified
        manager_id = payload.get("manager_user_id")
        if manager_id:
            notified_user_id = manager_id
            db.add(Notification(
                id=str(uuid.uuid4()),
                event_id=event_id,
                user_id=manager_id,
                tenant_id=payload["tenant_id"],
                title="Training Progress Reset",
                message=f"An employee's progress was reset due to a content update (version {payload.get('version_id', '')}).",
                notification_type="warning",
            ))

    elif event_type == "QUIZ_LOCKOUT":
        # In-app + email to manager
        manager_id = payload.get("manager_user_id")
        if manager_id:
            notified_user_id = manager_id
            db.add(Notification(
                id=str(uuid.uuid4()),
                event_id=event_id,
                user_id=manager_id,
                tenant_id=payload["tenant_id"],
                title="Quiz Lockout",
                message=f"{payload.get('learner_name', 'A learner')} has been locked out of a quiz.",
                notification_type="error",
            ))
            await send_email(
                to=payload.get("manager_email", ""),
                subject="Quiz Lockout — Action Required",
                template_name="quiz_lockout.html",
                context={**payload, "frontend_url": settings.FRONTEND_URL},
            )

    elif event_type == "USER_INVITED":
        # Email only — no in-app, no cache invalidation
        await send_email(
            to=payload.get("email", ""),
            subject="You're invited!",
            template_name="registration_invite.html",
            context={
                "registration_url": payload.get("invite_url"),
                "full_name": payload.get("full_name", payload.get("email", "")),
                "token": payload.get("token", ""),
                "tenant_name": payload.get("tenant_name"),
                "primary_color": payload.get("primary_color", "#1e3a5f"),
                "secondary_color": payload.get("secondary_color", "#2d6098"),
                "logo_url": payload.get("logo_url"),
            },
        )

    elif event_type == "PASSWORD_RESET_REQUESTED":
        # Email only — no in-app, no cache invalidation
        await send_email(
            to=payload.get("email", ""),
            subject="Reset your password",
            template_name="password_reset.html",
            context={"reset_url": payload.get("reset_url")},
        )

    elif event_type == "EMPLOYEE_ACTIVATED":
        # In-app to manager only
        manager_id = payload.get("manager_user_id")
        if manager_id:
            notified_user_id = manager_id
            db.add(Notification(
                id=str(uuid.uuid4()),
                event_id=event_id,
                user_id=manager_id,
                tenant_id=payload["tenant_id"],
                title="Employee Activated",
                message=f"{payload.get('employee_name', 'A new employee')} has activated their account.",
                notification_type="info",
            ))

    elif event_type == "COLLABORATOR_ADDED":
        # In-app to the newly added collaborator (BR-302a)
        collaborator_id = payload.get("collaborator_user_id")
        if collaborator_id:
            notified_user_id = collaborator_id
            training_title = payload.get("training_title", "a training")
            db.add(Notification(
                id=str(uuid.uuid4()),
                event_id=event_id,
                user_id=collaborator_id,
                tenant_id=payload["tenant_id"],
                title="Added as Collaborator",
                message=f"You've been added as a collaborator on \"{training_title}\".",
                notification_type="info",
            ))

    else:
        logger.warning("Unhandled event type: %s", event_type)
        return

    await db.commit()

    if notified_user_id:
        from app.core.cache import invalidate_cache
        await invalidate_cache("notification_list", payload.get("tenant_id", ""), user_id=notified_user_id)


async def consume_events():
    logger.info("Starting Redis consumer...")
    r = redis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe("lms_events")
    logger.info("Subscribed to lms_events channel")

    async for message in pubsub.listen():
        if message["type"] == "message":
            try:
                data = json.loads(message["data"])
                event = {
                    "type": data.get("event_type"),
                    "event_id": data.get("event_id"),
                    "payload": data.get("payload", {}),
                }
                async with AsyncSessionLocal() as db:
                    await handle_event(db, event)
            except Exception as e:
                logger.error("Error processing event: %s", e)
