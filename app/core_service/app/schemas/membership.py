from pydantic import BaseModel, ConfigDict, computed_field
from typing import Optional
from .tenant import Tenant

class TenantMembershipBase(BaseModel):
    role: str
    tenant_id: str
    is_business_manager: bool = False
    is_training_creator: bool = False
    is_employee: bool = True

class TenantMembership(TenantMembershipBase):
    tenant: Optional[Tenant] = None
    model_config = ConfigDict(from_attributes=True)
