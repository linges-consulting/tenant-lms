from datetime import timedelta, datetime, timezone
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api import deps
from app.core import security
from app.core.config import settings
from app.core.limiter import limiter
from app.core.token_blacklist import blacklist_token
from app.models.user import User, UserStatus
from app.models.tenant import Tenant
from app.models.membership import TenantMembership
from app.models.user_token import UserToken
from app.schemas.token import SessionToken, Token, ValidationPayload
from app.schemas.auth import TenantSelection, ValidateInviteRequest, ValidateInviteResponse, RegisterCompleteRequest, RegisterCompleteResponse, LoginRequest
from app.schemas.tenant import Tenant as TenantSchema
from app.schemas.user import UserRegister
from app.core.events import event_publisher
from app.core.cache import get_redis, invalidate_cache
from app.core.login_lockout import check_lockout, record_failed_attempt, clear_lockout


from fastapi.security import APIKeyHeader

router = APIRouter()

internal_api_key_header = APIKeyHeader(name="X-Internal-Api-Key", auto_error=True)

async def verify_internal_api_key(api_key: str = Depends(internal_api_key_header)):
    if api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials"
        )
    return api_key

@router.post("/login", response_model=SessionToken)
@limiter.limit("10/minute")
async def login_access_token(
    request: Request,
    session: deps.SessionDep,
    credentials: LoginRequest,
    redis=Depends(get_redis),
) -> Any:
    """
    Step 1: Authenticate via email/password and return a temporary session_token.
    """
    from sqlalchemy.orm import selectinload

    email = credentials.email.lower().strip()

    # 1. Check account lockout BEFORE any DB work (prevents timing oracle attacks)
    lockout = await check_lockout(email, redis)
    if lockout["force_reset"]:
        raise HTTPException(
            status_code=423,
            detail="Your account has been locked due to too many failed login attempts. Please reset your password to regain access.",
        )
    if lockout["locked"]:
        mins = ((lockout["lockout_seconds_remaining"] or 0) + 59) // 60  # ceiling division
        raise HTTPException(
            status_code=429,
            detail=f"Account temporarily locked due to too many failed attempts. Try again in {mins} minute(s).",
        )

    # 2. Look up user and verify password
    user_obj = await session.execute(
        select(User)
        .where(User.email == email)
        .options(selectinload(User.memberships).selectinload(TenantMembership.tenant))
    )
    user = user_obj.scalar_one_or_none()

    if not user or not security.verify_password(credentials.password, user.hashed_password):
        # Record failed attempt — same message for both cases to prevent email enumeration
        await record_failed_attempt(
            email,
            redis,
            max_attempts=settings.LOGIN_MAX_ATTEMPTS,
            lockout_minutes=settings.LOGIN_LOCKOUT_MINUTES,
            force_reset_threshold=settings.LOGIN_FORCE_RESET_ATTEMPTS,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated. Please contact your administrator.")

    # Check if the user has at least one active membership in an active tenant.
    # SysAdmins are exempt from this check as they have global access.
    # Users with zero memberships are also blocked (not just those whose memberships are all inactive).
    if not user.is_sysadmin:
        active_members = [
            m for m in user.memberships
            if m.is_active and m.tenant.is_active
        ]
        if not active_members:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is not associated with any active organizations. Contact your administrator."
            )

    # 3. Successful authentication — clear any prior lockout state
    await clear_lockout(email, redis)

    access_token_expires = timedelta(minutes=settings.SESSION_TOKEN_EXPIRE_MINUTES)
    session_token = security.create_access_token(
        f"session_{user.id}", expires_delta=access_token_expires
    )

    return {"session_token": session_token}

@router.post("/register", response_model=dict)
@limiter.limit("5/minute")
async def register_user(
    request: Request,
    registration: UserRegister,
    session: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Public registration endpoint - allows users to create an account.
    Username is required and must be unique.
    """
    # Validate username format
    if len(registration.username) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username must be at least 3 characters long"
        )
    
    if not all(c.isalnum() or c in '_-' for c in registration.username):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username can only contain letters, numbers, underscores, and hyphens"
        )
    
    # Check if email already exists
    existing_email = await session.execute(select(User).where(User.email == registration.email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    # Check if username is already taken (case-insensitive)
    existing_username = await session.execute(
        select(User).where(func.lower(User.username) == registration.username.lower())
    )
    if existing_username.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken"
        )
    
    # Create new user with ACTIVE status
    hashed_password = security.get_password_hash(registration.password)
    user = User(
        email=registration.email,
        username=registration.username,
        hashed_password=hashed_password,
        full_name=registration.full_name,
        is_active=True,  # Registered users are immediately active
        status=UserStatus.ACTIVE,  # Mark as active
        is_sysadmin=False
    )
    
    session.add(user)
    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        # Check if it was a uniqueness constraint violation
        if "UNIQUE constraint failed" in str(e) or "duplicate key value violates unique constraint" in str(e).lower():
             raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email or username already registered"
            )
        raise e
        
    await session.refresh(user)
    
    # Trigger Event
    await event_publisher.publish("USER_CREATED", {
        "user_id": str(user.id),
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name
    })

    
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username
    }

@router.get("/check-username")
async def check_username_availability(
    username: str = Query(..., min_length=3, max_length=50),
    session: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Check if a username is available for registration.
    """
    # Validate username format
    if not all(c.isalnum() or c in '_-' for c in username):
        return {"available": False, "reason": "Invalid characters"}
    
    # Check if username exists (case-insensitive)
    existing = await session.execute(
        select(User).where(func.lower(User.username) == username.lower())
    )
    if existing.scalar_one_or_none():
        return {"available": False, "reason": "Username taken"}
    
    return {"available": True}

@router.post("/register/complete", response_model=RegisterCompleteResponse)
@limiter.limit("5/minute")
async def register_complete(
    request: Request,
    registration: RegisterCompleteRequest,
    session: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Unified endpoint    Complete registration using a token.
    Supports tokens generated via user invitations (UserToken).
    """
    from datetime import datetime, timezone
    email = registration.email.lower()
    token = registration.token
    
    # Try UserToken table
    reg_token_res = await session.execute(
        select(UserToken).where(UserToken.token == token).with_for_update()
    )
    token_obj = reg_token_res.scalar_one_or_none()

    if not token_obj:
        raise HTTPException(status_code=404, detail="Registration link not found")

    if token_obj.is_used:
        raise HTTPException(status_code=400, detail="This registration link has already been used")
    expires_at = token_obj.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This registration link has expired")

    # Validate username format
    if len(registration.username) < 3:
        raise HTTPException(status_code=422, detail="Username must be at least 3 characters long")
    if not all(c.isalnum() or c in '_-' for c in registration.username):
        raise HTTPException(status_code=422, detail="Username can only contain letters, numbers, underscores, and hyphens")

    # Check username availability (case-insensitive)
    existing_username = await session.execute(
        select(User).where(func.lower(User.username) == registration.username.lower())
    )
    if existing_username.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username is already taken")

    user_obj = await session.get(User, token_obj.user_id)
    if not user_obj or user_obj.email.lower() != email:
        raise HTTPException(status_code=400, detail="Email does not match registration link")

    # Update user
    user_obj.username = registration.username
    user_obj.hashed_password = security.get_password_hash(registration.password)
    if registration.full_name:
        user_obj.full_name = registration.full_name
    user_obj.status = UserStatus.ACTIVE
    user_obj.is_active = True

    token_obj.is_used = True
    if hasattr(token_obj, 'used_at'):
        token_obj.used_at = datetime.now(timezone.utc)

    # Activate all PENDING memberships for this user
    result = await session.execute(
        select(TenantMembership).where(
            TenantMembership.user_id == user_obj.id,
            TenantMembership.status == UserStatus.PENDING
        )
    )
    pending_memberships = result.scalars().all()
    for membership in pending_memberships:
        membership.status = UserStatus.ACTIVE
        membership.is_active = True

    # SysAdmin logic
    if user_obj.is_sysadmin:
        tenants_result = await session.execute(select(Tenant).where(Tenant.is_active == True))
        for tenant in tenants_result.scalars().all():
            existing_membership = await session.execute(
                select(TenantMembership).where(
                    TenantMembership.user_id == user_obj.id,
                    TenantMembership.tenant_id == tenant.id
                )
            )
            if not existing_membership.scalar_one_or_none():
                session.add(TenantMembership(
                    user_id=user_obj.id,
                    tenant_id=tenant.id,
                    is_business_manager=True,
                    is_training_creator=True,
                    is_employee=False
                ))

    session.add(user_obj)
    session.add(token_obj)
    await session.commit()
    await session.refresh(user_obj)

    await event_publisher.publish("USER_CREATED", {
        "user_id": str(user_obj.id),
        "email": user_obj.email,
        "username": user_obj.username,
        "is_sysadmin": user_obj.is_sysadmin
    })

    # Invalidate cache for all tenants the user just joined (PENDING -> ACTIVE)
    for membership in pending_memberships:
        await invalidate_cache("user_list", membership.tenant_id)

    return RegisterCompleteResponse(
        id=str(user_obj.id),
        email=user_obj.email,
        username=user_obj.username,
        status=user_obj.status.value,
        message="Registration completed successfully"
    )

@router.post("/register/validate-token", response_model=ValidateInviteResponse)
async def validate_registration_token(
    request: ValidateInviteRequest,
    session: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Validate a registration or invite token for a given email.
    Checks the UserToken table for active tokens.
    """
    email = request.email.lower()
    token = request.token
    
    # Try UserToken table
    token_res = await session.execute(
        select(UserToken).where(UserToken.token == token)
    )
    user_token = token_res.scalar_one_or_none()
    
    if not user_token:
        raise HTTPException(status_code=404, detail="Registration link not found")
    
    if user_token.is_used:
        raise HTTPException(status_code=400, detail="This registration link has already been used")

    user_token_expires = user_token.expires_at
    if user_token_expires.tzinfo is None:
        user_token_expires = user_token_expires.replace(tzinfo=timezone.utc)
    if user_token_expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This registration link has expired")
        
    # Verify email
    user = await session.get(User, user_token.user_id)
    if not user or user.email.lower() != email:
        raise HTTPException(status_code=400, detail="Email does not match this registration link")
        
    return ValidateInviteResponse(valid=True, message="Registration link is valid")


@router.get("/tenants", response_model=List[TenantSchema])
async def read_user_tenants(
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Step 2: List all active tenants available to the logged-in user.
    """
    if current_user.is_sysadmin:
        result = await session.execute(
            select(Tenant).where(Tenant.is_active == True)
        )
    else:
        result = await session.execute(
            select(Tenant)
            .join(TenantMembership, TenantMembership.tenant_id == Tenant.id)
            .where(TenantMembership.user_id == current_user.id)
            .where(TenantMembership.is_active == True)
            .where(Tenant.is_active == True)
        )
    tenants = result.scalars().all()
    return tenants

@router.post("/select-tenant", response_model=Token)
async def select_tenant(
    selection: TenantSelection,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Step 3: Select a tenant and receive a tenant-scoped JWT.
    For SysAdmins: tenant_id can be null for global (non-scoped) access mode.
    For other users: tenant_id is required and must match one of their memberships.
    """
    # Handle SysAdmin global mode (tenant_id = null)
    if selection.tenant_id is None:
        if not current_user.is_sysadmin:
            raise HTTPException(status_code=403, detail="Only SysAdmins can use global access mode (tenant_id=null)")
        
        roles = ["SysAdmin"]
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        tenant_claims = {
            "tenant_id": None,  # No tenant scoping
            "roles": roles,
            "is_global": True  # Flag for global access
        }
        
        token = security.create_access_token(
            current_user.id, expires_delta=access_token_expires, additional_claims=tenant_claims
        )
        
        return {"access_token": token, "token_type": "bearer"}
    
    # Handle tenant-scoped mode (tenant_id provided)
    # Verify membership and tenant active status
    is_member = True
    result = await session.execute(
        select(TenantMembership)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(TenantMembership.user_id == current_user.id)
        .where(TenantMembership.tenant_id == selection.tenant_id)
        .where(TenantMembership.is_active == True)
        .where(Tenant.is_active == True)
    )
    membership = result.scalar_one_or_none()
    
    if not membership:
        if current_user.is_sysadmin:
            # SysAdmins can select any active tenant
            tenant_res = await session.execute(select(Tenant).where(Tenant.id == selection.tenant_id, Tenant.is_active == True))
            if not tenant_res.scalar_one_or_none():
                 raise HTTPException(status_code=403, detail="Tenant does not exist or is deactivated")
            is_member = False
        else:
            raise HTTPException(status_code=403, detail="Not a member of this tenant or tenant is deactivated")
        
    roles = []
    if is_member and membership:
        if membership.is_business_manager: roles.append("Business Manager")
        if membership.is_training_creator: roles.append("Training Creator")
        if membership.is_employee: roles.append("Employee")
    
    if current_user.is_sysadmin:
        roles.append("SysAdmin")
        if "Admin" not in roles:
            roles.append("Admin")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    tenant_claims = {
        "tenant_id": selection.tenant_id,
        "roles": roles
    }

    access_token = security.create_access_token(
        current_user.id, expires_delta=access_token_expires, additional_claims=tenant_claims
    )

    # Fetch tenant for branding (re-use membership.tenant if available, else query)
    if is_member and membership:
        tenant = membership.tenant
    else:
        tenant_res = await session.execute(
            select(Tenant).where(Tenant.id == selection.tenant_id)
        )
        tenant = tenant_res.scalar_one_or_none()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "branding": {
            "tenant_id": str(tenant.id),
            "tenant_name": tenant.name,
            "primary_color": tenant.primary_color,
            "secondary_color": tenant.secondary_color,
            "logo_url": getattr(tenant, "logo_url", None),
        } if tenant else None,
    }

@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: User = Depends(deps.get_current_user_for_refresh),
    token: str = Depends(deps.reusable_oauth2)
) -> Any:
    """
    Refresh a near-expiry or expired JWT token.
    This endpoint allows expired tokens to be refreshed.
    """
    # Decode the current token to extract tenant_id and roles using grace period logic
    # This matches the dependency logic and prevents refresh of long-expired tokens.
    payload = security.decode_token_with_grace(token, grace_period_minutes=30)
    tenant_id = payload.get("tenant_id")
    roles = payload.get("roles")
    is_global = payload.get("is_global", False)  # For SysAdmin global mode
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    tenant_claims = {}
    if tenant_id:
        tenant_claims["tenant_id"] = tenant_id
    if roles:
        tenant_claims["roles"] = roles
    if is_global:
        tenant_claims["is_global"] = True
        
    new_token = security.create_access_token(
        current_user.id, expires_delta=access_token_expires, additional_claims=tenant_claims
    )
    
    return {"access_token": new_token, "token_type": "bearer"}

@router.post("/logout", status_code=204)
async def logout(
    current_user: User = Depends(deps.get_current_user),
    token: str = Depends(deps.reusable_oauth2),
    redis=Depends(get_redis),
) -> Response:
    """Blacklist the current token so it cannot be reused after logout."""
    payload = security.decode_token(token)
    jti = payload.get("jti")
    if jti:
        exp = payload.get("exp", 0)
        remaining = max(0, exp - int(datetime.now(timezone.utc).timestamp()))
        await blacklist_token(jti, remaining, redis)
    return Response(status_code=204)


@router.post("/internal/validate-token", response_model=ValidationPayload)
async def validate_internal_token(
    api_key: str = Depends(verify_internal_api_key),
    current_user: User = Depends(deps.get_current_user),
    token: str = Depends(deps.reusable_oauth2),
    session: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Internal endpoint intended for other microservices to validate a JWT and 
    get the associated User details securely. Requires X-Internal-Api-Key.
    """
    try:
        payload = security.decode_token(token, secret=settings.EXTERNAL_JWT_SECRET)
    except Exception:
        payload = security.decode_token(token, secret=settings.INTERNAL_JWT_SECRET)
    
    tenant_id = payload.get("tenant_id")
    
    # Fetch groups if scoped to a tenant
    groups = []
    if tenant_id and tenant_id != "system":
        from app.models.group import Group, GroupMembership
        from sqlalchemy import select
        result = await session.execute(
            select(Group.id)
            .join(GroupMembership, GroupMembership.group_id == Group.id)
            .where(GroupMembership.user_id == current_user.id)
            .where(Group.tenant_id == tenant_id)
        )
        groups = [str(gid) for gid in result.scalars().all()]
        
        # Diagnostic logging
        import logging
        auth_logger = logging.getLogger("request_response")
        auth_logger.info(f"DEBUG_AUTH: Resolved {len(groups)} groups for user {current_user.id} in tenant {tenant_id}: {groups}")
    
    roles = payload.get("roles") or []
    is_global = payload.get("is_global", False)
    if current_user.is_sysadmin:
        is_global = True  # Always global for sysadmin at the internal validation level
        if "SysAdmin" not in roles:
            roles.append("SysAdmin")
    
    return ValidationPayload(
        user_id=str(current_user.id),
        email=current_user.email,
        tenant_id=tenant_id,
        roles=roles,
        groups=groups if tenant_id else None,
        is_active=current_user.is_active,
        is_global=is_global,
        full_name=current_user.full_name
    )
