"""
Dashboard endpoints — Manager, Creator, Employee views + internal reminder endpoints.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy import select, func, and_, not_, exists, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_user, UserAuth
from app.core.config import settings
from app.db.session import get_db
from app.models.training import Training
from app.models.assignment import TrainingAssignment
from app.models.quiz_attempt import QuizAttempt
from app.models.enrollment import Enrollment

router = APIRouter()


# ---------------------------------------------------------------------------
# Internal key dependency (no JWT required)
# ---------------------------------------------------------------------------

def _require_internal_key(x_internal_api_key: Optional[str] = Header(default=None)):
    """Dependency that validates the X-Internal-Api-Key header."""
    if x_internal_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal API key",
        )


# ---------------------------------------------------------------------------
# GET /dashboards/manager
# ---------------------------------------------------------------------------

@router.get("/manager")
async def manager_dashboard(
    current_user: UserAuth = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Dashboard summary for Business Managers and SysAdmins.
    """
    allowed_roles = {"Business Manager", "SysAdmin"}
    if not any(r in allowed_roles for r in current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Business Manager or SysAdmin role required.",
        )

    tenant_id = current_user.tenant_id
    now = datetime.now(timezone.utc)

    # Total assignments (user-level, excluding deleted)
    total_q = await db.execute(
        select(func.count(TrainingAssignment.id)).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.deleted_at.is_(None),
            TrainingAssignment.user_id.isnot(None),
        )
    )
    total_assignments: int = total_q.scalar_one() or 0

    # Completed assignments — correlated by both training_id AND user_id
    completed_q = await db.execute(
        select(func.count(TrainingAssignment.id)).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.deleted_at.is_(None),
            TrainingAssignment.user_id.isnot(None),
            exists(
                select(Enrollment.id).where(
                    Enrollment.tenant_id == tenant_id,
                    Enrollment.training_id == TrainingAssignment.training_id,
                    Enrollment.user_id == TrainingAssignment.user_id,
                    Enrollment.is_completed.is_(True),
                )
            ),
        )
    )
    completed_assignments: int = completed_q.scalar_one() or 0

    # Overdue assignments — due_date < now, not completed for that specific user
    overdue_q = await db.execute(
        select(func.count(TrainingAssignment.id)).where(
            TrainingAssignment.tenant_id == tenant_id,
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
    )
    overdue_assignments: int = overdue_q.scalar_one() or 0

    # Quiz lockouts — distinct (user_id, chapter_id) pairs where the user has
    # hit the default max attempts (10) without passing.
    # max_attempts is stored in chapter content_data JSON; we use 10 as the default.
    lockout_sub = (
        select(
            QuizAttempt.user_id,
            QuizAttempt.chapter_id,
            func.max(QuizAttempt.attempt_number).label("max_attempt"),
            func.sum(QuizAttempt.passed.cast(Integer)).label("pass_count"),
        )
        .where(
            QuizAttempt.tenant_id == tenant_id,
        )
        .group_by(QuizAttempt.user_id, QuizAttempt.chapter_id)
        .having(
            and_(
                func.max(QuizAttempt.attempt_number) >= 10,
                func.sum(QuizAttempt.passed.cast(Integer)) == 0,
            )
        )
        .subquery()
    )
    lockout_q = await db.execute(select(func.count()).select_from(lockout_sub))
    quiz_lockouts: int = lockout_q.scalar_one() or 0

    completion_rate = (
        (completed_assignments / total_assignments * 100) if total_assignments > 0 else 0.0
    )

    return {
        "total_employees": 0,  # Comes from auth-service; not available in core-service
        "overdue_assignments": overdue_assignments,
        "quiz_lockouts": quiz_lockouts,
        "completion_rate": round(completion_rate, 2),
        "total_assignments": total_assignments,
        "completed_assignments": completed_assignments,
    }


# ---------------------------------------------------------------------------
# GET /dashboards/creator
# ---------------------------------------------------------------------------

@router.get("/creator")
async def creator_dashboard(
    current_user: UserAuth = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Dashboard summary for Training Creators and SysAdmins.
    """
    allowed_roles = {"Training Creator", "SysAdmin"}
    if not any(r in allowed_roles for r in current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Training Creator or SysAdmin role required.",
        )

    tenant_id = current_user.tenant_id

    # Total trainings created by this user in this tenant (not soft-deleted)
    total_q = await db.execute(
        select(func.count(Training.id)).where(
            Training.tenant_id == tenant_id,
            Training.created_by_id == current_user.id,
            Training.deleted_at.is_(None),
        )
    )
    total_trainings: int = total_q.scalar_one() or 0

    # Published trainings
    published_q = await db.execute(
        select(func.count(Training.id)).where(
            Training.tenant_id == tenant_id,
            Training.created_by_id == current_user.id,
            Training.deleted_at.is_(None),
            Training.is_published.is_(True),
        )
    )
    published: int = published_q.scalar_one() or 0

    draft = total_trainings - published

    return {
        "total_trainings": total_trainings,
        "published": published,
        "draft": draft,
    }


# ---------------------------------------------------------------------------
# GET /dashboards/employee
# ---------------------------------------------------------------------------

@router.get("/employee")
async def employee_dashboard(
    current_user: UserAuth = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Personal training dashboard for any authenticated user.
    """
    now = datetime.now(timezone.utc)
    seven_days_later = now + timedelta(days=7)
    user_id = current_user.id
    tenant_id = current_user.tenant_id

    # In-progress: assignments for this user where no completed enrollment exists — latest 5
    in_progress_q = await db.execute(
        select(TrainingAssignment).where(
            TrainingAssignment.user_id == user_id,
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.deleted_at.is_(None),
            # Exclude trainings where user has a completed enrollment
            ~TrainingAssignment.training_id.in_(
                select(Enrollment.training_id).where(
                    Enrollment.user_id == user_id,
                    Enrollment.tenant_id == tenant_id,
                    Enrollment.is_completed.is_(True),
                )
            ),
        )
        .order_by(TrainingAssignment.assigned_at.desc())
        .limit(5)
    )
    in_progress_rows = in_progress_q.scalars().all()
    in_progress = [
        {"training_id": a.training_id, "due_date": a.due_date}
        for a in in_progress_rows
    ]

    # Upcoming due: due_date within next 7 days, not yet completed
    upcoming_q = await db.execute(
        select(TrainingAssignment).where(
            TrainingAssignment.user_id == user_id,
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.deleted_at.is_(None),
            TrainingAssignment.due_date.isnot(None),
            TrainingAssignment.due_date >= now,
            TrainingAssignment.due_date <= seven_days_later,
            ~TrainingAssignment.training_id.in_(
                select(Enrollment.training_id).where(
                    Enrollment.user_id == user_id,
                    Enrollment.tenant_id == tenant_id,
                    Enrollment.is_completed.is_(True),
                )
            ),
        )
        .order_by(TrainingAssignment.due_date.asc())
    )
    upcoming_rows = upcoming_q.scalars().all()
    upcoming_due = [
        {"training_id": a.training_id, "due_date": a.due_date}
        for a in upcoming_rows
    ]

    # Recently completed: last 5 completed enrollments for this user
    completed_q = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == user_id,
            Enrollment.tenant_id == tenant_id,
            Enrollment.is_completed.is_(True),
            Enrollment.completed_at.isnot(None),
        )
        .order_by(Enrollment.completed_at.desc())
        .limit(5)
    )
    completed_rows = completed_q.scalars().all()
    recently_completed = [
        {"training_id": e.training_id, "completed_at": e.completed_at}
        for e in completed_rows
    ]

    return {
        "in_progress": in_progress,
        "upcoming_due": upcoming_due,
        "recently_completed": recently_completed,
    }


# ---------------------------------------------------------------------------
# GET /dashboards/assignments-due (internal)
# ---------------------------------------------------------------------------

@router.get("/assignments-due", dependencies=[Depends(_require_internal_key)])
async def assignments_due(
    due_after: datetime = Query(..., description="ISO datetime lower bound (inclusive)"),
    due_before: datetime = Query(..., description="ISO datetime upper bound (inclusive)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Internal endpoint — list assignments whose due_date falls within the
    [due_after, due_before] window.  Used by notification service for reminders.
    No JWT required; protected by X-Internal-Api-Key header.
    """
    # NOT EXISTS subquery: exclude assignments where a matching completed enrollment exists
    completed_enrollment = (
        select(Enrollment.id).where(
            Enrollment.user_id == TrainingAssignment.user_id,
            Enrollment.training_id == TrainingAssignment.training_id,
            Enrollment.is_completed.is_(True),
        )
    ).correlate(TrainingAssignment)

    q = await db.execute(
        select(TrainingAssignment, Training.title).join(
            Training, TrainingAssignment.training_id == Training.id
        ).where(
            TrainingAssignment.deleted_at.is_(None),
            TrainingAssignment.user_id.isnot(None),
            TrainingAssignment.due_date.isnot(None),
            TrainingAssignment.due_date >= due_after,
            TrainingAssignment.due_date <= due_before,
            not_(exists(completed_enrollment)),
        )
    )
    rows = q.all()
    return [
        {
            "user_id": a.user_id,
            "tenant_id": a.tenant_id,
            "training_id": a.training_id,
            "training_title": title,
            "due_date": a.due_date,
            "completion_lock": a.completion_lock,
        }
        for a, title in rows
    ]


# ---------------------------------------------------------------------------
# GET /dashboards/assignments-overdue (internal)
# ---------------------------------------------------------------------------

@router.get("/assignments-overdue", dependencies=[Depends(_require_internal_key)])
async def assignments_overdue(
    db: AsyncSession = Depends(get_db),
):
    """
    Internal endpoint — list assignments that are overdue (due_date < now),
    not completed, not deleted.  Used by notification service for overdue alerts.
    No JWT required; protected by X-Internal-Api-Key header.
    """
    now = datetime.now(timezone.utc)

    # NOT EXISTS subquery: exclude assignments where a matching completed enrollment exists
    completed_enrollment_overdue = (
        select(Enrollment.id).where(
            Enrollment.user_id == TrainingAssignment.user_id,
            Enrollment.training_id == TrainingAssignment.training_id,
            Enrollment.is_completed.is_(True),
        )
    ).correlate(TrainingAssignment)

    q = await db.execute(
        select(TrainingAssignment, Training.title).join(
            Training, TrainingAssignment.training_id == Training.id
        ).where(
            TrainingAssignment.deleted_at.is_(None),
            TrainingAssignment.user_id.isnot(None),
            TrainingAssignment.due_date.isnot(None),
            TrainingAssignment.due_date < now,
            not_(exists(completed_enrollment_overdue)),
        )
    )
    rows = q.all()
    return [
        {
            "user_id": a.user_id,
            "tenant_id": a.tenant_id,
            "training_id": a.training_id,
            "training_title": title,
            "due_date": a.due_date,
            "completion_lock": a.completion_lock,
        }
        for a, title in rows
    ]
