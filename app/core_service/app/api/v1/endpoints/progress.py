from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

from app.db.session import get_db
from app.api.deps import get_current_user, get_current_tenant_id, UserAuth
from app.models.progress import UserProgress
from app.models.chapter import Chapter
from app.models.training import Training

router = APIRouter()


class VideoProgressUpdate(BaseModel):
    training_id: str
    chapter_id: str
    position_seconds: int = 0
    milestone_25: bool = False
    milestone_50: bool = False
    milestone_75: bool = False
    milestone_100: bool = False
    video_ended: bool = False


@router.post("/video")
async def update_video_progress(
    data: VideoProgressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserAuth = Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant_id),
):
    # Verify chapter belongs to this tenant's training (tenant isolation)
    chapter_result = await db.execute(
        select(Chapter).join(Training, Chapter.training_id == Training.id).where(
            Chapter.id == data.chapter_id,
            Training.id == data.training_id,
            Training.tenant_id == tenant_id,
        )
    )
    chapter = chapter_result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    # Fetch the training to get the current version
    training_result = await db.execute(
        select(Training).where(
            Training.id == data.training_id,
            Training.tenant_id == tenant_id,
        )
    )
    training = training_result.scalar_one_or_none()

    # Upsert UserProgress — find existing non-deleted row
    result = await db.execute(
        select(UserProgress).where(
            UserProgress.user_id == current_user.id,
            UserProgress.chapter_id == data.chapter_id,
            UserProgress.tenant_id == tenant_id,
            UserProgress.deleted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        row = UserProgress(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            chapter_id=data.chapter_id,
            training_id=data.training_id,
            tenant_id=tenant_id,
            status="IN_PROGRESS",
            training_version_id=training.version if training else 1,
            attempt_id=1,
        )
        db.add(row)

    row.resume_position_seconds = data.position_seconds
    if data.milestone_25:
        row.milestone_25 = True
    if data.milestone_50:
        row.milestone_50 = True
    if data.milestone_75:
        row.milestone_75 = True
    if data.milestone_100:
        row.milestone_100 = True
    if data.video_ended and data.milestone_100:
        row.status = "COMPLETED"
        row.completed_at = datetime.now(timezone.utc)

    await db.commit()
    return {"status": row.status, "resume_position_seconds": row.resume_position_seconds}
