import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from nanoid import generate

if TYPE_CHECKING:
    from .user import User

def generate_token():
    # Use nanoid for reasonably short, URL-safe tokens
    return generate(size=16)

class UserToken(Base):
    __tablename__ = "user_tokens"

    # id is already in Base
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    
    token: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False, default=generate_token)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc) + timedelta(days=7))
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # created_at, updated_at, deleted_at are inherited from Base
    
    user: Mapped["User"] = relationship(back_populates="user_tokens")
