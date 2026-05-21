from typing import Optional
from sqlalchemy import String, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from datetime import datetime, timezone

class TrainingAssignment(Base):
    __tablename__ = "training_assignments"

    training_id: Mapped[str] = mapped_column(ForeignKey("trainings.id", ondelete="CASCADE"), index=True, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # Assignment targets
    user_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    group_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)

    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Phase 3 fields
    completion_lock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    attempt_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    training: Mapped["Training"] = relationship("Training", back_populates="assignments")
