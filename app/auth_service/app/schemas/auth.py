from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from app.core.security import validate_password_strength

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TenantSelection(BaseModel):
    tenant_id: Optional[str] = None  # None for SysAdmin global mode

class ValidateInviteRequest(BaseModel):
    email: str
    token: str

class ValidateInviteResponse(BaseModel):
    valid: bool
    message: str

class RegisterCompleteRequest(BaseModel):
    """Unified request to complete registration with any token (SysAdmin or Employee)"""
    email: EmailStr
    token: str
    username: str
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    def password_strength(cls, v: str) -> str:
        if not validate_password_strength(v):
            raise ValueError("Password does not meet complexity requirements")
        return v

class RegisterCompleteResponse(BaseModel):
    """Unified response after successful registration completion"""
    id: str
    email: str
    username: str
    status: str
    message: str

