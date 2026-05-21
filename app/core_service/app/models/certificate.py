from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

if TYPE_CHECKING:
    from .training import Training
    from .certificate_template import CertificateTemplate

class Certificate(Base):
    """
    Represents an issued certificate for a specific user and training.
    """
    __tablename__ = "certificates"

    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    training_id: Mapped[str] = mapped_column(ForeignKey("trainings.id"), index=True, nullable=False)
    template_id: Mapped[str] = mapped_column(ForeignKey("certificate_templates.id"), index=True, nullable=False)
    
    certificate_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # JSON data to store variables used in the template (e.g., user name, completion date)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)

    training: Mapped["Training"] = relationship()
    template: Mapped["CertificateTemplate"] = relationship()
