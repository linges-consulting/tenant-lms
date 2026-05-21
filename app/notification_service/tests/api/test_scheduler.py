import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch


# TC-NOT-10: Due date reminder job calls send_email for each eligible assignment
@pytest.mark.asyncio
async def test_due_date_reminder_sends_email():
    from app.worker.scheduler import send_due_date_reminders

    mock_assignment = {
        "user_email": "learner@example.com",
        "training_title": "Safety Training",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "tenant_id": "tenant-1",
        "user_id": "user-1",
    }

    with patch("app.worker.scheduler.get_assignments_due_in_days", new_callable=AsyncMock, return_value=[mock_assignment]) as mock_query, \
         patch("app.worker.scheduler.send_email", new_callable=AsyncMock) as mock_send:
        await send_due_date_reminders(days_before=14)
        mock_query.assert_called_once_with(14)
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["template_name"] == "due_date_reminder.html"
        assert call_kwargs["to"] == "learner@example.com"
        assert call_kwargs["context"]["days_before"] == 14
        assert "14" in call_kwargs["subject"]


# TC-NOT-11: Overdue reminder job skips assignments that have completion_lock set
@pytest.mark.asyncio
async def test_overdue_reminder_skips_completion_lock():
    from app.worker.scheduler import send_overdue_reminders

    assignments = [
        {"user_email": "a@example.com", "training_title": "HR", "due_date": "2026-01-01", "completion_lock": False},
        {"user_email": "b@example.com", "training_title": "IT", "due_date": "2026-01-01", "completion_lock": True},
    ]

    with patch("app.worker.scheduler.get_overdue_assignments", new_callable=AsyncMock, return_value=assignments), \
         patch("app.worker.scheduler.send_email", new_callable=AsyncMock) as mock_send:
        await send_overdue_reminders()
        # Only the non-locked assignment should get an email
        assert mock_send.call_count == 1
        assert mock_send.call_args.kwargs["to"] == "a@example.com"


# TC-NOT-09: Scheduler registers exactly 4 cron jobs on startup
def test_scheduler_has_four_jobs():
    from app.worker.scheduler import create_scheduler
    scheduler = create_scheduler()
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert job_ids == {"reminder_14d", "reminder_7d", "reminder_1d", "overdue_daily"}
