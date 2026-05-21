from typing import List, Optional
from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

class Group(Base):
    __tablename__ = "groups"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="groups")
    members: Mapped[List["GroupMembership"]] = relationship(back_populates="group", cascade="all, delete-orphan")

class GroupMembership(Base):
    __tablename__ = "group_memberships"

    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)

    group: Mapped["Group"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uix_group_user"),
    )
