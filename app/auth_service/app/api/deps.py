from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.config import settings
from app.core import security
from app.core.cache import get_redis
from app.core.token_blacklist import is_token_blacklisted
from app.db.session import get_db
from app.models.user import User
from app.models.membership import TenantMembership
from app.schemas.token import TokenPayload

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]

async def get_current_user(session: SessionDep, token: TokenDep, redis: Redis = Depends(get_redis)) -> User:
    try:
        # First try external secret
        try:
            payload = jwt.decode(
                token, settings.EXTERNAL_JWT_SECRET, algorithms=[settings.ALGORITHM]
            )
        except JWTError:
            # Fallback to internal secret if external fails (for service-to-service user context)
            payload = jwt.decode(
                token, settings.INTERNAL_JWT_SECRET, algorithms=[settings.ALGORITHM]
            )
        token_data = TokenPayload(**payload)
    except JWTError:
        # 401 so the client can attempt a token refresh
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    # Check if token has been revoked (e.g. via logout)
    jti = payload.get("jti")
    if jti and await is_token_blacklisted(jti, redis):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    # Check if this is a temp session token instead of a full JWT
    # Allow global tokens for sysadmin actions
    if not token_data.tenant_id and "session_" not in token_data.sub and not token_data.is_global:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token type",
        )

    user_id = str(token_data.sub).replace("session_", "")
    from sqlalchemy.orm import selectinload
    user = await session.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    user = user.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact your administrator.",
        )
        
    # Check if this token is tenant-scoped and if that tenant is active
    if token_data.tenant_id:
        membership = next((m for m in user.memberships if m.tenant_id == token_data.tenant_id), None)
        if not membership and not user.is_sysadmin:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a member of the selected tenant",
            )
        if membership:
            if not membership.tenant.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This tenant has been deactivated. Please contact your administrator.",
                )
            if not membership.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your membership in this tenant has been deactivated. Please contact your administrator.",
                )

    # Transiently set the role based on the JWT claims for downstream permission checks
    if token_data.roles:
        # Priority: Business Manager > Training Creator > Employee
        if "Business Manager" in token_data.roles:
            user.role = "Business Manager"
        elif "Training Creator" in token_data.roles:
            user.role = "Training Creator"
        elif "Employee" in token_data.roles:
            user.role = "Employee"
            
    return user

async def get_current_user_for_refresh(session: SessionDep, token: TokenDep) -> User:
    """Get current user allowing expired tokens. Used only for token refresh."""
    from app.core.security import decode_token_with_grace
    try:
        # We allow a 30-minute grace period for refreshing tokens.
        # This prevents indefinite renewal of leaked tokens.
        try:
            payload = decode_token_with_grace(token, grace_period_minutes=30, secret=settings.EXTERNAL_JWT_SECRET)
        except JWTError:
            payload = decode_token_with_grace(token, grace_period_minutes=30, secret=settings.INTERNAL_JWT_SECRET)
        token_data = TokenPayload(**payload)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    
    # Check if this is a temp session token instead of a full JWT
    if not token_data.tenant_id and "session_" not in token_data.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token type",
        )

    user_id = str(token_data.sub).replace("session_", "")
    from sqlalchemy.orm import selectinload
    user = await session.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    user = user.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact your administrator.",
        )
        
    # Check if this token is tenant-scoped and if that tenant is active
    if token_data.tenant_id:
        membership = next((m for m in user.memberships if m.tenant_id == token_data.tenant_id), None)
        if not membership:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a member of the selected tenant",
            )
        if not membership.tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This tenant has been deactivated. Please contact your administrator.",
            )
        if not membership.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your membership in this tenant has been deactivated. Please contact your administrator.",
            )

    # Transiently set the role based on the JWT claims for downstream permission checks
    if token_data.roles:
        # Priority: Business Manager > Training Creator > Employee
        if "Business Manager" in token_data.roles:
            user.role = "Business Manager"
        elif "Training Creator" in token_data.roles:
            user.role = "Training Creator"
        elif "Employee" in token_data.roles:
            user.role = "Employee"
            
    return user

async def get_current_tenant_user(user: User = Depends(get_current_user)) -> User:
    """Verifies that the user has a valid fully scoped tenant JWT."""
    # The actual scoping logic happens by checking the JWT payload in get_current_tenant_id
    # We just ensure the user exists. 
    return user

async def get_current_tenant_id(token: TokenDep) -> str:
    """Extracts tenant_id from a fully scoped JWT."""
    try:
        try:
            payload = jwt.decode(
                token, settings.EXTERNAL_JWT_SECRET, algorithms=[settings.ALGORITHM]
            )
        except JWTError:
            payload = jwt.decode(
                token, settings.INTERNAL_JWT_SECRET, algorithms=[settings.ALGORITHM]
            )
        token_data = TokenPayload(**payload)
        
        if not token_data.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a tenant-scoped token. Please select a tenant first."
            )
        return token_data.tenant_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

async def get_optional_tenant_id(token: TokenDep) -> Optional[str]:
    """Extracts tenant_id from a JWT if present. Returns None if not a tenant-scoped token."""
    try:
        try:
            payload = jwt.decode(
                token, settings.EXTERNAL_JWT_SECRET, algorithms=[settings.ALGORITHM]
            )
        except JWTError:
            payload = jwt.decode(
                token, settings.INTERNAL_JWT_SECRET, algorithms=[settings.ALGORITHM]
            )
        token_data = TokenPayload(**payload)
        return token_data.tenant_id
    except JWTError:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

async def get_business_manager(
    user: User = Depends(get_current_tenant_user),
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db)
) -> User:
    """Verifies that the current user is a business manager in the active tenant."""
    membership = await session.execute(
        select(TenantMembership).where(
            and_(
                TenantMembership.user_id == user.id,
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.is_business_manager == True
            )
        )
    )
    membership = membership.scalar_one_or_none()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Business Manager permissions required for this tenant."
        )
        
    return user

async def get_manager_or_creator(
    user: User = Depends(get_current_tenant_user),
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db)
) -> User:
    """Verifies the user is a business manager OR training creator in the active tenant.
    Used for read-only endpoints that both roles need (e.g. listing users/groups for assignment).
    """
    from sqlalchemy import or_
    membership = await session.execute(
        select(TenantMembership).where(
            and_(
                TenantMembership.user_id == user.id,
                TenantMembership.tenant_id == tenant_id,
                or_(
                    TenantMembership.is_business_manager == True,
                    TenantMembership.is_training_creator == True,
                )
            )
        )
    )
    membership = membership.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Business Manager or Training Creator permissions required for this tenant."
        )

    return user

async def get_sysadmin(
    user: User = Depends(get_current_user),
) -> User:
    """Verifies that the current user is a system administrator."""
    if not user.is_sysadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System Administrator permissions required."
        )
    return user

async def validate_internal_api(
    x_internal_api_key: Optional[str] = Header(None, alias="X-Internal-Api-Key"),
) -> None:
    """
    Dependency to validate internal service-to-service calls.
    """
    if not x_internal_api_key or x_internal_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal API key",
        )
