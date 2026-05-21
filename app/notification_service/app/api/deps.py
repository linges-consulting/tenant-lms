import httpx
from typing import Annotated, Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

from app.core.config import settings
from app.db.session import get_db

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.AUTH_SERVICE_URL}/api/v1/auth/login"
)

SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]

class UserAuth(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    tenant_id: Optional[str] = None
    roles: List[str] = []
    is_active: bool = True
    full_name: Optional[str] = None

class ValidationPayload(BaseModel):
    user_id: str
    email: str
    tenant_id: Optional[str] = None
    roles: Optional[List[str]] = None
    is_active: bool
    full_name: Optional[str] = None

async def validate_token_with_auth_service(token: str) -> ValidationPayload:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.AUTH_SERVICE_URL}/api/v1/auth/internal/validate-token",
                headers={
                    "X-Internal-Api-Key": settings.INTERNAL_API_KEY,
                    "Authorization": f"Bearer {token}"
                },
                timeout=5.0
            )
            response.raise_for_status()
            return ValidationPayload(**response.json())
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}"
            )

async def get_current_user(token: TokenDep) -> UserAuth:
    payload = await validate_token_with_auth_service(token)
    if not payload.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")
    return UserAuth(
        id=payload.user_id,
        email=payload.email,
        tenant_id=payload.tenant_id,
        roles=payload.roles or [],
        is_active=payload.is_active,
        full_name=payload.full_name
    )

async def get_current_tenant_id(token: TokenDep) -> str:
    payload = await validate_token_with_auth_service(token)
    if not payload.tenant_id:
        # For SysAdmins, we default to the 'system' tenant if no tenant is selected
        if payload.roles and "SysAdmin" in payload.roles:
            return "system"
        raise HTTPException(status_code=403, detail="Not a tenant-scoped token")
    return payload.tenant_id
