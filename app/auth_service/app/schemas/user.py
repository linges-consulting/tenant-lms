from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime
from app.core.security import validate_password_strength

# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    theme_preference: str = "system"
    role: Optional[str] = None
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    password: str

    @field_validator("password")
    def password_strength(cls, v: str) -> str:
        if not validate_password_strength(v):
            raise ValueError("Password does not meet complexity requirements")
        return v

class UserRegister(BaseModel):
    """Schema for self-registration (public)"""
    email: EmailStr
    username: str  # Required for registration
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    def password_strength(cls, v: str) -> str:
        if not validate_password_strength(v):
            raise ValueError("Password does not meet complexity requirements")
        return v

class UserInvite(BaseModel):
    email: EmailStr
    full_name: str  # Required - cannot be None
    is_business_manager: Optional[bool] = False
    is_training_creator: Optional[bool] = False

class UserCreateRequest(BaseModel):
    """Schema for creating a new user with registration token (SysAdmin)"""
    email: EmailStr
    full_name: str
    tenant_id: Optional[str] = None
    role: Optional[str] = "EMPLOYEE"  # MANAGER, CREATOR, or EMPLOYEE

class RegistrationTokenResponse(BaseModel):
    """Response after creating user or regenerating token"""
    user_id: str
    email: str
    token: Optional[str] = None
    registration_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    message: str = "Registration token generated"

class UserInDBBase(UserBase):
    id: str
    is_sysadmin: bool
    status: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

from .membership import TenantMembership

from pydantic import Field

class User(UserInDBBase):
    members: List[TenantMembership] = Field(default=[], validation_alias="memberships")

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    avatar_url: Optional[str] = None
    theme_preference: Optional[str] = None

class UserPasswordUpdate(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    def password_strength(cls, v: str) -> str:
        if not validate_password_strength(v):
            raise ValueError("Password does not meet complexity requirements")
        return v

class UserResetPassword(BaseModel):
    new_password: str

    @field_validator("new_password")
    def password_strength(cls, v: str) -> str:
        if not validate_password_strength(v):
            raise ValueError("Password does not meet complexity requirements")
        return v

class UserInDB(UserInDBBase):
    hashed_password: str

# --- Authentication/Onboarding Schemas ---
class MagicLinkRedeem(BaseModel):
    token: str
    new_password: str
    username: Optional[str] = None  # Optional in schema to allow 404 for invalid tokens first

    @field_validator("new_password")
    def password_strength(cls, v: str) -> str:
        if not validate_password_strength(v):
            raise ValueError("Password does not meet complexity requirements")
        return v

class MagicLinkResponse(BaseModel):
    invite_url: Optional[str] = None
    message: str

class UserCreateRequest(BaseModel):
    """Request to create a new user with registration token"""
    email: EmailStr
    full_name: str  # Required
    tenant_id: Optional[str] = None  # Optional - for assigning to specific tenant
    role: Optional[str] = None  # MANAGER, CREATOR, or EMPLOYEE

class UserNameUpdateAdmin(BaseModel):
    full_name: str
    reason: str
