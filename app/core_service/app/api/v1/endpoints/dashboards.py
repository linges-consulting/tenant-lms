"""
Dashboard endpoints — Manager, Creator, Employee views + internal reminder endpoints.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy import select, func, and_, not_, or_, exists, Integer, distinct
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

    # Overdue assignments — due_date < now, not completed.
    # User-level: check that no completed enrollment exists for that user+training.
    # Group-level: group membership data lives in auth-service so we count the
    # assignment row itself as overdue (conservative — manager can see the group name).
    overdue_user_q = await db.execute(
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
    overdue_group_q = await db.execute(
        select(func.count(TrainingAssignment.id)).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.deleted_at.is_(None),
            TrainingAssignment.group_id.isnot(None),
            TrainingAssignment.due_date.isnot(None),
            TrainingAssignment.due_date < now,
        )
    )
    overdue_assignments: int = (overdue_user_q.scalar_one() or 0) + (overdue_group_q.scalar_one() or 0)

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

    # Total published trainings in this tenant
    published_q = await db.execute(
        select(func.count(Training.id)).where(
            Training.tenant_id == tenant_id,
            Training.is_published.is_(True),
            Training.deleted_at.is_(None),
        )
    )
    total_trainings: int = published_q.scalar_one() or 0

    return {
        "total_trainings": total_trainings,
        "active_assignments": total_assignments,
        "overdue_count": overdue_assignments,
        "quiz_lockouts": quiz_lockouts,
        "completion_rate": round(completion_rate, 2),
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

    draft_count = total_trainings - published

    return {
        "total_trainings": total_trainings,
        "published_count": published,
        "draft_count": draft_count,
        "total_enrollments": 0,
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
    Returns stat counts for the 4 learner dashboard cards.
    """
    now = datetime.now(timezone.utc)
    user_id = current_user.id
    tenant_id = current_user.tenant_id

    # Subquery: training_ids this user has completed
    completed_training_ids_sq = (
        select(Enrollment.training_id).where(
            Enrollment.user_id == user_id,
            Enrollment.tenant_id == tenant_id,
            Enrollment.is_completed.is_(True),
        )
    )

    # Build assignee filter once — reused by assigned and overdue queries
    assignee_filter = [TrainingAssignment.user_id == user_id]
    if current_user.groups:
        assignee_filter.append(TrainingAssignment.group_id.in_(current_user.groups))

    # Assigned trainings: distinct published trainings with an active assignment (not yet completed)
    assigned_q = await db.execute(
        select(func.count(distinct(TrainingAssignment.training_id))).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.deleted_at.is_(None),
            or_(*assignee_filter),
            ~TrainingAssignment.training_id.in_(completed_training_ids_sq),
            exists(
                select(Training.id).where(
                    Training.id == TrainingAssignment.training_id,
                    Training.is_published.is_(True),
                    Training.is_archived.is_(False),
                )
            ),
        )
    )
    assigned_trainings: int = assigned_q.scalar_one() or 0

    # In-progress: has a non-completed enrollment (user started but not finished)
    in_progress_q = await db.execute(
        select(func.count(distinct(Enrollment.training_id))).where(
            Enrollment.user_id == user_id,
            Enrollment.tenant_id == tenant_id,
            Enrollment.is_completed.is_(False),
        )
    )
    in_progress_trainings: int = in_progress_q.scalar_one() or 0

    # Completed: distinct trainings with a completed enrollment
    completed_count_q = await db.execute(
        select(func.count(distinct(Enrollment.training_id))).where(
            Enrollment.user_id == user_id,
            Enrollment.tenant_id == tenant_id,
            Enrollment.is_completed.is_(True),
        )
    )
    completed_trainings: int = completed_count_q.scalar_one() or 0

    # Overdue: active assignment past due_date, not completed
    # Reuses assignee_filter which covers both direct and group assignments
    overdue_q = await db.execute(
        select(func.count(distinct(TrainingAssignment.training_id))).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.deleted_at.is_(None),
            TrainingAssignment.due_date.isnot(None),
            TrainingAssignment.due_date < now,
            or_(*assignee_filter),
            ~TrainingAssignment.training_id.in_(completed_training_ids_sq),
        )
    )
    overdue_trainings: int = overdue_q.scalar_one() or 0

    return {
        "assigned_trainings": assigned_trainings,
        "in_progress_trainings": in_progress_trainings,
        "completed_trainings": completed_trainings,
        "overdue_trainings": overdue_trainings,
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
