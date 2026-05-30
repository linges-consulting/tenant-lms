from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel
from typing import Annotated, Any
import httpx
from datetime import datetime, timedelta, timezone
from nanoid import generate

from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

import httpx
from app.utils.provisioning import provision_default_certificate
from app.api import deps
from app.core import security
from app.core.cache import cache_response, invalidate_cache
from app.models.tenant import Tenant
from app.models.user import User, UserStatus
from app.models.membership import TenantMembership
from app.models.user_token import UserToken
from app.schemas.tenant import Tenant as TenantSchema
from app.schemas.tenant import TenantCreate, TenantUpdate
from app.api.v1.endpoints.users import get_random_avatar
from app.core.events import event_publisher

router = APIRouter()


class InternalTenantBranding(BaseModel):
    name: str
    primary_color: str
    secondary_color: str

@router.get("/admin/metrics")
@cache_response("admin_metrics", expire=settings.CACHE_TTL_MEDIUM)
async def get_admin_metrics(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_sysadmin: Annotated[User, Depends(deps.get_sysadmin)],
) -> Any:
    """
    Get global platform metrics (SysAdmin only).
    """
    # 1. Basic counts from Auth DB
    tenant_count = await db.scalar(select(func.count(Tenant.id)))
    user_count = await db.scalar(select(func.count(User.id)))
    
    # 2. Fetch User breakdown by tenant
    u_stmt = select(TenantMembership.tenant_id, func.count(TenantMembership.user_id)).group_by(TenantMembership.tenant_id)
    u_result = await db.execute(u_stmt)
    u_counts = {row[0]: row[1] for row in u_result.all()}
    
    # 3. Fetch Training/Certificate data from core-service
    core_metrics = {"total_trainings": 0, "total_certificates": 0, "tenant_breakdown": {}}
    async with httpx.AsyncClient() as client:
        try:
            # Use internal service name from settings or default to core-service
            core_url = "http://core-service:8000/api/v1/trainings/internal/metrics"
            response = await client.get(
                core_url,
                headers={"X-Internal-Api-Key": settings.INTERNAL_API_KEY},
                timeout=5.0
            )
            if response.status_code == 200:
                core_metrics = response.json()
        except Exception:
            # Silent fail for safety, keep defaults
            pass
            
    # 4. Fetch Tenant names for breakdown
    t_result = await db.execute(select(Tenant.id, Tenant.name))
    tenant_names = {row[0]: row[1] for row in t_result.all()}
    
    # 5. Build breakdown strings
    user_breakdown_parts = []
    training_breakdown_parts = []
    
    # Sort by name for consistency
    sorted_tenants = sorted(tenant_names.items(), key=lambda x: x[1])
    
    for tid, name in sorted_tenants:
        # Users
        uc = u_counts.get(tid, 0)
        user_breakdown_parts.append(f"{name}: {uc}")
        
        # Trainings
        tc = core_metrics["tenant_breakdown"].get(tid, {}).get("training_count", 0)
        training_breakdown_parts.append(f"{name}: {tc}")
        
    user_breakdown = " | ".join(user_breakdown_parts) if user_breakdown_parts else f"Total Users: {user_count}"
    training_breakdown = " | ".join(training_breakdown_parts) if training_breakdown_parts else "No training data available"

    return [
        {"label": "Active Tenants", "value": str(tenant_count), "trend": "", "isAlert": False},
        {"label": "Global Users", "value": str(user_count), "trend": user_breakdown, "isAlert": True},
        {"label": "Total Trainings", "value": str(core_metrics["total_trainings"]), "trend": training_breakdown, "isAlert": False},
        {"label": "System Status", "value": "Healthy", "trend": "All systems nominal", "isAlert": False},
    ]

@router.get("", response_model=list[TenantSchema])
@cache_response("tenant_list", expire=settings.CACHE_TTL_LONG)
async def list_tenants(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_sysadmin: Annotated[User, Depends(deps.get_sysadmin)],
) -> Any:
    """
    Retrieve all tenants with aggregated counts (SysAdmin only).
    """
    # Fetch all tenants
    result = await db.execute(select(Tenant))
    tenants = result.scalars().all()
    
    # Enrich with counts
    enriched_tenants = []
    
    # Fetch Training/Certificate data from core-service for all tenants
    all_core_metrics = {}
    async with httpx.AsyncClient() as client:
        try:
            core_url = "http://core-service:8000/api/v1/trainings/internal/metrics"
            response = await client.get(
                core_url,
                headers={"X-Internal-Api-Key": settings.INTERNAL_API_KEY},
                timeout=5.0
            )
            if response.status_code == 200:
                all_core_metrics = response.json().get("tenant_breakdown", {})
        except Exception:
            pass

    for tenant in tenants:
        # User count
        u_count = await db.scalar(
            select(func.count(TenantMembership.user_id))
            .where(TenantMembership.tenant_id == tenant.id)
        )
        
        # Course (Training) count from core-service
        tenant_core = all_core_metrics.get(tenant.id, {})
        c_count = tenant_core.get("training_count", 0)
        
        # Certificate (Enrollment where completed) count from core-service
        cert_count = tenant_core.get("certificate_count", 0)
        
        # Create a dictionary for the schema
        tenant_data = {
            "id": tenant.id,
            "name": tenant.name,
            "primary_color": tenant.primary_color,
            "secondary_color": tenant.secondary_color,
            "logo_url": tenant.logo_url,
            "is_active": tenant.is_active,
            "user_count": u_count or 0,
            "course_count": c_count or 0,
            "certificate_count": cert_count or 0
        }
        enriched_tenants.append(tenant_data)
        
    return enriched_tenants

@router.post("", response_model=TenantSchema, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_in: TenantCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_sysadmin: Annotated[User, Depends(deps.get_sysadmin)],
) -> Any:
    """
    Create a new tenant and assign a primary administrator (SysAdmin only).
    """
    # 1. Create Tenant
    tenant = Tenant(
        name=tenant_in.name,
        logo_url=tenant_in.logo_url,
        primary_color=tenant_in.primary_color,
        secondary_color=tenant_in.secondary_color
    )
    db.add(tenant)
    await db.flush()  # Get tenant.id

    # 2. Find or Create Admin User
    admin_email = tenant_in.admin_email.lower()
    result = await db.execute(select(User).where(User.email == admin_email))
    user = result.scalars().first()

    is_net_new = False
    if not user:
        is_net_new = True
        # Create new user if they don't exist
        user = User(
            email=admin_email,
            full_name=tenant_in.admin_name,
            hashed_password=None,
            is_active=False,
            is_sysadmin=False,
            status=UserStatus.PENDING,
            avatar_url=get_random_avatar()
        )
        db.add(user)
        await db.flush() # Get user.id

    # 3. Create Membership (as Manager)
    membership = TenantMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        is_business_manager=True,
        is_training_creator=True,
        is_employee=True,
        status="ACTIVE" if not is_net_new and user.status == UserStatus.ACTIVE else "PENDING"
    )
    db.add(membership)
    await db.flush()

    # 4. Generate Registration URL for the new manager if they are PENDING or net-new
    registration_url = None
    if is_net_new or user.status == UserStatus.PENDING:
        token_str = generate(size=16)
        expires = datetime.now(timezone.utc) + timedelta(hours=48) # Give them 2 days (BR-103)
        
        user_token = UserToken(
            user_id=user.id,
            tenant_id=tenant.id,
            token=token_str,
            expires_at=expires,
            is_used=False
        )
        db.add(user_token)
        
        frontend_url = settings.FRONTEND_URL.rstrip('/')
        registration_url = f"{frontend_url}/register?token={token_str}"
    
    await db.commit()
    await db.refresh(tenant)
    
    # 5. Trigger Invitation Email for the new manager
    if registration_url:
        await event_publisher.publish("USER_INVITED", {
            "user_id": str(user.id),
            "email": admin_email,
            "full_name": user.full_name or admin_email,
            "invite_url": registration_url,
            "token": token_str,
            "tenant_id": str(tenant.id),
            "primary_color": tenant.primary_color,
            "secondary_color": tenant.secondary_color,
            "logo_url": tenant.logo_url,
            "tenant_name": tenant.name
        })
    
    # Invalidate cache for sysadmin views
    await invalidate_cache("admin_metrics", "default")
    await invalidate_cache("tenant_list", "default")
    
    # Auto-provision a default professional landscape certificate template for the new tenant
    await provision_default_certificate(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        brand_color=tenant.primary_color
    )
    
    # Convert to schema and attach the link
    tenant_data = TenantSchema.model_validate(tenant)
    tenant_data.manager_invite_url = registration_url
    tenant_data.is_admin_new = is_net_new or user.status == UserStatus.PENDING
    
    return tenant_data

@router.get("/admin/{tenant_id}", response_model=TenantSchema)
async def get_tenant(
    tenant_id: str,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_sysadmin: Annotated[User, Depends(deps.get_sysadmin)],
) -> Any:
    """
    Get a single tenant's full details with user count (SysAdmin only).
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    u_count = await db.scalar(
        select(func.count(TenantMembership.user_id))
        .where(TenantMembership.tenant_id == tenant.id)
    )

    return {
        "id": tenant.id,
        "name": tenant.name,
        "primary_color": tenant.primary_color,
        "secondary_color": tenant.secondary_color,
        "logo_url": tenant.logo_url,
        "is_active": tenant.is_active,
        "user_count": u_count or 0,
        "course_count": 0,
        "certificate_count": 0,
    }

@router.post("/{tenant_id}/deactivate", response_model=TenantSchema)
async def deactivate_tenant(
    tenant_id: str,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_sysadmin: Annotated[User, Depends(deps.get_sysadmin)],
):
    """Deactivate a tenant (SysAdmin ONLY)."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    tenant.is_active = False
    await db.commit()
    await db.refresh(tenant)
    return tenant

@router.post("/{tenant_id}/activate", response_model=TenantSchema)
async def activate_tenant(
    tenant_id: str,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_sysadmin: Annotated[User, Depends(deps.get_sysadmin)],
):
    """Activate a tenant (SysAdmin ONLY)."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    tenant.is_active = True
    await db.commit()
    await db.refresh(tenant)
    return tenant

@router.api_route("/admin/{tenant_id}", methods=["PUT", "PATCH"], response_model=TenantSchema)
async def update_tenant_settings(
    tenant_id: str,
    tenant_in: TenantUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_sysadmin: Annotated[User, Depends(deps.get_sysadmin)],
) -> Any:
    """
    Update tenant settings and active status (SysAdmin only).
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    update_data = tenant_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)

    await db.commit()
    await db.refresh(tenant)

    # Invalidate cache for sysadmin views
    await invalidate_cache("admin_metrics", "default")
    await invalidate_cache("tenant_list", "default")

    # We will just return the tenant.
    return tenant

@router.get("/internal/branding/{tenant_id}", response_model=InternalTenantBranding, include_in_schema=False)
async def get_tenant_branding_internal(
    tenant_id: str,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    _: None = Depends(deps.validate_internal_api),
):
    """
    Internal endpoint for branding lookup by core-service.
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return InternalTenantBranding(
        name=tenant.name,
        primary_color=tenant.primary_color or "#2c3e50",
        secondary_color=tenant.secondary_color or "#ffffff"
    )
