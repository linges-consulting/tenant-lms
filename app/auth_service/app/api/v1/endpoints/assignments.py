from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.api import deps
from app.models.user import User
from app.models.group import Group, GroupMembership
from app.models.course_assignment import CourseAssignment
from app.models.enrollment import Enrollment
from app.models.training import Training
from app.schemas.group import AssignmentOut, AssignmentCreate

router = APIRouter()


@router.get("", response_model=List[AssignmentOut])
async def list_assignments(
    db: AsyncSession = Depends(deps.get_db),
    current_manager: User = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    """List all course assignments for the active tenant."""
    result = await db.execute(
        select(CourseAssignment)
        .where(CourseAssignment.tenant_id == tenant_id)
        .options(
            selectinload(CourseAssignment.training),
            selectinload(CourseAssignment.group),
            selectinload(CourseAssignment.user),
        )
    )
    assignments = result.scalars().all()
    return [
        AssignmentOut(
            id=a.id,
            training_id=a.training_id,
            tenant_id=a.tenant_id,
            group_id=a.group_id,
            user_id=a.user_id,
            assigned_at=a.assigned_at,
            group_name=a.group.name if a.group else None,
            user_name=a.user.full_name or a.user.email if a.user else None,
            training_title=a.training.title if a.training else None,
        )
        for a in assignments
    ]


@router.post("", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    payload: AssignmentCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_manager: User = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    """
    Assign a course to a group or individual user.
    - If group_id provided: fans out Enrollment rows for all current group members.
    - If user_id provided: creates a single Enrollment row.
    - Exactly one of group_id/user_id must be set.
    """
    if bool(payload.group_id) == bool(payload.user_id):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of group_id or user_id."
        )

    # Verify training belongs to tenant
    training_res = await db.execute(
        select(Training).where(
            and_(Training.id == payload.training_id, Training.tenant_id == tenant_id)
        )
    )
    training = training_res.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found in this tenant.")

    assignment = CourseAssignment(
        training_id=payload.training_id,
        tenant_id=tenant_id,
        group_id=payload.group_id,
        user_id=payload.user_id,
        assigned_by_id=current_manager.id,
    )
    db.add(assignment)
    await db.flush()

    # Fan-out enrollments
    if payload.group_id:
        group_res = await db.execute(
            select(Group)
            .where(and_(Group.id == payload.group_id, Group.tenant_id == tenant_id))
            .options(selectinload(Group.members))
        )
        group = group_res.scalar_one_or_none()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found.")

        for gm in group.members:
            # Avoid duplicate enrollments
            exists = await db.execute(
                select(Enrollment).where(
                    and_(
                        Enrollment.user_id == gm.user_id,
                        Enrollment.training_id == payload.training_id,
                        Enrollment.tenant_id == tenant_id,
                    )
                )
            )
            if not exists.scalar_one_or_none():
                db.add(Enrollment(
                    user_id=gm.user_id,
                    training_id=payload.training_id,
                    tenant_id=tenant_id,
                ))
    else:
        # Individual enrollment
        exists = await db.execute(
            select(Enrollment).where(
                and_(
                    Enrollment.user_id == payload.user_id,
                    Enrollment.training_id == payload.training_id,
                    Enrollment.tenant_id == tenant_id,
                )
            )
        )
        if not exists.scalar_one_or_none():
            db.add(Enrollment(
                user_id=payload.user_id,
                training_id=payload.training_id,
                tenant_id=tenant_id,
            ))

    await db.commit()
    await db.refresh(assignment)

    # Load relationships for response
    res2 = await db.execute(
        select(CourseAssignment)
        .where(CourseAssignment.id == assignment.id)
        .options(
            selectinload(CourseAssignment.training),
            selectinload(CourseAssignment.group),
            selectinload(CourseAssignment.user),
        )
    )
    a = res2.scalar_one()
    return AssignmentOut(
        id=a.id, training_id=a.training_id, tenant_id=a.tenant_id,
        group_id=a.group_id, user_id=a.user_id, assigned_at=a.assigned_at,
        group_name=a.group.name if a.group else None,
        user_name=a.user.full_name or a.user.email if a.user else None,
        training_title=a.training.title if a.training else None,
    )


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    assignment_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_manager: User = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> None:
    """Remove a course assignment (does not un-enroll users already in progress)."""
    result = await db.execute(
        select(CourseAssignment).where(
            and_(CourseAssignment.id == assignment_id, CourseAssignment.tenant_id == tenant_id)
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    await db.delete(assignment)
    await db.commit()
