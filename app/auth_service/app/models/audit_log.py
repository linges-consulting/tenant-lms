import uuid
from datetime import datetime, timezone
from sqlalchemy import String, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    actor_id: Mapped[str] = mapped_column(String, nullable=False, index=True)  # SysAdmin user_id
    actor_email: Mapped[str] = mapped_column(String, nullable=False)
    target_user_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)  # e.g. "NAME_CHANGE"
    details: Mapped[dict] = mapped_column(JSON, nullable=True)  # e.g. {"old_name": "...", "new_name": "...", "reason": "..."}
