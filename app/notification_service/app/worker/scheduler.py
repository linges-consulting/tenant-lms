import logging
import httpx
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.worker.email_client import send_email
from app.core.config import settings

logger = logging.getLogger(__name__)


async def get_assignments_due_in_days(days: int) -> list[dict]:
    """Query core_service for assignments due in `days` days (±12h window)."""
    now = datetime.now(timezone.utc)
    target_start = now + timedelta(days=days) - timedelta(hours=12)
    target_end = now + timedelta(days=days) + timedelta(hours=12)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{settings.CORE_SERVICE_URL}/api/v1/dashboards/assignments-due",
                params={
                    "due_after": target_start.isoformat(),
                    "due_before": target_end.isoformat(),
                },
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
            if resp.status_code == 200:
                return resp.json()
            logger.error("assignments-due returned %s", resp.status_code)
    except httpx.RequestError as exc:
        logger.error("assignments-due request failed: %s", exc)
    return []


async def get_overdue_assignments() -> list[dict]:
    """Query core_service for all overdue incomplete assignments."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{settings.CORE_SERVICE_URL}/api/v1/dashboards/assignments-overdue",
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
            if resp.status_code == 200:
                return resp.json()
            logger.error("assignments-overdue returned %s", resp.status_code)
    except httpx.RequestError as exc:
        logger.error("assignments-overdue request failed: %s", exc)
    return []


async def send_due_date_reminders(days_before: int) -> None:
    assignments = await get_assignments_due_in_days(days_before)
    for a in assignments:
        email = a.get("user_email", "")
        if not email:
            logger.warning("Skipping reminder for assignment without user_email: %s", a.get("training_id"))
            continue
        await send_email(
            to=email,
            subject=f"Reminder: Training due in {days_before} day{'s' if days_before != 1 else ''}",
            template_name="due_date_reminder.html",
            context={
                "training_title": a.get("training_title", ""),
                "due_date": a.get("due_date", ""),
                "days_before": days_before,
                "frontend_url": settings.FRONTEND_URL,
            },
        )


async def send_overdue_reminders() -> None:
    assignments = await get_overdue_assignments()
    for a in assignments:
        if a.get("completion_lock"):
            continue
        email = a.get("user_email", "")
        if not email:
            logger.warning("Skipping overdue reminder without user_email: %s", a.get("training_id"))
            continue
        await send_email(
            to=email,
            subject="Overdue: Training past due date",
            template_name="overdue_reminder.html",
            context={
                "training_title": a.get("training_title", ""),
                "due_date": a.get("due_date", ""),
                "frontend_url": settings.FRONTEND_URL,
            },
        )


async def auto_archive_expired_trainings() -> None:
    """Call core-service to archive trainings whose expiry date has passed."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.CORE_SERVICE_URL}/api/v1/trainings/internal/auto-archive-expired",
                headers={"X-Internal-Api-Key": settings.INTERNAL_API_KEY},
            )
            resp.raise_for_status()
            archived = resp.json()
            logger.info("Auto-archived %d expired trainings", len(archived))
            # TODO: send in-app notifications to managers per tenant
    except Exception:
        logger.exception("auto_archive_expired_trainings failed")


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(send_due_date_reminders, "cron", hour=8, minute=0, id="reminder_14d", args=[14])
    scheduler.add_job(send_due_date_reminders, "cron", hour=8, minute=5, id="reminder_7d", args=[7])
    scheduler.add_job(send_due_date_reminders, "cron", hour=8, minute=10, id="reminder_1d", args=[1])
    scheduler.add_job(send_overdue_reminders, "cron", hour=9, minute=0, id="overdue_daily")
    scheduler.add_job(auto_archive_expired_trainings, "cron", hour=0, minute=0, id="auto_archive_expired_trainings")
    return scheduler
