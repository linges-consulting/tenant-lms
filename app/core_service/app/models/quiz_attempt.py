from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    chapter_id: Mapped[str] = mapped_column(String, ForeignKey("chapters.id", ondelete="CASCADE"), index=True, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    answers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Phase 3 field — links quiz attempt to the enrollment attempt cycle
    enrollment_attempt_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
