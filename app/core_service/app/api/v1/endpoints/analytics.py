from __future__ import annotations

import csv
import html
import io
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import Integer, func, select, and_, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.events import publisher
from app.db.session import get_db
from app.utils.pdf import render_certificate_pdf
from app.models.assignment import TrainingAssignment
from app.models.chapter import Chapter, ContentType
from app.models.enrollment import Enrollment
from app.models.progress import UserProgress
from app.models.quiz_attempt import QuizAttempt
from app.models.training import Training

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

    # Build enrolled user sets per training by unioning two sources:
    # 1. Direct user assignments (TrainingAssignment.user_id) — covers assignments
    #    made via the core-service bulk endpoint which doesn't create Enrollment rows.
    # 2. Enrollment records — covers group fan-out created by the auth-service path.
    # Deduplicating in Python ensures a user assigned both ways counts once.
    enrolled_user_sets: dict[str, set[str]] = defaultdict(set)

    direct_asgn_rows = await db.execute(
        select(TrainingAssignment.training_id, TrainingAssignment.user_id).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.training_id.in_(training_ids),
            TrainingAssignment.deleted_at.is_(None),
            TrainingAssignment.user_id.isnot(None),
        )
    )
    for tid, uid in direct_asgn_rows.all():
        enrolled_user_sets[tid].add(uid)

    enroll_rows = await db.execute(
        select(Enrollment.training_id, Enrollment.user_id).where(
            Enrollment.tenant_id == tenant_id,
            Enrollment.training_id.in_(training_ids),
        )
    )
    for tid, uid in enroll_rows.all():
        enrolled_user_sets[tid].add(uid)

    # 3. UserProgress — catches group-assigned users who have started the training
    #    even when no Enrollment record exists (core-service group assignments don't
    #    fan out Enrollment rows).
    progress_rows = await db.execute(
        select(UserProgress.training_id, UserProgress.user_id).where(
            UserProgress.tenant_id == tenant_id,
            UserProgress.training_id.in_(training_ids),
            UserProgress.deleted_at.is_(None),
        ).distinct()
    )
    for tid, uid in progress_rows.all():
        enrolled_user_sets[tid].add(uid)

    enrolled_map: dict[str, int] = {tid: len(uids) for tid, uids in enrolled_user_sets.items()}

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

    # Overdue: enrolled users (from any assignment type) who have not completed
    # and whose training has a past-due assignment record (user-level or group-level).
    # We count enrolled-but-incomplete users for trainings that have at least one
    # past-due assignment, covering both direct and group assignment due dates.
    overdue_training_ids_q = await db.execute(
        select(func.distinct(TrainingAssignment.training_id)).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.training_id.in_(training_ids),
            TrainingAssignment.deleted_at.is_(None),
            TrainingAssignment.due_date.isnot(None),
            TrainingAssignment.due_date < now,
        )
    )
    overdue_training_ids = {row[0] for row in overdue_training_ids_q.all()}

    overdue_map: dict[str, int] = defaultdict(int)
    if overdue_training_ids:
        overdue_enrolled_q = await db.execute(
            select(Enrollment.training_id, func.count(func.distinct(Enrollment.user_id)))
            .where(
                Enrollment.tenant_id == tenant_id,
                Enrollment.training_id.in_(list(overdue_training_ids)),
                Enrollment.is_completed.is_(False),
            )
            .group_by(Enrollment.training_id)
        )
        for row in overdue_enrolled_q.all():
            overdue_map[row[0]] = row[1]

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
    chapter_max = {c.id: (c.content_data or {}).get("max_attempts", 0) for c in quiz_chapters}

    lockout_map: dict[str, int] = defaultdict(int)
    if quiz_chapters:
        chapter_ids = [c.id for c in quiz_chapters]
        attempts_q = await db.execute(
            select(
                QuizAttempt.chapter_id,
                QuizAttempt.user_id,
                func.max(QuizAttempt.attempt_number).label("max_att"),
                func.sum(QuizAttempt.passed.cast(Integer)).label("pass_count"),
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
            if max_allowed and max_att >= max_allowed and not (pass_cnt or 0):
                tid_for_chapter = chapter_to_training.get(cid)
                if tid_for_chapter:
                    lockout_map[tid_for_chapter] += 1

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

    # Fetch all assignment records — both direct (user_id) and group-based (group_id).
    all_asgn_q = await db.execute(
        select(TrainingAssignment).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.training_id == training_id,
            TrainingAssignment.deleted_at.is_(None),
        )
    )
    all_assignments = all_asgn_q.scalars().all()
    direct_assignments = [a for a in all_assignments if a.user_id]
    group_assignments = [a for a in all_assignments if a.group_id]

    # Resolve group members so their due_dates can be inferred from the group assignment.
    group_ids = [a.group_id for a in group_assignments]
    group_members_map: dict[str, list[str]] = await deps.get_group_members_batch(group_ids)

    # Build user_id → due_date: group assignment applies to its members;
    # direct assignment overrides if the same user also has one.
    user_due_date: dict[str, Optional[datetime]] = {}
    for a in group_assignments:
        for uid in group_members_map.get(a.group_id or "", []):
            user_due_date[uid] = a.due_date
    for a in direct_assignments:
        user_due_date[a.user_id] = a.due_date  # direct always wins

    # Enrolled users come from Enrollment records — already fanned out for groups.
    enroll_q = await db.execute(
        select(Enrollment).where(
            Enrollment.tenant_id == tenant_id,
            Enrollment.training_id == training_id,
        )
    )
    enrollments = {e.user_id: e for e in enroll_q.scalars().all()}

    # Union of direct-assigned users + group members + enrolled users (covers all cases).
    user_ids = list({
        *[a.user_id for a in direct_assignments],
        *[uid for gid, uids in group_members_map.items() for uid in uids],
        *list(enrollments.keys()),
    })
    enrolled_count = len(set(user_ids))

    if not user_ids:
        return _empty_detail(training, 0)

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
    chapter_max = {c.id: (c.content_data or {}).get("max_attempts", 0) for c in quiz_chapters}

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

    att_by_chapter_user: dict[tuple, list] = defaultdict(list)
    for a in attempt_rows:
        att_by_chapter_user[(a.chapter_id, a.user_id)].append(a)

    user_quiz_summary: dict[str, dict] = defaultdict(dict)
    for (cid, uid), atts in att_by_chapter_user.items():
        max_att_num = max(a.attempt_number for a in atts)
        passed = any(a.passed for a in atts)
        user_quiz_summary[uid][cid] = {
            "attempt_count": max_att_num,
            "max_attempts": chapter_max.get(cid, 0),
            "passed": passed,
        }

    quiz_stats = []
    for ch in quiz_chapters:
        cid = ch.id
        max_allowed = chapter_max.get(cid, 0)
        users_attempted = {uid for (c, uid) in att_by_chapter_user if c == cid}
        attempted_count = len(users_attempted)
        pass_users = {uid for uid in users_attempted if user_quiz_summary[uid].get(cid, {}).get("passed")}
        pass_count = len(pass_users)
        locked_users = {
            uid for uid in users_attempted
            if max_allowed and user_quiz_summary[uid][cid]["attempt_count"] >= max_allowed
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

    completed_count = sum(1 for e in enrollments.values() if e.is_completed)

    def _due_date_for(uid: str) -> Optional[datetime]:
        d = user_due_date.get(uid)
        if d is None:
            return None
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

    def _is_overdue_uid(uid: str) -> bool:
        due = _due_date_for(uid)
        if not due:
            return False
        enroll = enrollments.get(uid)
        return due < now and not (enroll and enroll.is_completed)

    overdue_count = sum(1 for uid in user_ids if _is_overdue_uid(uid))

    def _due_soon(days: int) -> int:
        cutoff = now + timedelta(days=days)
        return sum(
            1 for uid in user_ids
            if (due := _due_date_for(uid))
            and now <= due <= cutoff
            and not (enrollments.get(uid) and enrollments[uid].is_completed)
        )

    lockout_count = sum(
        1 for uid in user_ids
        if any(
            info["max_attempts"] and info["attempt_count"] >= info["max_attempts"] and not info["passed"]
            for info in user_quiz_summary.get(uid, {}).values()
        )
    )

    all_user_ids = user_ids + ([training.created_by_id] if training.created_by_id else [])
    users_data = await deps.get_users_batch(list(set(all_user_ids)))

    prog_q = await db.execute(
        select(UserProgress.user_id).where(
            UserProgress.tenant_id == tenant_id,
            UserProgress.training_id == training_id,
        ).distinct()
    )
    users_with_progress = {row[0] for row in prog_q.all()}

    def _employee_status(uid: str) -> str:
        enroll = enrollments.get(uid)
        if enroll and enroll.is_completed:
            return "completed"
        locked = any(
            info["max_attempts"] and info["attempt_count"] >= info["max_attempts"] and not info["passed"]
            for info in user_quiz_summary.get(uid, {}).values()
        )
        if locked:
            return "locked"
        if _is_overdue_uid(uid):
            return "overdue"
        if uid in users_with_progress:
            return "in_progress"
        return "not_started"

    employees = []
    for uid in user_ids:
        uinfo = users_data.get(uid, {})
        enroll = enrollments.get(uid)
        due = user_due_date.get(uid)
        locked_count = sum(
            1 for info in user_quiz_summary.get(uid, {}).values()
            if info["max_attempts"] and info["attempt_count"] >= info["max_attempts"] and not info["passed"]
        )
        employees.append({
            "user_id": uid,
            "username": uinfo.get("username", ""),
            "full_name": uinfo.get("full_name", ""),
            "email": uinfo.get("email", ""),
            "status": _employee_status(uid),
            "due_date": due.isoformat() if due else None,
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

    # Verify the user is assigned to this training within this tenant
    asgn_check = await db.execute(
        select(TrainingAssignment.id).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.training_id == training_id,
            TrainingAssignment.user_id == user_id,
            TrainingAssignment.deleted_at.is_(None),
        ).limit(1)
    )
    if not asgn_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Employee not found in this training")

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
        max_allowed = (chapter.content_data or {}).get("max_attempts", 0)
        atts = grouped.get(cid, [])
        result.append({
            "chapter_id": cid,
            "chapter_title": chapter.title,
            "max_attempts": max_allowed,
            "attempts": atts,
            "is_locked": bool(atts) and max(a["attempt_number"] for a in atts) >= max_allowed > 0 and not any(a["passed"] for a in atts),
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
    user_ids: list[str] = body.get("user_ids", [])
    if not user_ids:
        raise HTTPException(status_code=422, detail="user_ids required")

    training = await db.get(Training, training_id)
    if not training or training.tenant_id != tenant_id or training.deleted_at:
        raise HTTPException(status_code=404, detail="Training not found")

    asgn_q = await db.execute(
        select(TrainingAssignment).where(
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.training_id == training_id,
            TrainingAssignment.user_id.in_(user_ids),
            TrainingAssignment.deleted_at.is_(None),
        )
    )
    asgn_map = {a.user_id: a for a in asgn_q.scalars().all()}
    # Only fetch PII for users with a verified assignment in this tenant+training
    users_data = await deps.get_users_batch(list(asgn_map.keys()))

    # Iterate over validated asgn_map — not the raw request body — to prevent
    # reminders being sent to users not assigned to this training.
    for uid, asgn in asgn_map.items():
        uinfo = users_data.get(uid, {})
        await publisher.publish_event(
            "TRAINING_REMINDER",
            {
                "tenant_id": tenant_id,
                "user_id": uid,
                "user_email": uinfo.get("email", ""),
                "training_id": training_id,
                "training_title": training.title,
                "due_date": asgn.due_date.strftime("%B %d, %Y") if asgn.due_date else "No due date",
                "manager_name": current_user.full_name or "Your manager",
            },
        )
    return {"sent": len(asgn_map)}


_LIST_CSV_HEADERS = [
    "Title", "Category", "Creator", "Status", "Enrolled",
    "Completed", "Completion %", "Overdue", "Lockouts", "Last Updated",
]

_DETAIL_CSV_HEADERS = [
    "Name", "Email", "Status", "Due Date", "Completed At",
    "Locked Quizzes", "Quiz Attempts Summary",
]

_REPORT_HTML = """
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
<h1>{title}</h1>
<p class="meta">Generated {date}</p>
<table><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>
</body></html>
"""


@router.get("/report")
async def analytics_list_report(
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    trainings_data = await analytics_training_list(db=db, current_user=current_user, tenant_id=tenant_id)
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

    header_cells = "".join(f"<th>{h}</th>" for h in _LIST_CSV_HEADERS)
    body_rows = ""
    for row in trainings_data:
        cells = "".join(f"<td>{html.escape(str(v))}</td>" for v in [
            row["title"], row["category"], row["creator_name"],
            "Published" if row["is_published"] else "Draft",
            row["enrolled_count"], row["completed_count"],
            f"{row['completion_pct']}%", row["overdue_count"],
            row["lockout_count"], (row.get("updated_at") or "")[:10],
        ])
        body_rows += f"<tr>{cells}</tr>"
    html_content = _REPORT_HTML.format(
        title="Training Analytics Report",
        date=date_str,
        headers=header_cells,
        rows=body_rows,
    )
    pdf_bytes = render_certificate_pdf(html_content, {})
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=training-analytics-{date_str}.pdf"},
    )


@router.get("/trainings/{training_id}/report")
async def analytics_detail_report(
    training_id: str,
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    detail = await analytics_training_detail(
        training_id=training_id, db=db, current_user=current_user, tenant_id=tenant_id
    )
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    safe_title = detail["title"].replace(" ", "-")[:30]

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(_DETAIL_CSV_HEADERS)
        for emp in detail["employees"]:
            quiz_summary = "; ".join(
                f"{qa['attempt_count']}/{qa['max_attempts']} {'pass' if qa['passed'] else 'fail'}"
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

    header_cells = "".join(f"<th>{h}</th>" for h in _DETAIL_CSV_HEADERS)
    body_rows = ""
    for emp in detail["employees"]:
        quiz_summary = ", ".join(
            f"{qa['attempt_count']}/{qa['max_attempts']}"
            for qa in emp.get("quiz_attempts", [])
        )
        cells = "".join(f"<td>{html.escape(str(v))}</td>" for v in [
            emp["full_name"], emp["email"], emp["status"],
            (emp.get("due_date") or "")[:10], (emp.get("completed_at") or "")[:10],
            emp["locked_quiz_count"], quiz_summary,
        ])
        body_rows += f"<tr>{cells}</tr>"
    html_content = _REPORT_HTML.format(
        title=html.escape(f"Analytics: {detail['title']}"),
        date=date_str,
        headers=header_cells,
        rows=body_rows,
    )
    pdf_bytes = render_certificate_pdf(html_content, {})
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={safe_title}-analytics-{date_str}.pdf"},
    )


@router.get("/profile/{user_id}")
async def analytics_profile_history(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """Training history for one user, accessible by the user themselves or privileged roles."""
    is_self = current_user.id == user_id
    is_authorized = is_self or any(
        r in {"Business Manager", "Training Creator", "SysAdmin"}
        for r in current_user.roles
    )
    if not is_authorized:
        raise HTTPException(status_code=403, detail="Not authorised to view this profile")

    now = datetime.now(timezone.utc)

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

    tr_q = await db.execute(
        select(Training).where(
            Training.id.in_(training_ids),
            Training.tenant_id == tenant_id,
            Training.deleted_at.is_(None),
        )
    )
    trainings = {t.id: t for t in tr_q.scalars().all()}

    enroll_q = await db.execute(
        select(Enrollment).where(
            Enrollment.tenant_id == tenant_id,
            Enrollment.user_id == user_id,
            Enrollment.training_id.in_(training_ids),
        )
    )
    enrollments = {e.training_id: e for e in enroll_q.scalars().all()}

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

    quiz_passed_by_tr: dict[str, int] = defaultdict(int)
    if quiz_chs:
        att_q = await db.execute(
            select(QuizAttempt.chapter_id, QuizAttempt.passed).where(
                QuizAttempt.tenant_id == tenant_id,
                QuizAttempt.user_id == user_id,
                QuizAttempt.chapter_id.in_(list(chapter_to_tr.keys())),
                QuizAttempt.deleted_at.is_(None),
            )
        )
        passed_chapters: set[str] = set()
        for cid, passed in att_q.all():
            if passed and cid not in passed_chapters:
                passed_chapters.add(cid)
                quiz_passed_by_tr[chapter_to_tr[cid]] += 1

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
        elif (
            asgn.due_date and not (enroll and enroll.is_completed)
            and (asgn.due_date if asgn.due_date.tzinfo else asgn.due_date.replace(tzinfo=timezone.utc)) < now
        ):
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
            "quiz_passed": quiz_passed_by_tr.get(tid_tr, 0),
            "certificate_id": enroll.certificate_id if enroll and hasattr(enroll, "certificate_id") else None,
        })
    return result


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
