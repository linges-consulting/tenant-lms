from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base
from datetime import datetime, timezone

class TrainingHistory(Base):
    __tablename__ = "training_histories"

    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    training_id: Mapped[str] = mapped_column(ForeignKey("trainings.id"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
