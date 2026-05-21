from typing import List, Optional
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

class Tenant(Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    primary_color: Mapped[str] = mapped_column(String, default="#000000", server_default="#000000")
    secondary_color: Mapped[str] = mapped_column(String, default="#ffffff", server_default="#ffffff")
    logo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    memberships: Mapped[List["TenantMembership"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    groups: Mapped[List["Group"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
