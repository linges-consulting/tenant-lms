from typing import List, Optional
from enum import Enum as PyEnum
from sqlalchemy import String, Boolean, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base


class UserStatus(PyEnum):
    """User account status states"""
    PENDING = "PENDING"        # Invited but hasn't completed registration
    ACTIVE = "ACTIVE"          # Fully registered and active
    INACTIVE = "INACTIVE"      # Admin-deactivated account

class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, nullable=True)
    # Optional because invited users haven't set a password yet
    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    theme_preference: Mapped[str] = mapped_column(String, default="system", server_default="system")
    role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_sysadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.PENDING, server_default=UserStatus.PENDING.value, nullable=False)

    memberships: Mapped[List["TenantMembership"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    user_tokens: Mapped[List["UserToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
