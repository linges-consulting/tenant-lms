from enum import Enum as PyEnum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Boolean, ForeignKey, Enum, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

class ProgressStatus(str, PyEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

class UserProgress(Base):
    __tablename__ = "user_progress"

    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    training_id: Mapped[str] = mapped_column(ForeignKey("trainings.id"), index=True, nullable=False)
    chapter_id: Mapped[str] = mapped_column(ForeignKey("chapters.id"), index=True, nullable=False)

    status: Mapped[ProgressStatus] = mapped_column(Enum(ProgressStatus, name="user_progress_status"), default=ProgressStatus.IN_PROGRESS)
    training_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Phase 3 fields — video progress & milestones
    resume_position_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    milestone_25: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    milestone_50: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    milestone_75: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    milestone_100: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    attempt_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        UniqueConstraint("user_id", "chapter_id", name="uix_user_chapter_progress"),
    )
