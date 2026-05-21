from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

class TrainingCollaborator(Base):
    __tablename__ = "training_collaborators"

    training_id: Mapped[str] = mapped_column(ForeignKey("trainings.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String, primary_key=True)

    training: Mapped["Training"] = relationship("Training", back_populates="collaborators")
