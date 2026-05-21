from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict

# Certificate Template
class CertificateTemplateBase(BaseModel):
    name: str
    html_content: str
    is_active: bool = True
    is_default: bool = False

class CertificateTemplateCreate(CertificateTemplateBase):
    target_tenant_id: Optional[str] = None

class CertificateTemplateUpdate(BaseModel):
    name: Optional[str] = None
    html_content: Optional[str] = None
    is_active: Optional[bool] = None

class CertificateTemplate(CertificateTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime

class CertificateTemplateWithUsage(CertificateTemplate):
    is_in_use: bool = False

# Certificate
class CertificateBase(BaseModel):
    user_id: str
    training_id: str
    template_id: str
    certificate_number: str
    issued_at: datetime
    expires_at: Optional[datetime] = None
    data: Dict[str, Any] = {}

class CertificateCreate(CertificateBase):
    tenant_id: str

class Certificate(CertificateBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime

# Helper schemas
class CertificatePreviewRequest(BaseModel):
    html_content: str
    data: Optional[Dict[str, Any]] = None

class CertificatePreviewResponse(BaseModel):
    rendered_html: str
