from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

# Shared properties
class TenantBase(BaseModel):
    name: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$")
    secondary_color: Optional[str] = Field(None, pattern=r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$")
    logo_url: Optional[str] = None
    is_active: Optional[bool] = True

# Properties to receive on item creation
class TenantCreate(TenantBase):
    name: str
    admin_email: str
    admin_name: str

# Properties to receive on item update
class TenantUpdate(TenantBase):
    pass

# Properties shared by models stored in DB
class TenantInDBBase(TenantBase):
    id: str
    model_config = ConfigDict(from_attributes=True)

# Properties to return to client
class Tenant(TenantInDBBase):
    user_count: Optional[int] = 0
    course_count: Optional[int] = 0
    certificate_count: Optional[int] = 0
