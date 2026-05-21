from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.core.cache import cache_response, invalidate_cache

from app.api import deps
from app.models.user import User
from app.models.group import Group, GroupMembership
from app.models.membership import TenantMembership
from app.schemas.group import GroupOut, GroupCreate, GroupUpdate, GroupMemberOut, AddGroupMembersPayload

router = APIRouter()


@router.get("", response_model=List[GroupOut])
@cache_response("group_list", expire=600)
async def list_groups(
    db: AsyncSession = Depends(deps.get_db),
    current_manager: User = Depends(deps.get_manager_or_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    """List all groups in the active tenant."""
    result = await db.execute(
        select(Group)
        .where(Group.tenant_id == tenant_id)
        .options(selectinload(Group.members))
    )
    groups = result.scalars().all()
    return [
        GroupOut(
            id=g.id,
            tenant_id=g.tenant_id,
            name=g.name,
            description=g.description,
            created_at=g.created_at,
            member_count=len(g.members),
        )
        for g in groups
    ]


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_manager: User = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    """Create a new group in the active tenant."""
    group = Group(tenant_id=tenant_id, name=payload.name, description=payload.description)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    
    # Invalidate group list cache
    await invalidate_cache("group_list", tenant_id)
    
    return GroupOut(
        id=group.id, tenant_id=group.tenant_id, name=group.name,
        description=group.description, created_at=group.created_at, member_count=0,
    )


@router.patch("/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: str,
    payload: GroupUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_manager: User = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    """Update group name or description."""
    result = await db.execute(
        select(Group).where(and_(Group.id == group_id, Group.tenant_id == tenant_id))
        .options(selectinload(Group.members))
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if payload.name is not None:
        group.name = payload.name
    if payload.description is not None:
        group.description = payload.description
    await db.commit()
    await db.refresh(group)
    
    # Invalidate group list cache
    await invalidate_cache("group_list", tenant_id)
    
    return GroupOut(
        id=group.id, tenant_id=group.tenant_id, name=group.name,
        description=group.description, created_at=group.created_at, member_count=len(group.members),
    )


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_manager: User = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> None:
    """Delete a group (members are removed, users are not deleted)."""
    result = await db.execute(
        select(Group).where(and_(Group.id == group_id, Group.tenant_id == tenant_id))
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    await db.delete(group)
    await db.commit()
    
    # Invalidate group list cache
    await invalidate_cache("group_list", tenant_id)


@router.get("/{group_id}/members", response_model=List[GroupMemberOut])
async def list_group_members(
    group_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_manager: User = Depends(deps.get_manager_or_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    """List members of a group."""
    result = await db.execute(
        select(Group).where(and_(Group.id == group_id, Group.tenant_id == tenant_id))
        .options(selectinload(Group.members).selectinload(GroupMembership.user))
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return [
        GroupMemberOut(
            user_id=m.user_id,
            added_at=m.created_at,
            user_email=m.user.email if m.user else None,
            user_name=m.user.full_name if m.user else None,
            user_avatar_url=m.user.avatar_url if m.user else None,
        )
        for m in group.members
    ]


@router.post("/{group_id}/members", status_code=status.HTTP_201_CREATED)
async def add_group_members(
    group_id: str,
    payload: AddGroupMembersPayload,
    db: AsyncSession = Depends(deps.get_db),
    current_manager: User = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    """Add users to a group. Ignores already-existing memberships."""
    result = await db.execute(
        select(Group).where(and_(Group.id == group_id, Group.tenant_id == tenant_id))
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Validate that submitted user_ids belong to the caller's tenant and are active
    valid_members_result = await db.execute(
        select(TenantMembership.user_id).where(
            and_(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id.in_(payload.user_ids),
                TenantMembership.is_active == True,
            )
        )
    )
    valid_user_ids = set(valid_members_result.scalars().all())

    if not valid_user_ids:
        raise HTTPException(status_code=400, detail="No valid tenant members found in the provided user list.")

    # Fetch existing memberships to avoid duplicates
    existing = await db.execute(
        select(GroupMembership.user_id).where(GroupMembership.group_id == group_id)
    )
    existing_ids = {r for r in existing.scalars().all()}

    added = 0
    for uid in payload.user_ids:
        if uid in valid_user_ids and uid not in existing_ids:
            db.add(GroupMembership(group_id=group_id, user_id=uid))
            added += 1

    await db.commit()

    # Invalidate group list cache (member count changed)
    await invalidate_cache("group_list", tenant_id)

    return {"added": added, "message": f"Added {added} member(s) to group."}


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(
    group_id: str,
    user_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_manager: User = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> None:
    """Remove a user from a group."""
    # Verify the group belongs to the caller's tenant
    group_result = await db.execute(
        select(Group).where(and_(Group.id == group_id, Group.tenant_id == tenant_id))
    )
    group = group_result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    result = await db.execute(
        select(GroupMembership).where(
            and_(GroupMembership.group_id == group_id, GroupMembership.user_id == user_id)
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    await db.delete(membership)
    await db.commit()
    
    # Invalidate group list cache (member count changed)
    await invalidate_cache("group_list", tenant_id)


@router.post("/internal/batch", response_model=dict)
async def get_groups_batch(
    group_ids: List[str],
    db: AsyncSession = Depends(deps.get_db),
    x_internal_api_key: Optional[str] = Header(None, alias="X-Internal-Api-Key"),
):
    """
    INTERNAL ONLY: Fetch basic group info (id, name) for a batch of IDs.
    """
    from app.core.config import settings
    if x_internal_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing internal API key")

    result = await db.execute(
        select(Group.id, Group.name).where(Group.id.in_(group_ids))
    )
    groups = result.all()
    # Format as { "group_id": { "name": "..." } }
    return {
        g.id: {
            "name": g.name
        } for g in groups
    }
