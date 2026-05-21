from enum import Enum as PyEnum
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

class ContentType(str, PyEnum):
    VIDEO = "VIDEO"
    PDF = "PDF"
    SCORM = "SCORM"
    QUIZ = "QUIZ"
    RICH_TEXT = "RICH_TEXT"

class Chapter(Base):
    __tablename__ = "chapters"

    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    training_id: Mapped[str] = mapped_column(ForeignKey("trainings.id"), index=True, nullable=False)
    module_id: Mapped[Optional[str]] = mapped_column(ForeignKey("modules.id"), index=True, nullable=True)
    
    title: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType, name="chapter_content_type"), nullable=False)
    content_data: Mapped[dict] = mapped_column(JSON, nullable=False)  # URLs, text content, questions
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="can_continue", server_default="can_continue")

    training: Mapped["Training"] = relationship(back_populates="chapters")
    module: Mapped[Optional["Module"]] = relationship(back_populates="chapters")
