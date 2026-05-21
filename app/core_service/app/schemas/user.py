from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from typing import Optional, List
from app.core.security import validate_password_strength

# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = True

class UserCreate(BaseModel):
    email: str
    password: str

    @field_validator("password")
    def password_strength(cls, v: str) -> str:
        if not validate_password_strength(v):
            raise ValueError("Password does not meet complexity requirements")
        return v

class UserInvite(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

from datetime import datetime

class UserInDBBase(UserBase):
    id: str
    is_sysadmin: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

from .membership import TenantMembership

from pydantic import Field

class User(UserInDBBase):
    members: List[TenantMembership] = Field(default=[], validation_alias="memberships")

class UserUpdate(UserBase):
    password: Optional[str] = None
    is_active: Optional[bool] = None

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

    @field_validator("new_password")
    def password_strength(cls, v: str) -> str:
        if not validate_password_strength(v):
            raise ValueError("Password does not meet complexity requirements")
        return v

class MagicLinkResponse(BaseModel):
    invite_url: str
    message: str
