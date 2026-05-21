from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from app.models.user import UserStatus

class TenantMembership(Base):
    __tablename__ = "tenant_memberships"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    
    # Roles within this specific tenant
    is_business_manager: Mapped[bool] = mapped_column(Boolean, default=False)
    is_training_creator: Mapped[bool] = mapped_column(Boolean, default=False)
    is_employee: Mapped[bool] = mapped_column(Boolean, default=True)

    # Tenant-level status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.ACTIVE, server_default=UserStatus.ACTIVE.value, nullable=False)

    user: Mapped["User"] = relationship(back_populates="memberships")
    tenant: Mapped["Tenant"] = relationship(back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uix_user_tenant"),
    )

    @property
    def role(self) -> str:
        if self.is_business_manager:
            return "Business Manager"
        if self.is_training_creator:
            return "Training Creator"
        return "Employee"
