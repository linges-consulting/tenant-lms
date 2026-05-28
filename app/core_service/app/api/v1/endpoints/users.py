from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List, Optional
from datetime import datetime, timezone

from app.api import deps
from app.core.cache import cache_response, invalidate_cache
from app.core.config import settings
from app.models.training import Training
from app.models.progress import UserProgress, ProgressStatus
from app.models.enrollment import Enrollment
from app.schemas.user_stats import UserStats, UserCertificate

router = APIRouter()

@router.get("/me/stats", response_model=UserStats)
@cache_response("user_stats", expire=settings.CACHE_TTL_SHORT, include_user_id=True)
async def get_my_stats(
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Get statistics for the current user in the active tenant.
    """
    user_id = current_user.id
    
    # Completed Courses (Enrolled and is_completed=True)
    completed_stmt = select(func.count(Enrollment.id)).where(
        Enrollment.user_id == user_id,
        Enrollment.tenant_id == tenant_id,
        Enrollment.is_completed == True
    )
    completed_count = (await db.execute(completed_stmt)).scalar() or 0
    
    # Total Enrollments
    enrollment_stmt = select(func.count(Enrollment.id)).where(
        Enrollment.user_id == user_id,
        Enrollment.tenant_id == tenant_id
    )
    total_enrollments = (await db.execute(enrollment_stmt)).scalar() or 0
    
    # In Progress (Have enrollment but not completed)
    in_progress_stmt = select(func.count(Enrollment.id)).where(
        Enrollment.user_id == user_id,
        Enrollment.tenant_id == tenant_id,
        Enrollment.is_completed == False
    )
    in_progress_count = (await db.execute(in_progress_stmt)).scalar() or 0
    
    return UserStats(
        completed_courses=completed_count,
        in_progress_courses=in_progress_count,
        total_enrollments=total_enrollments,
        certificates_earned=completed_count
    )

@router.get("/me/certificates", response_model=List[UserCertificate])
async def get_my_certificates(
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Get latest completed certificates for the current user.
    """
    stmt = (
        select(Enrollment, Training.title)
        .join(Training, Enrollment.training_id == Training.id)
        .where(
            Enrollment.user_id == current_user.id,
            Enrollment.tenant_id == tenant_id,
            Enrollment.is_completed == True
        )
        .order_by(Enrollment.completed_at.desc())
    )
    result = await db.execute(stmt)
    certificates = []
    for row in result.all():
        enrollment = row[0]
        training_title = row[1]
        
        if not enrollment:
            continue
            
        certificates.append(UserCertificate(
            id=str(enrollment.id),
            training_id=str(enrollment.training_id),
            training_title=str(training_title or "Unknown Training"),
            completed_at=enrollment.completed_at or datetime.now(timezone.utc),
            certificate_url=enrollment.certificate_url,
            certificate_id=str(enrollment.certificate_id) if enrollment.certificate_id else None
        ))
    return certificates

@router.get("/{user_id}/stats", response_model=UserStats)
async def get_user_stats(
    user_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_user),
    tenant_id: Optional[str] = Depends(deps.get_optional_tenant_id),
):
    """
    Admin/Manager/SysAdmin: Get statistics for a specific user.
    """
    is_sysadmin = current_user.is_global or "SysAdmin" in current_user.roles
    is_authorized = is_sysadmin or any(role in ["Business Manager", "Admin"] for role in current_user.roles)
    
    if not is_authorized and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    if not is_sysadmin and not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant scope required")

    completed_filters = [Enrollment.user_id == user_id, Enrollment.is_completed == True]
    in_progress_filters = [Enrollment.user_id == user_id, Enrollment.is_completed == False]
    total_filters = [Enrollment.user_id == user_id]

    if tenant_id:
        completed_filters.append(Enrollment.tenant_id == tenant_id)
        in_progress_filters.append(Enrollment.tenant_id == tenant_id)
        total_filters.append(Enrollment.tenant_id == tenant_id)

    completed_stmt = select(func.count(Enrollment.id)).where(*completed_filters)
    completed_count = (await db.execute(completed_stmt)).scalar() or 0
    
    in_progress_stmt = select(func.count(Enrollment.id)).where(*in_progress_filters)
    in_progress_count = (await db.execute(in_progress_stmt)).scalar() or 0

    total_enrollments_stmt = select(func.count(Enrollment.id)).where(*total_filters)
    total_enrollments = (await db.execute(total_enrollments_stmt)).scalar() or 0
    
    return UserStats(
        completed_courses=completed_count,
        in_progress_courses=in_progress_count,
        total_enrollments=total_enrollments,
        certificates_earned=completed_count
    )

@router.get("/{user_id}/certificates", response_model=List[UserCertificate])
async def get_user_certificates(
    user_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_user),
    tenant_id: Optional[str] = Depends(deps.get_optional_tenant_id),
):
    """
    Admin/Manager/SysAdmin: Get certificates for a specific user.
    """
    is_sysadmin = current_user.is_global or "SysAdmin" in current_user.roles
    is_authorized = is_sysadmin or any(role in ["Business Manager", "Admin"] for role in current_user.roles)
    
    if not is_authorized and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    if not is_sysadmin and not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant scope required")

    filters = [
        Enrollment.user_id == user_id,
        Enrollment.is_completed == True
    ]
    if tenant_id:
        filters.append(Enrollment.tenant_id == tenant_id)

    stmt = (
        select(Enrollment, Training.title)
        .join(Training, Enrollment.training_id == Training.id)
        .where(*filters)
        .order_by(Enrollment.completed_at.desc())
    )
    result = await db.execute(stmt)
    certificates = []
    for row in result.all():
        enrollment = row[0]
        training_title = row[1]
        
        if not enrollment:
            continue
            
        certificates.append(UserCertificate(
            id=str(enrollment.id),
            training_id=str(enrollment.training_id),
            training_title=str(training_title or "Unknown Training"),
            completed_at=enrollment.completed_at or datetime.now(timezone.utc),
            certificate_url=enrollment.certificate_url,
            certificate_id=str(enrollment.certificate_id) if enrollment.certificate_id else None
        ))
    return certificates
