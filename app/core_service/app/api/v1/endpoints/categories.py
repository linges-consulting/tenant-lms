"""
Category CRUD endpoints — Task C4.

Routes:
  GET  /categories/       — Creator OR Manager, active categories only (tenant-scoped)
  POST /categories/       — Manager only, create; 409 on duplicate active name
  PUT  /categories/{id}   — Manager only, update name or is_active
  DELETE /categories/{id} — Manager only, soft-delete (is_active=False), 204
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.session import get_db
from app.models.category import TrainingCategory
from app.schemas.category import Category, CategoryCreate, CategoryUpdate

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /categories/ — list active categories (Creator or Manager)
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[Category])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> List[Category]:
    """Return all active categories for the current tenant."""
    result = await db.execute(
        select(TrainingCategory).where(
            and_(
                TrainingCategory.tenant_id == tenant_id,
                TrainingCategory.is_active.is_(True),
            )
        )
    )
    categories = result.scalars().all()
    return [Category.model_validate(c) for c in categories]


# ---------------------------------------------------------------------------
# POST /categories/ — create a new category (Manager only)
# ---------------------------------------------------------------------------

@router.post("/", response_model=Category, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Category:
    """Create a new active category. Returns 409 if an active category with the same name exists."""
    # Check for duplicate active name within this tenant
    existing = await db.execute(
        select(TrainingCategory).where(
            and_(
                TrainingCategory.tenant_id == tenant_id,
                TrainingCategory.name == payload.name,
                TrainingCategory.is_active.is_(True),
            )
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A category named '{payload.name}' already exists in this tenant.",
        )

    category = TrainingCategory(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=payload.name,
        is_active=True,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return Category.model_validate(category)


# ---------------------------------------------------------------------------
# PUT /categories/{id} — update category (Manager only)
# ---------------------------------------------------------------------------

@router.put("/{category_id}", response_model=Category)
async def update_category(
    category_id: str,
    payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Category:
    """Update a category's name and/or is_active flag. Scoped to the current tenant."""
    result = await db.execute(
        select(TrainingCategory).where(
            and_(
                TrainingCategory.id == category_id,
                TrainingCategory.tenant_id == tenant_id,
            )
        )
    )
    category = result.scalars().first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )

    if payload.name is not None:
        category.name = payload.name
    if payload.is_active is not None:
        category.is_active = payload.is_active

    await db.commit()
    await db.refresh(category)
    return Category.model_validate(category)


# ---------------------------------------------------------------------------
# DELETE /categories/{id} — soft-delete (Manager only), returns 204
# ---------------------------------------------------------------------------

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> None:
    """Soft-delete a category by setting is_active=False. Returns 204 on success."""
    result = await db.execute(
        select(TrainingCategory).where(
            and_(
                TrainingCategory.id == category_id,
                TrainingCategory.tenant_id == tenant_id,
            )
        )
    )
    category = result.scalars().first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )

    category.is_active = False
    await db.commit()
