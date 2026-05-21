from pydantic import BaseModel
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str
    branding: Optional[dict] = None
    
class SessionToken(BaseModel):
    session_token: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    tenant_id: Optional[str] = None
    roles: Optional[list[str]] = None
    is_global: Optional[bool] = False

class ValidationPayload(BaseModel):
    user_id: str
    email: str
    tenant_id: Optional[str] = None
    roles: Optional[list[str]] = None
    groups: Optional[list[str]] = None
    is_active: bool
    is_global: bool = False
    full_name: Optional[str] = None
