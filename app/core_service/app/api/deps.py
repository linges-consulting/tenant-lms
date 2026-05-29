import httpx
from typing import Annotated, Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.config import settings
from app.db.session import get_db
from pydantic import BaseModel, ConfigDict

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"/api/v1/auth/login"
)

SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]

class UserAuth(BaseModel):
    """Minimal User schema for internal service use, populated from Auth Service payload."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    email: str
    tenant_id: Optional[str] = None
    roles: List[str] = []
    groups: List[str] = []
    is_active: bool = True
    is_global: bool = False
    full_name: Optional[str] = None

class ValidationPayload(BaseModel):
    user_id: str
    email: str
    tenant_id: Optional[str] = None
    roles: Optional[List[str]] = None
    groups: Optional[List[str]] = None
    is_active: bool
    is_global: bool = False
    full_name: Optional[str] = None

async def validate_token_with_auth_service(token: str) -> ValidationPayload:
    """
    Calls the Auth Service to securely validate the JWT and retrieve user claims.
    """
    async with httpx.AsyncClient() as client:
        try:
            # Note: Using the specific internal validation endpoint
            response = await client.post(
                f"{settings.AUTH_SERVICE_URL}/api/v1/auth/internal/validate-token",
                headers={
                    "X-Internal-Api-Key": settings.INTERNAL_API_KEY,
                    "Authorization": f"Bearer {token}"
                },
                timeout=5.0
            )
            response.raise_for_status()
            data = response.json()
            return ValidationPayload(**data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                # Log the specific error from the auth service for internal debugging
                print(f"DEBUG: Auth Service validation failed with {e.response.status_code}: {e.response.text}")
                # Propagate 401 so the frontend refresh mechanism can retry;
                # propagate 403 for real permission denials (inactive user/tenant).
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail="Could not validate credentials",
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Auth service error: {e}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth service is unavailable",
            )

async def get_tenant_branding(tenant_id: str) -> dict:
    """
    Calls Auth Service internal endpoint to get tenant branding (name, colors).
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/tenants/internal/branding/{tenant_id}",
                headers={
                    "X-Internal-Api-Key": settings.INTERNAL_API_KEY,
                },
                timeout=5.0
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            # Fallback branding
            return {
                "name": "The Training Platform",
                "primary_color": "#2c3e50",
                "secondary_color": "#ffffff"
            }

async def get_users_batch(user_ids: List[str]) -> dict:
    """
    Calls Auth Service internal endpoint to get basic details (full_name, email, username)
    for a list of user IDs. Returns a dict of {user_id: {"full_name": ..., "email": ..., "username": ...}}.
    """
    if not user_ids:
        return {}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.AUTH_SERVICE_URL}/api/v1/users/internal/batch",
                headers={
                    "X-Internal-Api-Key": settings.INTERNAL_API_KEY,
                },
                json=user_ids,
                timeout=5.0
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            # On failure, return empty dict or fallback gracefully
            return {}

async def get_groups_batch(group_ids: List[str]) -> dict:
    """
    Calls Auth Service internal endpoint to get basic details (name)
    for a list of group IDs. Returns a dict of {group_id: {"name": ...}}.
    """
    if not group_ids:
        return {}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.AUTH_SERVICE_URL}/api/v1/groups/internal/batch",
                headers={
                    "X-Internal-Api-Key": settings.INTERNAL_API_KEY,
                },
                json=group_ids,
                timeout=5.0
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            # On failure, return empty dict or fallback gracefully
            return {}

async def get_current_user(token: TokenDep) -> UserAuth:
    """
    Validates token via Auth Service and returns a transient UserAuth object.
    No local DB lookup for users.
    """
    payload: ValidationPayload = await validate_token_with_auth_service(token)
    
    if not payload.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")

    return UserAuth(
        id=payload.user_id,
        email=payload.email,
        tenant_id=payload.tenant_id,
        roles=payload.roles or [],
        groups=payload.groups or [],
        is_active=payload.is_active,
        is_global=payload.is_global,
        full_name=payload.full_name
    )

async def get_current_tenant_user(user: UserAuth = Depends(get_current_user)) -> UserAuth:
    return user

async def get_optional_tenant_id(token: TokenDep) -> Optional[str]:
    """Extracts tenant_id from JWT payload if present. Returns None if not a tenant-scoped token."""
    try:
        payload: ValidationPayload = await validate_token_with_auth_service(token)
        return payload.tenant_id
    except Exception:
        return None

async def get_current_tenant_id(token: TokenDep) -> str:
    """Extracts tenant_id from JWT payload retrieved from Auth Service."""
    payload: ValidationPayload = await validate_token_with_auth_service(token)
    
    if not payload.tenant_id:
        # For SysAdmins in global access mode, we default to the 'system' tenant
        if payload.is_global or (payload.roles and "SysAdmin" in payload.roles):
            return "system"
            
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a tenant-scoped token. Please select a tenant first."
        )
    return payload.tenant_id

async def get_business_manager(
    user: UserAuth = Depends(get_current_tenant_user),
    tenant_id: str = Depends(get_current_tenant_id)
) -> UserAuth:
    """Verifies that the current user has manager roles in the active tenant."""
    # In microservices, we trust the Auth Service's 'roles' claim for the tenant.
    is_manager = any(role in ["Business Manager", "Admin", "SysAdmin"] for role in user.roles)
    
    if not is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Business Manager permissions required for this tenant."
        )
        
    return user


async def get_training_creator(
    user: UserAuth = Depends(get_current_tenant_user),
    tenant_id: str = Depends(get_current_tenant_id)
) -> UserAuth:
    """Verifies that the current user has the Training Creator or Manager role in the active tenant."""
    is_authorized = any(role in ["Business Manager", "Training Creator", "Admin", "SysAdmin"] for role in user.roles)

    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Training Creator or Business Manager permissions required for this tenant."
        )

    return user

from fastapi import Request

async def validate_internal_api(request: Request):
    """
    Simple header-based validation for service-to-service communication.
    """
    api_key = request.headers.get("X-Internal-Api-Key")
    if api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal API key"
        )
