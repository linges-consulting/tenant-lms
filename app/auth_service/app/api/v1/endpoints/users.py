import csv
import io
import re
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, UploadFile, File
from fastapi import Query as QueryParam
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from nanoid import generate

from app.api import deps
from app.core import security
from app.core.config import settings
from app.core.cache import cache_response, invalidate_cache
from app.models.user import User, UserStatus
from app.models.membership import TenantMembership
from app.models.user_token import UserToken
from app.schemas.user import User as UserSchema
from app.schemas.user import UserInvite, MagicLinkResponse, UserPasswordUpdate, UserUpdate, UserCreateRequest, RegistrationTokenResponse
from app.core.events import event_publisher


logger = logging.getLogger(__name__)
router = APIRouter()


async def _write_audit_log(db, actor_id: str, actor_email: str, target_user_id: str, event_type: str, details: dict):
    from app.models.audit_log import AuditLog
    entry = AuditLog(
        actor_id=actor_id,
        actor_email=actor_email,
        target_user_id=target_user_id,
        event_type=event_type,
        details=details,
    )
    db.add(entry)
    # caller is responsible for commit


def get_random_avatar() -> str:
    import random
    return f"avatar{random.randint(1, 10)}"

# Request schemas
class UserNameUpdate(BaseModel):
    full_name: str

class UserNameUpdateAdmin(BaseModel):
    full_name: str
    reason: str

def map_user_status(user: User, membership: Optional[TenantMembership] = None) -> tuple[str, bool]:
    """
    Unifies the status mapping logic.
    Returns (status_string, is_active_bool)
    
    Logic:
    1. If the global User.status is PENDING, the user is always PENDING (needs registration).
    2. If global status is ACTIVE:
       - If membership exists and is specifically INACTIVE, status is INACTIVE.
       - Otherwise, status is ACTIVE.
    3. If global status is INACTIVE, status is INACTIVE.
    """
    # Global PENDING always takes precedence (needs to set password)
    if user.status == UserStatus.PENDING or user.status == UserStatus.PENDING.value:
        return UserStatus.PENDING.value, False
    
    # If a membership is provided, check its specific state
    if membership:
        if membership.status == UserStatus.INACTIVE or membership.status == UserStatus.INACTIVE.value:
            return UserStatus.INACTIVE.value, False
        if not membership.is_active:
            return UserStatus.INACTIVE.value, False

    # Fallback to global state
    if user.status == UserStatus.INACTIVE or user.status == UserStatus.INACTIVE.value:
        return UserStatus.INACTIVE.value, False
        
    return UserStatus.ACTIVE.value, True


_EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")


async def _process_single_invite(
    db: AsyncSession,
    email: str,
    first_name: str,
    last_name: str,
    tenant_id: str,
    is_bm: bool,
    is_tc: bool,
) -> str:
    """
    Core invite logic shared by invite_user and bulk_import_users.

    Creates or fetches the User record, upserts a TenantMembership, and (for
    net-new / still-pending users) generates a UserToken and fires the
    USER_INVITED event.

    Returns a short status string describing what happened.
    """
    from app.models.tenant import Tenant

    full_name = f"{first_name} {last_name}".strip()

    # 1. Get or create user stub
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    is_net_new = not user or user.status == UserStatus.PENDING or user.status == UserStatus.PENDING.value
    if not user:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=None,
            is_active=False,
            status=UserStatus.PENDING,
            avatar_url=get_random_avatar(),
        )
        db.add(user)
        await db.flush()

    # 2. Upsert membership
    mem_result = await db.execute(
        select(TenantMembership).where(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == tenant_id,
        )
    )
    membership = mem_result.scalar_one_or_none()

    if not membership:
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=tenant_id,
            is_employee=True,
            is_business_manager=is_bm,
            is_training_creator=is_tc,
            status=UserStatus.PENDING if is_net_new else UserStatus.ACTIVE,
        )
        db.add(membership)
    else:
        membership.is_business_manager = is_bm
        membership.is_training_creator = is_tc
        if not is_net_new:
            membership.is_active = True
            membership.status = UserStatus.ACTIVE

    # 3. Already-active users — no token needed
    if not is_net_new and user.status == UserStatus.ACTIVE:
        await db.flush()
        return "already_active"

    # 4. Generate registration token
    token_str = generate(size=16)
    expires = datetime.now(timezone.utc) + timedelta(hours=48)
    invite_url = f"{settings.FRONTEND_URL}/register?token={token_str}"

    user_token = UserToken(
        user_id=user.id,
        tenant_id=tenant_id,
        token=token_str,
        expires_at=expires,
        is_used=False,
    )
    db.add(user_token)
    await db.flush()

    # 5. Load tenant branding for email event
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()

    await event_publisher.publish("USER_INVITED", {
        "user_id": str(user.id),
        "email": email,
        "full_name": user.full_name or email,
        "invite_url": invite_url,
        "token": token_str,
        "tenant_id": tenant_id,
        "primary_color": tenant.primary_color if tenant else None,
        "secondary_color": tenant.secondary_color if tenant else None,
        "logo_url": tenant.logo_url if tenant else None,
        "tenant_name": tenant.name if tenant else "Our Platform",
    })

    return "invited"


@router.post("/bulk-import")
async def bulk_import_users(
    tenant_id: str = QueryParam(...),
    file: UploadFile = File(...),
    current_sysadmin: User = Depends(deps.get_sysadmin),
    db: AsyncSession = Depends(deps.get_db),
):
    """SysAdmin-only: import users from a CSV file into a tenant."""
    from app.models.tenant import Tenant

    tenant = await db.get(Tenant, tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="Tenant not found")

    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))

    successes: list[dict] = []
    failures: list[dict] = []
    required_fields = {"email", "first_name", "last_name"}

    for i, row in enumerate(reader, start=2):
        missing = required_fields - set(row.keys())
        if missing:
            failures.append({
                "row": i,
                "email": row.get("email", ""),
                "reason": f"Missing columns: {missing}",
            })
            continue

        email = row["email"].strip().lower()
        first_name = row["first_name"].strip()
        last_name = row["last_name"].strip()
        is_bm = row.get("is_business_manager", "false").lower() == "true"
        is_tc = row.get("is_training_creator", "false").lower() == "true"

        if not _EMAIL_RE.match(email):
            failures.append({"row": i, "email": email, "reason": "Invalid email format"})
            continue

        if not first_name or not last_name:
            failures.append({
                "row": i,
                "email": email,
                "reason": "first_name and last_name are required",
            })
            continue

        try:
            result = await _process_single_invite(
                db, email, first_name, last_name, tenant_id, is_bm, is_tc
            )
            successes.append({"row": i, "email": email, "result": result})
        except Exception as e:
            failures.append({"row": i, "email": email, "reason": str(e)})

    # Commit all successful rows in one shot
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during commit: {e}")

    # Invalidate user-list cache for this tenant
    await invalidate_cache("user_list", tenant_id)

    return {
        "successes": successes,
        "failures": failures,
        "total_rows": len(successes) + len(failures),
    }


@router.post("/invite", response_model=MagicLinkResponse)
async def invite_user(
    invite_data: UserInvite,
    db: AsyncSession = Depends(deps.get_db),
    current_manager: User = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Invite a user to the active tenant.
    Returns a Magic Link token.
    """
    email = invite_data.email.lower()
    
    # 1. Check if user exists
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    # BR-107 / Rule #12: SysAdmins are global-only — cannot hold tenant memberships.
    if user and user.is_sysadmin:
        raise HTTPException(
            status_code=400,
            detail="SysAdmin users cannot be added to a tenant."
        )

    is_net_new = not user or user.status == UserStatus.PENDING or user.status == UserStatus.PENDING.value
    if not user:
        # Create user stub with PENDING status
        user = User(
            email=email, 
            full_name=invite_data.full_name,
            hashed_password=None, 
            is_active=False,
            status=UserStatus.PENDING,
            avatar_url=get_random_avatar()
        )
        db.add(user)
        await db.flush()
    
    # 2. Upsert membership
    mem_result = await db.execute(
        select(TenantMembership).where(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == tenant_id
        )
    )
    membership = mem_result.scalar_one_or_none()
    
    if not membership:
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=tenant_id,
            is_employee=True,
            is_business_manager=invite_data.is_business_manager or False,
            is_training_creator=invite_data.is_training_creator or False,
            status=UserStatus.PENDING if is_net_new else UserStatus.ACTIVE
        )
        db.add(membership)
    else:
        # Update roles if already member
        membership.is_business_manager = invite_data.is_business_manager or False
        membership.is_training_creator = invite_data.is_training_creator or False
        if not is_net_new:
            membership.is_active = True
            membership.status = UserStatus.ACTIVE
    
    # 4. Handle token and activation
    # Rule: If not net new (already in system and registered), skip register flow
    if not is_net_new and user.status == UserStatus.ACTIVE:
        await db.commit()
        return MagicLinkResponse(
            invite_url="",
            message="User already exists and is active. They can login directly."
        )
    
    # Otherwise (net new or still pending), generate token
    token_str = generate(size=16)
    expires = datetime.now(timezone.utc) + timedelta(hours=48)
    invite_url = f"{settings.FRONTEND_URL}/register?token={token_str}"
    
    user_token = UserToken(
        user_id=user.id,
        tenant_id=tenant_id,
        token=token_str,
        expires_at=expires,
        is_used=False
    )
    db.add(user_token)
    await db.commit()
    
    # Load tenant branding for email
    from app.models.tenant import Tenant
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    
    # Trigger Event
    await event_publisher.publish("USER_INVITED", {
        "user_id": str(user.id),
        "email": email,
        "full_name": user.full_name or email,
        "invite_url": invite_url,
        "token": token_str,
        "tenant_id": tenant_id,
        "primary_color": tenant.primary_color if tenant else None,
        "secondary_color": tenant.secondary_color if tenant else None,
        "logo_url": tenant.logo_url if tenant else None,
        "tenant_name": tenant.name if tenant else "Our Platform"
    })
    
    # Invalidate cache
    await invalidate_cache("user_list", tenant_id)
    
    return {"invite_url": invite_url, "message": "Invitation sent"}

@router.get("/me", response_model=UserSchema)
# @cache_response("user_me", expire=300, include_user_id=True)
async def read_user_me(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    tenant_id: Optional[str] = Depends(deps.get_optional_tenant_id),
) -> Any:
    """
    Get current user.
    """
    # Eagerly load memberships before returning
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User).where(User.id == current_user.id).options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    return result.scalar_one()

@router.patch("/me", response_model=UserSchema)
async def update_user_me(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_user),
    tenant_id: Optional[str] = Depends(deps.get_optional_tenant_id),
) -> Any:
    """
    Update own user profile.
    Note: full_name and email updates are restricted. Contact an administrator to change your name or email.
    """
    # Prevent email updates
    if user_in.email is not None:
        raise HTTPException(
            status_code=403,
            detail="Email cannot be updated by users. Contact an administrator to change your email."
        )

    # Prevent full_name updates (Rule #11)
    if user_in.full_name is not None:
        raise HTTPException(
            status_code=403,
            detail="You cannot change your own name. Contact a SysAdmin."
        )

    if user_in.username is not None:
        # Validate username format (same rules as registration)
        import re as _re
        if not _re.fullmatch(r'[a-zA-Z0-9_-]{3,50}', user_in.username):
            raise HTTPException(
                status_code=422,
                detail="Username may only contain letters, numbers, underscores, and hyphens (3–50 characters)"
            )
        # Check uniqueness if not empty
        if user_in.username:
            existing_user = await db.execute(
                select(User).where(User.username == user_in.username, User.id != current_user.id)
            )
            if existing_user.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Username already exists")
        current_user.username = user_in.username
    
    # Allow avatar_url updates
    if user_in.avatar_url is not None:
        current_user.avatar_url = user_in.avatar_url
    
    # Allow theme_preference updates
    if user_in.theme_preference is not None:
        current_user.theme_preference = user_in.theme_preference

    if user_in.password is not None:
        current_user.hashed_password = security.get_password_hash(user_in.password)
        
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    # Invalidate cache
    await invalidate_cache("user_me", tenant_id, user_id=current_user.id)
    await invalidate_cache("public_profile", tenant_id)
    await invalidate_cache("user_list", tenant_id)
    
    # Eagerly load memberships before returning
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User).where(User.id == current_user.id).options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    return result.scalar_one()

@router.get("", response_model=List[UserSchema])
# @cache_response("user_list", expire=300)
async def list_tenant_users(
    db: AsyncSession = Depends(deps.get_db),
    current_manager: User = Depends(deps.get_manager_or_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """List all employees in the active tenant."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User)
        .join(TenantMembership, User.id == TenantMembership.user_id)
        .where(
            TenantMembership.tenant_id == tenant_id,
            User.id != current_manager.id,  # BR-501: exclude the requesting manager
        )
        .options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    users = result.scalars().all()
    
    serialized_users = []
    for user in users:
        schema = UserSchema.model_validate(user)
        # Find the specific membership for the active tenant
        membership = next((m for m in user.memberships if m.tenant_id == tenant_id), None)
        
        status_str, is_active = map_user_status(user, membership)
        schema.status = status_str
        schema.is_active = is_active
        serialized_users.append(schema)

        
    return serialized_users


@router.get("/admin/list", response_model=List[UserSchema])
async def list_global_users(
    db: AsyncSession = Depends(deps.get_db),
    current_sysadmin: User = Depends(deps.get_sysadmin),
):
    """List all users in the system (SysAdmin only)."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User).options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    users = result.scalars().all()
    
    serialized_users = []
    for user in users:
        schema = UserSchema.model_validate(user)
        status_str, is_active = map_user_status(user)
        schema.status = status_str
        schema.is_active = is_active
        serialized_users.append(schema)
        
    return serialized_users

@router.post("/invite-sysadmin", response_model=RegistrationTokenResponse)
async def invite_sysadmin(
    invite_data: UserInvite,
    db: AsyncSession = Depends(deps.get_db),
    current_sysadmin: User = Depends(deps.get_sysadmin),
):
    """Invite/Create a new SysAdmin with registration token.
    
    Email must be globally unique (cannot be used across multiple tenants).
    Full name is required.
    Generates a registration token for the SysAdmin to complete onboarding.
    """
    try:
        email = invite_data.email.lower()
        
        # Check if email already exists
        existing_user = await db.execute(select(User).where(User.email == email))
        existing_user = existing_user.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="Email already exists. Email must be globally unique."
            )
        
        # Create new SysAdmin user with required fields
        user = User(
            email=email,
            full_name=invite_data.full_name,  # Now required from input
            hashed_password=None,
            is_sysadmin=True,
            is_active=True,
            status=UserStatus.PENDING,
            theme_preference="system",
            avatar_url=get_random_avatar()
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Generate registration token with 48-hour expiration (BR-103)
        token = security.generate_registration_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
        
        user_token = UserToken(
            user_id=str(user.id),
            token=token,
            expires_at=expires_at,
        )
        db.add(user_token)
        await db.commit()
        
        # Generate registration URL
        registration_url = f"{settings.FRONTEND_URL}/register?token={token}"
        
        return RegistrationTokenResponse(
            user_id=str(user.id),
            email=user.email,
            token=token,
            registration_url=registration_url,
            expires_at=expires_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error inviting sysadmin: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create sysadmin: {str(e)}"
        )

@router.post("/create", response_model=RegistrationTokenResponse)
async def create_user(
    user_data: UserCreateRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_sysadmin: User = Depends(deps.get_sysadmin),
):
    """
    Create a new user and generate a registration token.
    
    - Email must be globally unique
    - Full name is required
    - Optional: tenant_id and role (for assigning to a specific tenant)
    - For non-SysAdmin users, creates TenantMembership with specified role
    - Returns registration token and URL
    """
    try:
        email = user_data.email.lower()
        
        # Check if user already exists
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        is_net_new = False
        if not user:
            is_net_new = True
            # Create new user with PENDING status
            user = User(
                email=email,
                full_name=user_data.full_name,
                hashed_password=None,
                is_sysadmin=False,
                is_active=False,
                status=UserStatus.PENDING,
                theme_preference="system",
                avatar_url=get_random_avatar()
            )
            db.add(user)
            await db.flush()
        
        # Requirement: must be created with associated tenant
        if not user_data.tenant_id:
             raise HTTPException(status_code=400, detail="Tenant ID is required for non-SysAdmin users.")

        # Check for duplicate membership in the SAME tenant
        existing_membership = await db.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == user.id,
                TenantMembership.tenant_id == user_data.tenant_id
            )
        )
        if existing_membership.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="User is already a member of this tenant.")

        # Create membership
        mapping = {
            "MANAGER": {"is_business_manager": True, "is_training_creator": False, "is_employee": False},
            "CREATOR": {"is_business_manager": False, "is_training_creator": True, "is_employee": False},
            "EMPLOYEE": {"is_business_manager": False, "is_training_creator": False, "is_employee": True},
        }
        role_mapping = mapping.get(user_data.role or "EMPLOYEE", 
                                   {"is_business_manager": False, "is_training_creator": False, "is_employee": True})
        
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=user_data.tenant_id,
            status=UserStatus.PENDING if is_net_new else UserStatus.ACTIVE,
            **role_mapping
        )
        db.add(membership)

        if not is_net_new and user.status == UserStatus.ACTIVE:
            # Rule: If NOT net new (already in system and active), automatically active in this tenant too
            await db.commit()
            return RegistrationTokenResponse(
                user_id=str(user.id),
                email=user.email,
                message=f"User already exists. They have been added to the tenant and can login directly."
            )
        
        # Net new user or still pending - generate registration token (BR-103: 48h)
        token_str = generate(size=16)
        expires = datetime.now(timezone.utc) + timedelta(hours=48)

        user_token = UserToken(
            user_id=user.id,
            tenant_id=user_data.tenant_id,
            token=token_str,
            expires_at=expires,
            is_used=False
        )
        db.add(user_token)
        await db.commit()
        await db.refresh(user)
        
        # Trigger Event
        await event_publisher.publish("USER_CREATED", {
            "user_id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "tenant_id": user_data.tenant_id,
            "role": user_data.role or "EMPLOYEE"
        })

        
        # Build registration URL
        registration_url = f"{settings.FRONTEND_URL}/register?token={token_str}"
        
        # Fetch tenant name if applicable
        tenant_name = None
        if user_data.tenant_id:
            from app.models.tenant import Tenant
            result = await db.execute(select(Tenant).where(Tenant.id == user_data.tenant_id))
            tenant = result.scalar_one_or_none()
            if tenant:
                tenant_name = tenant.name
        
        # Publish event for email worker
        await event_publisher.publish("USER_INVITED", {
            "user_id": str(user.id),
            "email": user.email,
            "full_name": user.full_name or user.email,
            "registration_url": registration_url,
            "token": token_str,
            "tenant_id": user_data.tenant_id,
            "tenant_name": tenant_name
        })
        
        # Invalidate cache
        await invalidate_cache("user_list", user_data.tenant_id)
        
        return RegistrationTokenResponse(
            user_id=str(user.id),
            email=user.email,
            token=token_str,
            registration_url=registration_url,
            expires_at=expires,
            message=f"User created successfully. Registration invitation email sent."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error creating user: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create user: {str(e)}"
        )

@router.get("/{user_id}/token", response_model=dict)
async def get_user_registration_token(
    user_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
):
    """
    Retrieve the active registration token for a user.
    Only available for users in PENDING status.
    Available to SysAdmins and Managers (if user in their tenant).
    """
    from sqlalchemy.orm import selectinload
    
    # 1. Check Permissions
    is_authorized = current_user.is_sysadmin
    
    if not is_authorized:
        if not tenant_id:
            raise HTTPException(status_code=403, detail="X-Tenant-Id header required for managers.")
        
        # Check if current_user is manager of this tenant
        mgr_mem_res = await db.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == current_user.id,
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.is_business_manager == True
            )
        )
        if not mgr_mem_res.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not a manager of this tenant.")
            
        # Check if target user is in this tenant
        target_mem_res = await db.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == user_id,
                TenantMembership.tenant_id == tenant_id
            )
        )
        if not target_mem_res.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Target user not found in your tenant.")
        
        is_authorized = True
    
    result = await db.execute(
        select(User).where(User.id == user_id).options(
            selectinload(User.user_tokens)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.status != UserStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Registration token only available for PENDING users. This user is {user.status.value}."
        )
    
    # Get the active (unused) registration token
    active_token = None
    for token in user.user_tokens:
        if not token.is_used and token.expires_at > datetime.now(timezone.utc):
            active_token = token
            break
    
    if not active_token:
        raise HTTPException(
            status_code=404,
            detail="No active registration token found. Request a new one."
        )
    
    return {
        "token": active_token.token,
        "expires_at": active_token.expires_at,
        "registration_url": f"{settings.FRONTEND_URL}/register?token={active_token.token}"
    }

@router.post("/{user_id}/regenerate-token", response_model=RegistrationTokenResponse)
async def regenerate_registration_token(
    user_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
):
    """
    Regenerate a registration token for a user.
    Only available for users in PENDING status.
    Invalidates the old token and creates a new one with 7-day expiration.
    Available to SysAdmins and Managers (if user in their tenant).
    """
    from sqlalchemy.orm import selectinload
    
    # 1. Check Permissions
    is_authorized = current_user.is_sysadmin
    
    if not is_authorized:
        # Check if Manager for the current tenant
        if not tenant_id:
            raise HTTPException(status_code=403, detail="X-Tenant-Id header required for managers.")
        
        # Check if current_user is manager of this tenant
        mgr_mem_res = await db.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == current_user.id,
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.is_business_manager == True
            )
        )
        if not mgr_mem_res.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not a manager of this tenant.")
            
        # Check if target user is in this tenant
        target_mem_res = await db.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == user_id,
                TenantMembership.tenant_id == tenant_id
            )
        )
        if not target_mem_res.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Target user not found in your tenant.")
        
        is_authorized = True

    result = await db.execute(
        select(User).where(User.id == user_id).options(
            selectinload(User.user_tokens),
            selectinload(User.memberships)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.status != UserStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Can only regenerate token for PENDING users. This user is {user.status.value}."
        )
    
    try:
        # Mark all existing tokens as used
        for token in user.user_tokens:
            if not token.is_used:
                token.is_used = True
                token.used_at = datetime.now(timezone.utc)
        
        # Generate new token (BR-103: 48h expiry)
        token_str = generate(size=16)
        expires = datetime.now(timezone.utc) + timedelta(hours=48)

        new_token = UserToken(
            user_id=user.id,
            tenant_id=tenant_id,
            token=token_str,
            expires_at=expires,
            is_used=False
        )
        db.add(new_token)
        await db.commit()
        await db.refresh(user)
        
        registration_url = f"{settings.FRONTEND_URL}/register?token={token_str}"
        
        # Fetch tenant name if applicable
        tenant_name = None
        t_obj = None
        if tenant_id:
            from app.models.tenant import Tenant
            t_res = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
            t_obj = t_res.scalar_one_or_none()
            if t_obj:
                tenant_name = t_obj.name

        # Publish event for email worker (uses branded templates)
        await event_publisher.publish("USER_INVITED", {
            "user_id": str(user.id),
            "email": user.email,
            "full_name": user.full_name or user.email,
            "invite_url": registration_url,
            "token": token_str,
            "tenant_id": tenant_id,
            "primary_color": t_obj.primary_color if t_obj else None,
            "secondary_color": t_obj.secondary_color if t_obj else None,
            "logo_url": t_obj.logo_url if t_obj else None,
            "tenant_name": tenant_name if tenant_name else "Our Platform"
        })
        
        return RegistrationTokenResponse(
            user_id=str(user.id),
            email=user.email,
            token=token_str,
            registration_url=registration_url,
            expires_at=expires,
            message="New registration token generated and invitation email sent."
        )
    
    except Exception as e:
        await db.rollback()
        logger.error(f"Error regenerating token: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{user_id}/update-name", response_model=UserSchema)
async def update_user_name_admin(
    user_id: str,
    payload: UserNameUpdateAdmin,
    db: AsyncSession = Depends(deps.get_db),
    current_sysadmin: User = Depends(deps.get_sysadmin),
):
    """
    Update a user's full name (SysAdmin only).
    Requires a reasoning for the change.
    """
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    old_name = user.full_name
    user.full_name = payload.full_name

    # Audit log — belt and suspenders: both logger and persistent DB record
    logger.info(f"AUDIT | SysAdmin {current_sysadmin.email} updated name for user {user.email} from '{old_name}' to '{payload.full_name}'. Reason: {payload.reason}")
    await _write_audit_log(
        db,
        actor_id=current_sysadmin.id,
        actor_email=current_sysadmin.email,
        target_user_id=user.id,
        event_type="NAME_CHANGE",
        details={"old_name": old_name, "new_name": payload.full_name, "reason": payload.reason},
    )

    await db.commit()
    await db.refresh(user)
    
    return user

@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    tenant_id: Optional[str] = Query(None, description="Explicit tenant ID context for deletion"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    scoped_tenant_id: Optional[str] = Depends(deps.get_optional_tenant_id),
):
    """
    Delete a user permanently or remove from a tenant.
    SysAdmin: Permanent deletion of a user globally.
    Manager: Removes membership for PENDING/INACTIVE user from their tenant.
    Prevents deletion of own account as safety measure.
    """
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User).where(User.id == user_id).options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own account"
        )
    
    # resolved_tenant_id for deletions
    resolved_tenant_id = tenant_id or scoped_tenant_id
    
    # If SysAdmin and NO tenant context, delete permanently across the system.
    if current_user.is_sysadmin and not resolved_tenant_id:
        # Get memberships for cache invalidation before deletion
        memberships = user.memberships
        try:
            user_id_str = str(user.id)
            user_email = user.email
            await db.delete(user)
            await db.commit()
            
            # Invalidate cache for all tenants the user was in
            for m in memberships:
                await invalidate_cache("user_list", m.tenant_id)
            
            # Publish event for other services
            from app.core.events import event_publisher
            await event_publisher.publish("USER_DELETED", {
                "user_id": user_id_str,
                "email": user_email,
                "global_delete": True
            })
                
            return {"message": f"User {user_id} deleted successfully from system"}
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")

    # Otherwise, it must be a tenant-level removal.
    if not resolved_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context required to remove user from tenant")

    if not current_user.is_sysadmin:
        caller_memberships = await db.execute(
            select(TenantMembership.tenant_id)
            .where(TenantMembership.user_id == current_user.id, TenantMembership.is_business_manager == True)
        )
        caller_mgr_tenants = set(caller_memberships.scalars().all())
        
        if resolved_tenant_id not in caller_mgr_tenants:
            raise HTTPException(status_code=403, detail="Not authorized to remove users in this tenant")
            
    membership = next((m for m in user.memberships if m.tenant_id == resolved_tenant_id), None)
    if not membership:
        raise HTTPException(status_code=404, detail="User is not a member of this tenant")
        
    mem_status = membership.status.value if hasattr(membership.status, 'value') else membership.status
    if not current_user.is_sysadmin and mem_status not in [UserStatus.PENDING.value, UserStatus.INACTIVE.value, UserStatus.PENDING, UserStatus.INACTIVE]:
        raise HTTPException(
            status_code=400,
            detail=f"Can only remove PENDING or INACTIVE users from tenant. Current status: {mem_status}"
        )
        
    try:
        user_id_str = str(user.id)
        user_email = user.email
        await db.delete(membership)
        await db.commit()
        
        # Invalidate cache
        await invalidate_cache("user_list", resolved_tenant_id)
        
        # Publish event
        from app.core.events import event_publisher
        await event_publisher.publish("USER_DELETED", {
            "user_id": user_id_str,
            "email": user_email,
            "tenant_id": resolved_tenant_id,
            "global_delete": False
        })
        
        return {"message": f"User {user_id} removed from tenant {resolved_tenant_id} successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to remove user from tenant: {str(e)}")

@router.post("/{user_id}/deactivate", response_model=UserSchema)
async def deactivate_user(
    user_id: str,
    tenant_id: Optional[str] = Query(None, description="Explicit tenant ID for SysAdmins"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    scoped_tenant_id: Optional[str] = Depends(deps.get_optional_tenant_id),
):
    """Deactivate a user (SysAdmin or Manager of the user's tenant)."""
    # Eagerly load memberships to avoid lazy loading errors during validation or serialization
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User).where(User.id == user_id).options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if current_user.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    resolved_tenant_id = tenant_id or scoped_tenant_id
    
    # Tenant context checks moved below based on user type
        
    if not current_user.is_sysadmin:
        if not resolved_tenant_id:
            raise HTTPException(status_code=400, detail="Tenant context required to deactivate user.")
            
        caller_memberships = await db.execute(
            select(TenantMembership.tenant_id)
            .where(TenantMembership.user_id == current_user.id, TenantMembership.is_business_manager == True)
        )
        caller_mgr_tenants = set(caller_memberships.scalars().all())
        
        target_tenants = {m.tenant_id for m in user.memberships}
        
        if resolved_tenant_id not in caller_mgr_tenants or resolved_tenant_id not in target_tenants:
            raise HTTPException(status_code=403, detail="Not authorized to deactivate this user in this tenant")

    if user.is_sysadmin:
        user.is_active = False
        user.status = UserStatus.INACTIVE
    else:
        membership = next((m for m in user.memberships if m.tenant_id == resolved_tenant_id), None)
        if not membership:
            raise HTTPException(status_code=404, detail="User is not a member of this tenant")

        membership.is_active = False
        membership.status = UserStatus.INACTIVE
    
    await db.commit()
    
    # Invalidate cache
    await invalidate_cache("user_list", resolved_tenant_id)

    # Publish event
    from app.core.events import event_publisher
    await event_publisher.publish("USER_DEACTIVATED", {
        "user_id": str(user.id),
        "email": user.email,
        "tenant_id": resolved_tenant_id
    })
    
    # Re-fetch the user with memberships eagerly loaded after commit to avoid lazy loading in serialization
    result = await db.execute(
        select(User).where(User.id == user_id).options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    user = result.scalar_one()

    # Return serialized user with status mapped
    schema = UserSchema.model_validate(user)
    if user.is_sysadmin:
        schema.is_active = user.is_active
        schema.status = user.status.value if hasattr(user.status, 'value') else user.status
    else:
        schema.is_active = membership.is_active
        schema.status = membership.status.value if hasattr(membership.status, 'value') else membership.status
    return schema

@router.post("/{user_id}/reactivate", response_model=UserSchema)
async def reactivate_user(
    user_id: str,
    tenant_id: Optional[str] = Query(None, description="Explicit tenant ID for SysAdmins"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    scoped_tenant_id: Optional[str] = Depends(deps.get_optional_tenant_id),
):
    """Reactivate a user (SysAdmin or Manager of the user's tenant)."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User).where(User.id == user_id).options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    resolved_tenant_id = tenant_id or scoped_tenant_id
    
    # Tenant context checks moved below based on user type
        
    if not current_user.is_sysadmin:
        if not resolved_tenant_id:
            raise HTTPException(status_code=400, detail="Tenant context required to reactivate user.")
            
        caller_memberships = await db.execute(
            select(TenantMembership.tenant_id)
            .where(TenantMembership.user_id == current_user.id, TenantMembership.is_business_manager == True)
        )
        caller_mgr_tenants = set(caller_memberships.scalars().all())
        
        target_tenants = {m.tenant_id for m in user.memberships}
        
        if resolved_tenant_id not in caller_mgr_tenants or resolved_tenant_id not in target_tenants:
            raise HTTPException(status_code=403, detail="Not authorized to reactivate this user in this tenant")

    if user.is_sysadmin:
        user.is_active = True
        user.status = UserStatus.ACTIVE
    else:
        membership = next((m for m in user.memberships if m.tenant_id == resolved_tenant_id), None)
        if not membership:
            raise HTTPException(status_code=404, detail="User is not a member of this tenant")
            
        membership.is_active = True
        membership.status = UserStatus.ACTIVE
    
    await db.commit()
    
    # Invalidate cache
    await invalidate_cache("user_list", resolved_tenant_id)
    
    # Publish event
    from app.core.events import event_publisher
    await event_publisher.publish("USER_REACTIVATED", {
        "user_id": str(user.id),
        "email": user.email,
        "tenant_id": resolved_tenant_id
    })
    
    # Re-fetch the user with memberships eagerly loaded after commit to avoid lazy loading in serialization
    result = await db.execute(
        select(User).where(User.id == user_id).options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    user = result.scalar_one()

    # Return serialized user with status mapped
    schema = UserSchema.model_validate(user)
    if user.is_sysadmin:
        schema.is_active = user.is_active
        schema.status = user.status.value if hasattr(user.status, 'value') else user.status
    else:
        schema.is_active = membership.is_active
        schema.status = membership.status.value if hasattr(membership.status, 'value') else membership.status
    return schema

@router.patch("/{user_id}/name", response_model=UserSchema)
async def update_user_name_admin(
    user_id: str,
    payload: UserNameUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_sysadmin),
):
    """
    Update a user's full name (SysAdmin only).
    Only system administrators can update user names.
    """
    from sqlalchemy.orm import selectinload
    
    # Verify user exists
    result = await db.execute(
        select(User).where(User.id == user_id).options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.full_name = payload.full_name
    await db.commit()

    # Invalidate cache for all tenants the user belongs to
    from app.core.cache import invalidate_cache
    for m in user.memberships:
        await invalidate_cache("user_list", m.tenant_id)

    # Publish event
    from app.core.events import event_publisher
    await event_publisher.publish("USER_UPDATED", {
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name
    })

    await db.refresh(user)
    
    # Reload with memberships
    result = await db.execute(
        select(User).where(User.id == user_id).options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    return result.scalar_one()

@router.get("/{user_id}", response_model=UserSchema)
async def read_user(
    user_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_tenant_user),
):
    """Get a specific user by ID."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User).where(User.id == user_id).options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/internal/batch", response_model=dict)
async def get_users_batch(
    user_ids: List[str],
    db: AsyncSession = Depends(deps.get_db),
    x_internal_api_key: Optional[str] = Header(None, alias="X-Internal-Api-Key"),
):
    """
    INTERNAL ONLY: Fetch basic user info (id, full_name, email, username) for a batch of IDs.
    """
    from app.core.config import settings
    if x_internal_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing internal API key")

    result = await db.execute(
        select(User.id, User.full_name, User.email, User.username).where(User.id.in_(user_ids))
    )
    users = result.all()
    # Format as { "user_id": { "full_name": "...", "email": "...", "username": "..." } }
    return {
        u.id: {
            "full_name": u.full_name,
            "email": u.email,
            "username": u.username
        } for u in users
    }

@router.patch("/me/password")
async def update_user_password(
    password_data: UserPasswordUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Update own password."""
    if not security.verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect old password")
    
    current_user.hashed_password = security.get_password_hash(password_data.new_password)
    await db.commit()
    return {"message": "Password updated successfully"}


# ---- Role Modification ----
class RoleUpdatePayload(BaseModel):
    tenant_id: str
    is_business_manager: bool = False
    is_training_creator: bool = False

@router.patch("/{user_id}/role")
async def modify_user_role(
    user_id: str,
    payload: RoleUpdatePayload,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    tenant_id: Optional[str] = Depends(deps.get_optional_tenant_id),
):
    """Modify a user's role within a tenant.
    SysAdmins can modify any user in any tenant.
    Business Managers can modify users within their own tenant.
    """
    from sqlalchemy.orm import selectinload
    
    # Auth check
    if not current_user.is_sysadmin:
        # Manager can only modify within their own tenant
        if not tenant_id:
             raise HTTPException(status_code=403, detail="Not a tenant-scoped token. Please select a tenant first.")
        if payload.tenant_id != tenant_id:
            raise HTTPException(status_code=403, detail="Not authorized to modify users in this tenant")
        # Check current user is a manager in that tenant
        mgr_membership = await db.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == current_user.id,
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.is_business_manager == True,
            )
        )
        if not mgr_membership.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not a business manager")
    # If SysAdmin, they can skip the scoped JWT check and just use payload.tenant_id
    
    membership = await db.execute(
        select(TenantMembership).where(
            TenantMembership.user_id == user_id,
            TenantMembership.tenant_id == payload.tenant_id,
        )
    )
    membership = membership.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="User is not a member of this tenant")
    
    membership.is_business_manager = payload.is_business_manager
    membership.is_training_creator = payload.is_training_creator
    await db.commit()
    
    # Invalidate cache
    await invalidate_cache("user_list", payload.tenant_id)
    
    return {"message": "Role updated successfully"}


# ---- Admin invite to any tenant ----
class UserLookupResponse(BaseModel):
    id: Optional[str] = None
    email: str
    full_name: Optional[str] = None
    existing_tenant_ids: List[str] = []
    is_active: bool = False

@router.get("/admin/lookup/{email}", response_model=UserLookupResponse)
async def lookup_user_by_email(
    email: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    email = email.lower()
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    
    if not user:
        return UserLookupResponse(email=email)
        
    # Get existing memberships
    mem_result = await db.execute(
        select(TenantMembership.tenant_id).where(TenantMembership.user_id == user.id)
    )
    existing_tenant_ids = [r[0] for r in mem_result.all()]
    
    return UserLookupResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        existing_tenant_ids=existing_tenant_ids,
        is_active=user.status == UserStatus.ACTIVE
    )

class AdminInvitePayload(BaseModel):
    email: str
    full_name: Optional[str] = None
    tenant_id: str
    is_business_manager: bool = False
    is_training_creator: bool = False

@router.post("/admin/invite-to-tenant", response_model=MagicLinkResponse)
async def admin_invite_to_tenant(
    payload: AdminInvitePayload,
    db: AsyncSession = Depends(deps.get_db),
    current_sysadmin: User = Depends(deps.get_sysadmin),
):
    # SysAdmin invites a user to a specific tenant with a specified role.
    email = payload.email.lower()
    
    # Ensure tenant exists
    from app.models.tenant import Tenant as TenantModel
    tenant = await db.get(TenantModel, payload.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Get or create user
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    
    # Logic for net-new vs existing user
    is_net_new = not user or user.status == UserStatus.PENDING
    if not user:
        user = User(
            email=email,
            hashed_password=None,
            is_active=False,
            status=UserStatus.PENDING,
            full_name=payload.full_name,
            avatar_url=get_random_avatar()
        )
        db.add(user)
        await db.flush()
    
    # Upsert membership
    mem_result = await db.execute(
        select(TenantMembership).where(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == payload.tenant_id,
        )
    )
    membership = mem_result.scalar_one_or_none()
    if not membership:
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=payload.tenant_id,
            is_employee=True,
            is_business_manager=payload.is_business_manager,
            is_training_creator=payload.is_training_creator,
            status=UserStatus.PENDING if is_net_new else UserStatus.ACTIVE
        )
        db.add(membership)
    else:
        membership.is_business_manager = payload.is_business_manager
        membership.is_training_creator = payload.is_training_creator
        # If user is already active elsewhere, this membership should also be active
        if not is_net_new:
            membership.status = UserStatus.ACTIVE
    
    if not is_net_new and user.status == UserStatus.ACTIVE:
        await db.commit()
        return {"invite_url": None, "message": "User is already active and has been added to the tenant."}

    # Generate registration token using UserToken
    token_str = generate(size=16)
    invite_url = f"{settings.FRONTEND_URL}/signup?token={token_str}"
    expires = datetime.now(timezone.utc) + timedelta(hours=48)
    user_token = UserToken(
        user_id=user.id,
        tenant_id=payload.tenant_id,
        token=token_str,
        expires_at=expires,
        is_used=False,
    )
    db.add(user_token)
    await db.commit()

    # Load tenant branding for email
    tenant_result = await db.execute(select(TenantModel).where(TenantModel.id == payload.tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    
    # Trigger event for email worker
    await event_publisher.publish("USER_INVITED", {
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name or user.email,
        "invite_url": invite_url,
        "token": token_str,
        "tenant_id": payload.tenant_id,
        "primary_color": tenant.primary_color if tenant else None,
        "secondary_color": tenant.secondary_color if tenant else None,
        "logo_url": tenant.logo_url if tenant else None,
        "tenant_name": tenant.name if tenant else "Our Platform"
    })
    
    # Invalidate user list cache
    await invalidate_cache("user_list", payload.tenant_id)
    
    return {"invite_url": invite_url, "message": "Invitation sent successfully"}


@router.get("/profile/{username}", response_model=UserSchema)
@cache_response("public_profile", expire=settings.CACHE_TTL_SHORT)
async def get_user_profile_by_username(
    username: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    tenant_id: Optional[str] = Depends(deps.get_optional_tenant_id),
) -> Any:
    """
    Get a user's profile by username.
    SysAdmins can view any profile.
    Business Managers and Training Creators can view profiles within their shared tenant.
    Plain employees can only view their own profile.
    """
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User)
        .where(User.username == username)
        .options(
            selectinload(User.memberships).selectinload(TenantMembership.tenant)
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Own profile: always allowed
    if user.id == current_user.id:
        return user

    # SysAdmin: can view anyone
    if current_user.is_sysadmin:
        return user

    # Non-admin viewing another user: must be manager or creator in a shared tenant
    current_user_tenants = {m.tenant_id for m in current_user.memberships}
    target_user_tenants = {m.tenant_id for m in user.memberships}
    shared_tenants = current_user_tenants.intersection(target_user_tenants)

    if not shared_tenants:
        raise HTTPException(status_code=403, detail="Cannot view profiles outside your organization")

    # Check if caller is a manager or creator in at least one shared tenant
    caller_is_privileged = any(
        m.is_business_manager or m.is_training_creator
        for m in current_user.memberships
        if m.tenant_id in shared_tenants
    )
    if not caller_is_privileged:
        raise HTTPException(status_code=403, detail="Only managers and creators can view other users' profiles")

    return user


