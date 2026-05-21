from typing import Optional
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

class Enrollment(Base):
    """
    Represents a user's enrollment and completion status in a Training.
    If is_completed is True, it can act as the 'Certificate' of completion.
    """
    __tablename__ = "enrollments"

    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    training_id: Mapped[str] = mapped_column(ForeignKey("trainings.id"), index=True, nullable=False)
    
    # Snapshot of the version the user completed
    training_version_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Store explicit generated certificate URL or ID if exported to a PDF system
    certificate_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    certificate_id: Mapped[Optional[str]] = mapped_column(ForeignKey("certificates.id"), nullable=True)
    certificate: Mapped[Optional["Certificate"]] = relationship()

    training: Mapped["Training"] = relationship()

