from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Boolean, Integer, ForeignKey, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

class Training(Base):
    __tablename__ = "trainings"

    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    duration: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    thumbnail: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    requires_certificate: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    template_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("certificate_templates.id"), nullable=True)
    created_by_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)

    # Phase 3 fields
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    structure_type: Mapped[str] = mapped_column(String(20), nullable=False, default="flat", server_default="flat")
    requires_recertification: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    recertification_period_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    template: Mapped[Optional["CertificateTemplate"]] = relationship("CertificateTemplate")

    modules: Mapped[List["Module"]] = relationship(back_populates="training", cascade="all, delete-orphan")
    chapters: Mapped[List["Chapter"]] = relationship(back_populates="training", cascade="all, delete-orphan")
    collaborators: Mapped[List["TrainingCollaborator"]] = relationship("TrainingCollaborator", back_populates="training", cascade="all, delete-orphan")
    assignments: Mapped[List["TrainingAssignment"]] = relationship("TrainingAssignment", back_populates="training", cascade="all, delete-orphan")
