from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

# Shared properties
class CertificateBase(BaseModel):
    training_id: str
    training_version_id: Optional[int] = None
    is_completed: bool
    completed_at: Optional[datetime] = None
    certificate_url: Optional[str] = None

# Properties shared by models stored in DB
class CertificateInDBBase(CertificateBase):
    id: str
    user_id: str
    tenant_id: str
    enrolled_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Properties to return to client
class Certificate(CertificateInDBBase):
    training_title: Optional[str] = None # Filled in manually based on join
