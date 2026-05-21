from pydantic import BaseModel, ConfigDict, computed_field
from typing import Optional
from .tenant import Tenant

class TenantMembershipBase(BaseModel):
    # Base fields common to all membership schemas
    tenant_id: str
    is_business_manager: bool = False
    is_training_creator: bool = False
    is_employee: bool = True
    is_active: bool = True
    status: Optional[str] = "ACTIVE"

class TenantMembership(TenantMembershipBase):
    tenant: Optional[Tenant] = None
    
    @computed_field
    @property
    def role(self) -> str:
        """
        Dynamically compute the role label based on boolean flags.
        This ensures the label is always consistent with the underlying data.
        """
        if self.is_business_manager:
            return "Business Manager"
        if self.is_training_creator:
            return "Training Creator"
        return "Employee"

    model_config = ConfigDict(from_attributes=True)
