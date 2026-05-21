from typing import List, Optional
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

class Module(Base):
    __tablename__ = "modules"

    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    training_id: Mapped[str] = mapped_column(ForeignKey("trainings.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)

    training: Mapped["Training"] = relationship(back_populates="modules")
    chapters: Mapped[List["Chapter"]] = relationship(back_populates="module")
