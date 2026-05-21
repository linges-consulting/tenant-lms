from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    action: Mapped[str] = mapped_column(String, index=True, nullable=False) # ENROLL, COMPLETE, SUBMIT, ARCHIVE
    entity_type: Mapped[str] = mapped_column(String, index=True, nullable=False) # training, module, chapter
    entity_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True)
