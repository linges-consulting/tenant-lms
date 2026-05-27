import random
import traceback
import sys
import logging

BANNER_PRESETS = ("ocean", "sunset", "forest", "ember")
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query as QP
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, delete
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.api import deps
from app.core.cache import cache_response, invalidate_cache
from app.models.training import Training
from app.models.module import Module
from app.models.chapter import Chapter, ContentType
from app.models.progress import UserProgress, ProgressStatus
from app.models.training_history import TrainingHistory
from app.models.enrollment import Enrollment
from app.models.assignment import TrainingAssignment
from app.models.quiz_attempt import QuizAttempt
from app.models.audit_log import AuditLog
from app.models.collaborator import TrainingCollaborator
from app.models.certificate import Certificate
from app.models.certificate_template import CertificateTemplate
from app import schemas
from app.schemas.training import Training as TrainingSchema
from app.schemas.training import TrainingStructure, TrainingCreate, TrainingUpdate, TrainingHistorySnapshot, TrainingCollaborator as TrainingCollaboratorSchema, TrainingAuditLog
from app.schemas.module import ModuleWithChapters, ModuleCreate, ModuleUpdate, Module as ModuleSchema
from app.schemas.chapter import Chapter as ChapterSchema, ChapterCreate, ChapterUpdate
from app.schemas.reorder import BulkReorder
from app.schemas.assignment import (
    TrainingAssignment as AssignmentSchema, 
    BulkAssignmentCreate, 
    TrainingAssignmentUpdate
)
from datetime import datetime, timezone
import uuid
import shutil
import os
from app.utils import storage
from app.schemas.metrics import GlobalMetrics, TenantMetric

router = APIRouter()

logger = logging.getLogger(__name__)


async def enrich_trainings_with_creator_names(trainings: List[Training]) -> List[TrainingSchema]:
    """Helper to bulk fetch creator names from auth_service."""
    user_ids = list(set([t.created_by_id for t in trainings if t.created_by_id]))
    users_data = await deps.get_users_batch(user_ids)
    
    result = []
    for t in trainings:
        schema = TrainingSchema.model_validate(t)
        if t.created_by_id and t.created_by_id in users_data:
            schema.creator_name = users_data[t.created_by_id].get("full_name")
        result.append(schema)
    return result

async def is_owner_or_admin(training: Training, current_user: deps.UserAuth) -> bool:
    """Check if user is the original creator or a SysAdmin."""
    if any(role in ["SysAdmin", "Admin"] for role in current_user.roles):
        return True
    return training.created_by_id == current_user.id

async def log_audit(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    metadata: dict = None
):
    """Utility to log training actions to AuditLog."""
    audit = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=metadata
    )
    db.add(audit)

async def check_training_edit_permission(
    training: Training, 
    current_user: deps.UserAuth, 
    db: AsyncSession
) -> bool:
    """
    Check if user has permission to edit a training draft.
    Owner, Collaborator, or Admin — but ONLY when training is in Draft state.

    BR-301: Editing is only permitted in Draft state.
    BR-302: Collaborators can edit the training only while it is in Draft state.
    """
    # BR-301/BR-302: editing is only allowed in Draft state.
    # Draft = is_ready=False AND is_published=False AND is_archived=False.
    if training.is_ready or training.is_published or training.is_archived:
        return False

    # Admins, Business Managers have tenant-wide edit access (in Draft)
    if any(role in ["Business Manager", "Admin", "SysAdmin"] for role in current_user.roles):
        return True

    # Training Creator can only edit if Owner or Collaborator
    if training.created_by_id == current_user.id:
        return True

    # Check if collaborator
    stmt = select(TrainingCollaborator).where(
        TrainingCollaborator.training_id == training.id,
        TrainingCollaborator.user_id == current_user.id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None

@router.get("", response_model=List[TrainingSchema])
@cache_response("assigned_trainings", expire=300, include_user_id=True)
async def read_trainings(
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    category: Optional[str] = QP(default=None, description="Filter by category"),
    tags: Optional[List[str]] = QP(default=None, description="Filter by one or more tags"),
):
    """
    Retrieve published trainings for the user's active tenant, 
    enriched with progress and assignment status.
    """
    try:
        # Subquery to count total chapters per training
        total_chapters_sub = (
            select(Chapter.training_id, func.count(Chapter.id).label("total_count"))
            .group_by(Chapter.training_id)
            .subquery()
        )

        # Subquery to count completed chapters for THIS user
        completed_chapters_sub = (
            select(UserProgress.training_id, func.count(UserProgress.id).label("completed_count"))
            .where(UserProgress.user_id == current_user.id)
            .where(UserProgress.status == ProgressStatus.COMPLETED)
            .where(UserProgress.deleted_at.is_(None))
            .group_by(UserProgress.training_id)
            .subquery()
        )

        # Get the latest due_date for the user's assignments to these trainings
        # We check both direct user assignments and group-based assignments
        assignment_filters = [TrainingAssignment.user_id == current_user.id]
        if current_user.groups:
            assignment_filters.append(TrainingAssignment.group_id.in_(current_user.groups))
            
        import logging
        auth_logger = logging.getLogger("request_response")
        auth_logger.info(f"DEBUG_AUTH: Resolved {len(current_user.groups)} groups for user {current_user.id} in tenant {tenant_id}: {current_user.groups}")

        assignment_sub = (
            select(
                TrainingAssignment.training_id,
                func.max(TrainingAssignment.due_date).label("due_date")
            )
            .where(
                TrainingAssignment.tenant_id == tenant_id,
                or_(*assignment_filters)
            )
            .group_by(TrainingAssignment.training_id)
            .subquery()
        )

        stmt = (
            select(
                Training,
                func.coalesce(total_chapters_sub.c.total_count, 0).label("total_chapters"),
                func.coalesce(completed_chapters_sub.c.completed_count, 0).label("completed_chapters"),
                assignment_sub.c.due_date
            )
            .join(assignment_sub, Training.id == assignment_sub.c.training_id)
            .outerjoin(total_chapters_sub, Training.id == total_chapters_sub.c.training_id)
            .outerjoin(completed_chapters_sub, Training.id == completed_chapters_sub.c.training_id)
            .where(Training.tenant_id == tenant_id)
            .where(Training.is_published == True)
            .where(Training.is_active == True)
            .where(Training.deleted_at == None)
            .options(selectinload(Training.collaborators))
        )

        if category:
            stmt = stmt.where(Training.category == category)

        result = await db.execute(stmt)
        rows = result.all()

        # Apply tags filter in Python (cross-DB compatible with JSON column)
        if tags:
            tag_set = set(tags)
            rows = [row for row in rows if row[0].tags and tag_set.intersection(set(row[0].tags))]
        
        trainings_output = []
        now = datetime.now(timezone.utc)
        
        # Bulk fetch creator names
        user_ids = list(set([t[0].created_by_id for t in rows if t[0].created_by_id]))
        users_data = await deps.get_users_batch(user_ids)

        for training_obj, total_count, completed_count, due_date in rows:
            # Map to schema
            schema = TrainingSchema.model_validate(training_obj)
            schema.total_chapters = total_count
            schema.completed_chapters = completed_count
            
            # Enrich creator name
            if training_obj.created_by_id and training_obj.created_by_id in users_data:
                schema.creator_name = users_data[training_obj.created_by_id].get("full_name")
            
            # Calculate progress
            if total_count > 0:
                schema.progress_percentage = round((completed_count / total_count) * 100, 2)
            else:
                schema.progress_percentage = 0.0

            # Determine Status
            if due_date and due_date < now:
                schema.status = "expired"
            elif schema.progress_percentage >= 100:
                schema.status = "completed"
            elif schema.progress_percentage > 0:
                schema.status = "in_progress"
            else:
                schema.status = "not_started"
                
            trainings_output.append(schema)

        return trainings_output
    except Exception as e:
        err_msg = f"ERROR in read_trainings: {str(e)}\n{traceback.format_exc()}"
        print(err_msg, file=sys.stderr)
        raise HTTPException(status_code=500, detail=err_msg)

@router.get("/manager", response_model=List[TrainingSchema])
async def read_trainings_manager(
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    category: Optional[str] = QP(default=None, description="Filter by category"),
    tags: Optional[List[str]] = QP(default=None, description="Filter by one or more tags"),
    status: Optional[str] = QP(default=None, description="Filter by status: 'published', 'draft', or 'archived'"),
):
    """
    Retrieve ALL trainings for the user's active tenant (including drafts).
    Manager or Training Creator only.
    Supports optional filters: category, tags, status.
    """
    # Check permissions using roles from Auth Service
    is_authorized = any(role in ["Business Manager", "Training Creator", "Admin", "SysAdmin"] for role in current_user.roles)
    if not is_authorized:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    stmt = (
        select(Training)
        .where(Training.tenant_id == tenant_id)
        .where(Training.deleted_at == None)
        .options(selectinload(Training.collaborators))
    )

    # Business Managers and Admins see all trainings.
    # Pure Training Creators see only trainings they own or collaborate on.
    is_privileged = any(role in ["Business Manager", "Admin", "SysAdmin"] for role in current_user.roles)
    if not is_privileged:
        stmt = stmt.where(
            or_(
                Training.created_by_id == current_user.id,
                Training.collaborators.any(TrainingCollaborator.user_id == current_user.id)
            )
        )

    if category:
        stmt = stmt.where(Training.category == category)

    if status == "published":
        stmt = stmt.where(Training.is_published.is_(True))
    elif status == "draft":
        stmt = stmt.where(Training.is_published.is_(False), Training.is_archived.is_(False))
    elif status == "archived":
        stmt = stmt.where(Training.is_archived.is_(True))
    # Any other/unknown status value is silently ignored (no crash)

    # tags filter: JSON column — for SQLite compat we do a Python-side filter after fetch
    # For production PostgreSQL, a DB-level overlap/contains would be used instead.

    stmt = stmt.order_by(Training.id.desc())
    result = await db.execute(stmt)
    trainings = result.scalars().all()

    # Apply tags filter in Python (cross-DB compatible with JSON column)
    if tags:
        tag_set = set(tags)
        trainings = [t for t in trainings if t.tags and tag_set.intersection(set(t.tags))]

    return await enrich_trainings_with_creator_names(trainings)

@router.post("", response_model=TrainingSchema, status_code=status.HTTP_201_CREATED)
async def create_training(
    training_in: TrainingCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Create new training (as draft). Requires Training Creator role.
    """

    # 0a. Check for duplicate title within tenant
    dup_check = await db.execute(
        select(Training).where(
            Training.tenant_id == tenant_id,
            Training.title == training_in.title,
            Training.deleted_at == None,
        )
    )
    if dup_check.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A training with this name already exists.")

    # 0b. Validate Certificate Requirements
    requires_cert = training_in.requires_certificate if training_in.requires_certificate is not None else True
    if requires_cert and not training_in.template_id:
        raise HTTPException(
            status_code=400,
            detail="A certificate template must be selected if the training requires a certificate."
        )

    # Auto-assign a random preset banner if the caller didn't pick one.
    # The picker UI was removed; trainings always get a visual identity.
    thumbnail = training_in.thumbnail or f"preset:{random.choice(BANNER_PRESETS)}"

    db_item = Training(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title=training_in.title,
        description=training_in.description,
        category=training_in.category,
        duration=training_in.duration,
        thumbnail=thumbnail,
        version=1,
        is_published=False,
        requires_certificate=requires_cert,
        template_id=training_in.template_id,
        created_by_id=current_user.id,
        structure_type=training_in.structure_type,
        tags=training_in.tags,
        requires_recertification=training_in.requires_recertification,
        recertification_period_days=training_in.recertification_period_days,
    )
    training_id = db_item.id
    db.add(db_item)
    await db.commit()
    
    # Re-fetch with collaborators to avoid MissingGreenlet error
    stmt = select(Training).where(Training.id == training_id).options(selectinload(Training.collaborators))
    result = await db.execute(stmt)
    db_item = result.scalar_one()
    
    # Set creator name from the current user auth object for immediate response
    setattr(db_item, "creator_name", current_user.full_name)

    await log_audit(db, tenant_id, current_user.id, "CREATE_TRAINING", "training", training_id, {"title": db_item.title})
    await db.commit()
    
    return db_item

@router.put("/{training_id}", response_model=TrainingSchema)
async def update_training(
    training_id: str,
    training_in: TrainingUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Update a training. Requires Training Creator role.
    """

    stmt = (
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id, Training.deleted_at == None)
        .options(selectinload(Training.collaborators))
    )
    result = await db.execute(stmt)
    training = result.scalar_one_or_none()
    
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # BR-301/BR-302: editing only allowed in Draft state.
    if not await check_training_edit_permission(training, current_user, db):
        raise HTTPException(status_code=403, detail="Training must be in Draft state to edit content.")

    update_data = training_in.model_dump(exclude_unset=True)

    # Validate title uniqueness if title is being changed
    if "title" in update_data and update_data["title"] != training.title:
        dup_check = await db.execute(
            select(Training).where(
                Training.tenant_id == tenant_id,
                Training.title == update_data["title"],
                Training.id != training_id,
                Training.deleted_at == None,
            )
        )
        if dup_check.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="A training with this name already exists.")

    for field in update_data:
        setattr(training, field, update_data[field])

    # 1.5. Validate Certificate Requirements post-update
    if training.requires_certificate and not training.template_id:
        raise HTTPException(
            status_code=400,
            detail="A certificate template must be selected if the training requires a certificate."
        )
        
    await log_audit(db, tenant_id, current_user.id, "UPDATE_TRAINING", "training", training_id, update_data)
    await db.commit()

    # Invalidate relevant caches
    await invalidate_cache("training_detail", tenant_id)
    await invalidate_cache("training_structure", tenant_id)
    await invalidate_cache("assigned_trainings", tenant_id)

    # Re-fetch with eager-loaded collaborators to avoid MissingGreenlet on serialization
    refreshed_result = await db.execute(
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id)
        .options(selectinload(Training.collaborators))
    )
    training = refreshed_result.scalar_one()

    return training

@router.get("/{training_id}", response_model=TrainingSchema)
@cache_response("training_detail", expire=300, include_user_id=True)
async def read_training(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Retrieve a single training by ID.
    """
    # Managers/Creators can see inactive/draft trainings for preview/edit
    is_management = any(role in ["Business Manager", "Training Creator", "Admin"] for role in current_user.roles)
    
    stmt = select(Training).where(
        Training.id == training_id,
        Training.tenant_id == tenant_id,
        Training.deleted_at == None
    ).options(selectinload(Training.collaborators))
    
    if not is_management:
        stmt = stmt.where(Training.is_active == True)
        
    result = await db.execute(stmt)
    training = result.scalar_one_or_none()
    
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
        
    # Enrichment for Learners — count only live chapters so this matches
    # what /structure returns (which already filters via the join path).
    total_count = await db.scalar(
        select(func.count(Chapter.id))
        .where(Chapter.training_id == training_id)
        .where(Chapter.deleted_at.is_(None))
    ) or 0
    
    completed_count = 0
    due_date = None
    
    # Check for assignments and progress if user is not management (or even for managers if they want to see their own status)
    # Actually, for the detail view, we always try to show progress if it exists.
    completed_count = await db.scalar(
        select(func.count(UserProgress.id))
        .where(UserProgress.training_id == training_id, UserProgress.user_id == current_user.id, UserProgress.status == ProgressStatus.COMPLETED)
        .where(UserProgress.deleted_at.is_(None))
    ) or 0
    
    # Find due date
    due_date = await db.scalar(
        select(func.max(TrainingAssignment.due_date))
        .where(
            TrainingAssignment.training_id == training_id,
            or_(
                TrainingAssignment.user_id == current_user.id,
                TrainingAssignment.group_id.in_(current_user.groups) if current_user.groups else False
            )
        )
    )

    # Fetch enrollment for completed_at
    enroll_row = await db.scalar(
        select(Enrollment).where(
            Enrollment.training_id == training_id,
            Enrollment.user_id == current_user.id,
            Enrollment.tenant_id == tenant_id,
            Enrollment.deleted_at.is_(None),
        )
    )

    schema = TrainingSchema.model_validate(training)
    schema.total_chapters = total_count
    schema.completed_chapters = completed_count

    if total_count > 0:
        schema.progress_percentage = round((completed_count / total_count) * 100, 2)
    else:
        schema.progress_percentage = 0.0

    now = datetime.now(timezone.utc)
    if due_date and due_date < now:
        schema.status = "expired"
    elif schema.progress_percentage >= 100:
        schema.status = "completed"
    elif schema.progress_percentage > 0:
        schema.status = "in_progress"
    else:
        schema.status = "not_started"

    if enroll_row:
        if enroll_row.completed_at:
            schema.completed_at = enroll_row.completed_at.isoformat()
        if enroll_row.certificate_id:
            schema.certificate_id = str(enroll_row.certificate_id)

    # Creator Enrichment
    if training.created_by_id:
        users_data = await deps.get_users_batch([training.created_by_id])
        if training.created_by_id in users_data:
            schema.creator_name = users_data[training.created_by_id].get("full_name")

    return schema

@router.delete("/{training_id}")
async def delete_training(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Soft delete a training. Requires Training Creator role.
    """

    # Fetch with assignments to check for safeguard
    stmt = (
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id, Training.deleted_at == None)
        .options(selectinload(Training.assignments))
    )
    result = await db.execute(stmt)
    training = result.scalar_one_or_none()
    
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # Only the owner (Training Creator) can delete — not managers
    if training.created_by_id != current_user.id and "SysAdmin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Only the training owner can delete a training")

    # Deletion restricted to Draft state only
    if training.is_ready or training.is_published or training.is_archived:
        raise HTTPException(
            status_code=400,
            detail="Only draft trainings can be deleted. Use Archive to remove published trainings."
        )

    training.is_active = False
    training.deleted_at = datetime.now(timezone.utc)
    
    await log_audit(db, tenant_id, current_user.id, "DELETE_TRAINING", "training", training_id)
    await db.commit()
    return {"message": "Training archived"}

# Collaborator Management
@router.get("/{training_id}/collaborators", response_model=List[schemas.training.TrainingCollaborator])
async def list_collaborators(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """List all collaborators for a training draft."""
    stmt = select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id)
    result = await db.execute(stmt)
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    
    # Only owner or collaborator can see the list
    if not await check_training_edit_permission(training, current_user, db):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    stmt = select(TrainingCollaborator).where(TrainingCollaborator.training_id == training_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.delete("/{training_id}/collaborators/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_collaborator(
    training_id: str,
    user_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """Remove a collaborator from a training draft. Owner only."""
    stmt = select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id)
    result = await db.execute(stmt)
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    
    if not await is_owner_or_admin(training, current_user):
        raise HTTPException(status_code=403, detail="Only the owner or an admin can remove collaborators")

    stmt = select(TrainingCollaborator).where(
        TrainingCollaborator.training_id == training_id,
        TrainingCollaborator.user_id == user_id
    )
    result = await db.execute(stmt)
    db_item = result.scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="Collaborator not found")

    await db.delete(db_item)
    await log_audit(db, tenant_id, current_user.id, "COLLABORATOR_REMOVED", "training", training_id, {"collaborator_user_id": user_id})
    await db.commit()
    return None

@router.post("/{training_id}/assignments/bulk", response_model=dict)
async def bulk_assign_training(
    training_id: str,
    bulk_data: BulkAssignmentCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Bulk assign training to multiple users and/or groups.
    """
    # BR-301a: Only Business Managers and SysAdmins can assign trainings
    is_authorized = any(role in ["Business Manager", "SysAdmin"] for role in current_user.roles)
    if not is_authorized:
        raise HTTPException(status_code=403, detail="Only Business Managers can assign trainings.")

    # Verify training exists
    result = await db.execute(select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id))
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # TC-ASN-07: Only published or ready trainings can be assigned
    if not training.is_published and not training.is_ready:
        raise HTTPException(status_code=400, detail="Training must be published or ready before assigning.")

    assignments_to_add = []
    
    # Process user assignments
    for user_id in bulk_data.user_ids:
        # Check if already assigned
        existing = await db.execute(
            select(TrainingAssignment).where(
                TrainingAssignment.training_id == training_id,
                TrainingAssignment.user_id == user_id,
                TrainingAssignment.tenant_id == tenant_id
            )
        )
        if not existing.scalar_one_or_none():
            assignments_to_add.append(
                TrainingAssignment(
                    id=str(uuid.uuid4()),
                    training_id=training_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    due_date=bulk_data.due_date
                )
            )
            
            # Publish NEW_TRAINING_ASSIGNED event
            from app.core.events import publisher
            await publisher.publish_event(
                "NEW_TRAINING_ASSIGNED",
                {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "training_id": training_id,
                    "training_title": training.title,
                    "due_date": bulk_data.due_date.isoformat() if bulk_data.due_date else "No due date"
                }
            )

    # Process group assignments
    for group_id in bulk_data.group_ids:
        existing = await db.execute(
            select(TrainingAssignment).where(
                TrainingAssignment.training_id == training_id,
                TrainingAssignment.group_id == group_id,
                TrainingAssignment.tenant_id == tenant_id
            )
        )
        if not existing.scalar_one_or_none():
            assignments_to_add.append(
                TrainingAssignment(
                    id=str(uuid.uuid4()),
                    training_id=training_id,
                    tenant_id=tenant_id,
                    group_id=group_id,
                    due_date=bulk_data.due_date
                )
            )

    if assignments_to_add:
        db.add_all(assignments_to_add)
        await db.commit()
        
        # Invalidate assigned trainings for affected users/groups
        # We invalidate for the entire tenant to ensure consistency across all potentially affected users
        await invalidate_cache("assigned_trainings", tenant_id, user_id="")
        await invalidate_cache("assigned_trainings", tenant_id, user_id="*")
        
    return {"status": "success", "added_count": len(assignments_to_add)}

@router.get("/{training_id}/assignments", response_model=List[AssignmentSchema])
async def list_training_assignments(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    List all assignments for a specific training.
    """
    is_authorized = any(role in ["Business Manager", "Training Creator", "Admin"] for role in current_user.roles)
    if not is_authorized:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    stmt = (
        select(TrainingAssignment)
        .where(TrainingAssignment.training_id == training_id, TrainingAssignment.tenant_id == tenant_id)
    )
    result = await db.execute(stmt)
    assignments = result.scalars().all()
    
    # Enrichment
    user_ids = [a.user_id for a in assignments if a.user_id]
    group_ids = [a.group_id for a in assignments if a.group_id]
    
    users_data = await deps.get_users_batch(user_ids) if user_ids else {}
    groups_data = await deps.get_groups_batch(group_ids) if group_ids else {}
    
    enriched_assignments = []
    for a in assignments:
        schema = AssignmentSchema.model_validate(a)
        if a.user_id and a.user_id in users_data:
            schema.user_name = users_data[a.user_id].get("full_name")
        if a.group_id and a.group_id in groups_data:
            schema.group_name = groups_data[a.group_id].get("name")
        enriched_assignments.append(schema)
        
    return enriched_assignments

@router.post("/{training_id}/collaborators", response_model=List[TrainingCollaboratorSchema])
async def add_collaborators(
    training_id: str,
    collaborators_in: List[str],
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Add collaborators to a training. Only Owner can add.
    """
    result = await db.execute(select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id))
    training = result.scalar_one_or_none()
    
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
        
    if not await is_owner_or_admin(training, current_user):
        raise HTTPException(status_code=403, detail="Only the initial creator or an admin can manage collaborators")

    # Prevent owner from adding themselves as a collaborator
    for collaborator_user_id in collaborators_in:
        if collaborator_user_id == str(training.created_by_id):
            raise HTTPException(status_code=400, detail="Owner cannot be added as a collaborator")

    # Add each new collaborator
    newly_added: list[str] = []
    for uid in collaborators_in:
        # Check if already exists
        exists = await db.execute(
            select(TrainingCollaborator).where(
                TrainingCollaborator.training_id == training_id,
                TrainingCollaborator.user_id == uid
            )
        )
        if not exists.scalar_one_or_none():
            db.add(TrainingCollaborator(training_id=training_id, user_id=uid))
            await log_audit(db, tenant_id, current_user.id, "COLLABORATOR_ADDED", "training", training_id, {"collaborator_user_id": uid})
            newly_added.append(uid)

    await db.commit()

    # Publish COLLABORATOR_ADDED notification event for each newly added collaborator (BR-302a)
    from app.core.events import publisher
    for uid in newly_added:
        try:
            await publisher.publish_event(
                "COLLABORATOR_ADDED",
                {
                    "tenant_id": tenant_id,
                    "collaborator_user_id": uid,
                    "training_id": training_id,
                    "training_title": training.title,
                    "added_by_user_id": current_user.id,
                }
            )
        except Exception:
            import logging
            logging.getLogger(__name__).error(
                "Failed to publish COLLABORATOR_ADDED event for user %s on training %s", uid, training_id
            )

    # Return updated list
    updated = await db.execute(select(TrainingCollaborator).where(TrainingCollaborator.training_id == training_id))
    return updated.scalars().all()

@router.delete("/assignments/{assignment_id}", response_model=dict)
async def delete_assignment(
    assignment_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Remove an assignment.
    """
    is_authorized = any(role in ["Business Manager", "Training Creator", "Admin"] for role in current_user.roles)
    if not is_authorized:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    assignment = await db.execute(
        select(TrainingAssignment)
        .where(TrainingAssignment.id == assignment_id, TrainingAssignment.tenant_id == tenant_id)
    )
    assignment = assignment.scalar_one_or_none()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    await db.delete(assignment)
    await db.commit()
    
    # Invalidate assigned trainings
    await invalidate_cache("assigned_trainings", tenant_id)
    
    return {"status": "success", "message": "Assignment removed"}

@router.post("/{training_id}/archive", response_model=TrainingSchema)
async def archive_training(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Archive a training (Published → Archived). Manager only.
    Blocked (BR-503) if any learner has an incomplete enrollment whose assignment due_date is in the future.
    """
    # 1. Tenant-scoped lookup
    stmt = (
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id)
        .options(selectinload(Training.collaborators))
    )
    result = await db.execute(stmt)
    training = result.scalar_one_or_none()

    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # 2. State guard: must be Ready or Published and not already archived
    if not (training.is_ready or training.is_published) or training.is_archived:
        raise HTTPException(
            status_code=400,
            detail="Training must be in Ready or Published state to archive"
        )

    # 3. Archive gate (BR-503): block if any incomplete enrollment has a future assignment due_date
    now = datetime.now(timezone.utc)
    blocking_result = await db.execute(
        select(TrainingAssignment).where(
            TrainingAssignment.training_id == training_id,
            TrainingAssignment.tenant_id == tenant_id,
            TrainingAssignment.due_date > now,
        )
    )
    blocking_assignments = blocking_result.scalars().all()

    if blocking_assignments:
        # Separate individual (user_id) and group (group_id) assignments
        individual_assignments = [a for a in blocking_assignments if a.user_id is not None]
        group_assignments = [a for a in blocking_assignments if a.group_id is not None]

        # Check individual assignments: block if any assigned user has an incomplete enrollment
        if individual_assignments:
            assigned_user_ids = [a.user_id for a in individual_assignments]
            incomplete_result = await db.execute(
                select(Enrollment).where(
                    Enrollment.training_id == training_id,
                    Enrollment.tenant_id == tenant_id,
                    Enrollment.user_id.in_(assigned_user_ids),
                    Enrollment.is_completed == False,
                )
            )
            incomplete_enrollments = incomplete_result.scalars().all()
            if incomplete_enrollments:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot archive: some learners have not completed the training and their due dates have not passed."
                )

        # Group assignments: GroupMembership lives in the auth-service DB and cannot be
        # queried directly here.  Any future-dated group assignment is treated as blocking
        # because we cannot verify all group members have completed without cross-service
        # access.  This is the safe/conservative choice (BR-503).
        if group_assignments:
            raise HTTPException(
                status_code=400,
                detail="Cannot archive: there are active group assignments with future due dates — verify all group members have completed the training before archiving."
            )

    # 4. Transition to Archived
    training.is_archived = True
    training.is_active = False

    # 5. Audit log
    await log_audit(
        db, tenant_id, current_user.id,
        "ARCHIVE", "training", training_id,
        {"title": training.title}
    )

    await db.commit()

    # Re-fetch with eager loading
    refreshed_result = await db.execute(
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id)
        .options(selectinload(Training.collaborators))
    )
    training = refreshed_result.scalar_one()

    # Invalidate cache
    await invalidate_cache("assigned_trainings", tenant_id)
    await invalidate_cache("training_detail", tenant_id)

    return training

@router.post("/{training_id}/reassign/{user_id}", response_model=dict)
async def reassign_training(
    training_id: str,
    user_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Reassign a training to a user, triggering a full progress reset.
    Business Manager or Training Creator role required.
    """
    is_authorized = any(role in ["Business Manager", "Training Creator", "Admin"] for role in current_user.roles)
    if not is_authorized:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Verify training exists
    stmt = select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Training not found")

    # Reset progress for this user and training
    stmt_del = delete(UserProgress).where(
        UserProgress.training_id == training_id,
        UserProgress.user_id == user_id,
        UserProgress.tenant_id == tenant_id
    )
    await db.execute(stmt_del)
    
    # Reset Enrollment if exists
    stmt_enroll = select(Enrollment).where(
        Enrollment.training_id == training_id,
        Enrollment.user_id == user_id,
        Enrollment.tenant_id == tenant_id
    )
    res_enroll = await db.execute(stmt_enroll)
    enrollment = res_enroll.scalar_one_or_none()
    if enrollment:
        enrollment.status = "IN_PROGRESS"
        enrollment.completed_at = None
        enrollment.progress_percent = 0
    
    await db.commit()
    
    # Invalidate relevant caches
    await invalidate_cache("training_structure", tenant_id)
    await invalidate_cache("training_detail", tenant_id)
    await invalidate_cache("assigned_trainings", tenant_id)
    await invalidate_cache("user_stats", tenant_id, user_id=user_id)
    
    return {"status": "success", "message": f"Training reassigned to user {user_id}"}

@router.post("/{training_id}/mark-ready", response_model=TrainingSchema)
async def mark_training_ready(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Transition a training from Draft to Ready state (BR-305a).
    Only the training owner can mark ready.
    Requires: title, category, and at least one lesson.
    """
    # 1. Load training (tenant-isolated)
    stmt = (
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id, Training.deleted_at == None)
        .options(selectinload(Training.collaborators))
    )
    result = await db.execute(stmt)
    training = result.scalar_one_or_none()

    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # 2. Authorization: only the owner can mark ready
    if training.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the training owner can mark it as ready")

    # 3. State check: must be in Draft (is_ready=False, is_published=False, is_archived=False)
    if training.is_ready or training.is_published or training.is_archived:
        raise HTTPException(status_code=400, detail="Training must be in Draft state to mark as ready")

    # 4. Ready gate (BR-305a) — title, category, and at least one lesson required
    if not training.title:
        raise HTTPException(status_code=400, detail="Training must have a title")
    if not training.category:
        raise HTTPException(status_code=400, detail="Training must have a category")

    # Check at least one lesson (chapter) exists
    lesson_count_result = await db.execute(
        select(func.count()).select_from(Chapter).where(
            Chapter.training_id == training_id,
            Chapter.tenant_id == current_user.tenant_id,
        )
    )
    if lesson_count_result.scalar() == 0:
        raise HTTPException(status_code=400, detail="Training must have at least one lesson")

    # 5. Transition to Ready
    training.is_ready = True

    # 6. Audit log
    await log_audit(
        db, tenant_id, current_user.id,
        "MARK_READY", "training", training_id,
        {"title": training.title}
    )

    await db.commit()

    # Re-fetch with eager-loaded collaborators to avoid MissingGreenlet on serialization
    refreshed_result = await db.execute(
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == current_user.tenant_id)
        .options(selectinload(Training.collaborators))
    )
    training = refreshed_result.scalar_one()

    return training


@router.post("/{training_id}/send-to-draft", response_model=TrainingSchema)
async def send_training_to_draft(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Transition a training from Ready back to Draft state (BR-301a).
    Allowed: Training Creator (owner only) OR Business Manager.
    """
    # 1. Load training (tenant-isolated)
    stmt = (
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id, Training.deleted_at == None)
        .options(selectinload(Training.collaborators))
    )
    result = await db.execute(stmt)
    training = result.scalar_one_or_none()

    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # 2. Role authorization: Business Manager OR owner Training Creator
    is_manager = any(role in ["Business Manager", "Admin", "SysAdmin"] for role in current_user.roles)
    is_owner = training.created_by_id == current_user.id
    if not is_manager and not is_owner:
        raise HTTPException(status_code=403, detail="Only the training owner or a Manager can send to draft")

    # 3. State guard
    if training.is_archived:
        raise HTTPException(status_code=400, detail="Archived trainings cannot be sent to draft")

    if not training.is_ready and not training.is_published:
        raise HTTPException(status_code=400, detail="Training must be in Ready or Published state to send to draft")

    # 4. Branch on current state
    if training.is_published:
        # Published → Draft: Manager only
        if not is_manager:
            raise HTTPException(status_code=403, detail="Only a Manager can unpublish a training")

        # Reset all learner progress for this training
        # Delete UserProgress rows for all chapters in this training
        await db.execute(
            delete(UserProgress).where(UserProgress.training_id == training_id)
        )
        # Reset enrollment completion status (keep enrollment records, just un-complete them)
        enrollments_result = await db.execute(
            select(Enrollment).where(
                Enrollment.training_id == training_id,
                Enrollment.tenant_id == tenant_id,
            )
        )
        enrollments = enrollments_result.scalars().all()
        for enrollment in enrollments:
            enrollment.is_completed = False
            enrollment.completed_at = None
            enrollment.training_version_id = None

        training.is_published = False
        training.is_ready = False

        # Audit log: UNPUBLISH
        await log_audit(
            db, tenant_id, current_user.id,
            "UNPUBLISH", "training", training_id,
            {"title": training.title}
        )
    else:
        # Ready → Draft: Creator (owner) OR Manager
        training.is_ready = False

        # Audit log: SEND_TO_DRAFT
        await log_audit(
            db, tenant_id, current_user.id,
            "SEND_TO_DRAFT", "training", training_id,
            {"title": training.title}
        )

    await db.commit()

    # Re-fetch with eager-loaded collaborators to avoid MissingGreenlet on serialization
    refreshed_result = await db.execute(
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id)
        .options(selectinload(Training.collaborators))
    )
    updated = refreshed_result.scalar_one_or_none()
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated training")

    return updated


@router.post("/{training_id}/publish", response_model=TrainingSchema)
async def publish_training(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_business_manager),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Publish a training (Ready → Published). Manager only.
    Training must be in Ready state (is_ready=True, is_published=False, is_archived=False).
    """
    # 1. Tenant-scoped lookup
    result = await db.execute(
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id)
        .options(selectinload(Training.collaborators))
    )
    training = result.scalar_one_or_none()

    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # 2. State guard: must be Ready (is_ready=True, is_published=False, is_archived=False)
    if not training.is_ready or training.is_published or training.is_archived:
        raise HTTPException(
            status_code=400,
            detail="Training must be in Ready state to publish (is_ready=True, not already published or archived)"
        )

    # 2a. Pushback check (BR-402, BR-602): compare current chapters to the previous
    #     published snapshot (TrainingHistory at training.version).  If any chapter's
    #     content_data changed, soft-delete learner progress from the first changed
    #     chapter onwards and write an audit log entry per affected user.
    old_history_result = await db.execute(
        select(TrainingHistory)
        .where(
            TrainingHistory.training_id == training_id,
            TrainingHistory.version == training.version,
        )
    )
    old_history = old_history_result.scalar_one_or_none()

    if old_history and old_history.snapshot:
        def flatten_chapters(struct):
            """
            Extract all chapters from a training structure snapshot into a flat dict
            keyed by chapter id.  Handles both 'orphan_chapters' (current key) and
            legacy 'chapters' key, plus chapters nested inside modules.
            """
            chaps = {}
            for m in struct.get("modules", []):
                for c in m.get("chapters", []):
                    chaps[c["id"]] = c
            for c in struct.get("orphan_chapters", []):
                chaps[c["id"]] = c
            for c in struct.get("chapters", []):
                chaps[c["id"]] = c
            return chaps

        # Get current chapters from DB
        current_chapters_result = await db.execute(
            select(Chapter)
            .where(Chapter.training_id == training_id)
        )
        current_chapters = current_chapters_result.scalars().all()
        current_chapter_map = {ch.id: ch for ch in current_chapters}

        old_chapter_map = flatten_chapters(old_history.snapshot)

        modified_chapter_ids = []
        for cid, old_ch in old_chapter_map.items():
            if cid in current_chapter_map:
                if current_chapter_map[cid].content_data != old_ch.get("content_data"):
                    modified_chapter_ids.append(cid)

        if modified_chapter_ids:
            # Find the minimum sequence_order among changed chapters to cascade forward.
            changed_seq_result = await db.execute(
                select(Chapter.sequence_order)
                .where(Chapter.id.in_(modified_chapter_ids))
            )
            changed_seq_orders = changed_seq_result.scalars().all()
            min_changed_seq = min(changed_seq_orders) if changed_seq_orders else 0

            # All chapters at or after the first changed chapter's position.
            cascade_chapter_result = await db.execute(
                select(Chapter.id)
                .where(
                    Chapter.training_id == training_id,
                    Chapter.sequence_order >= min_changed_seq,
                )
            )
            cascade_chapter_ids = cascade_chapter_result.scalars().all()

            # Find affected learners (exclude already soft-deleted rows).
            affected_users_result = await db.execute(
                select(UserProgress.user_id)
                .where(
                    UserProgress.chapter_id.in_(cascade_chapter_ids),
                    UserProgress.deleted_at.is_(None),
                )
                .distinct()
            )
            affected_users = affected_users_result.scalars().all()

            if affected_users:
                now = datetime.now(timezone.utc)

                # Soft-delete progress rows (BR rule #2: no hard deletes).
                progress_rows_result = await db.execute(
                    select(UserProgress).where(
                        UserProgress.chapter_id.in_(cascade_chapter_ids),
                        UserProgress.user_id.in_(affected_users),
                        UserProgress.deleted_at.is_(None),
                    )
                )
                for row in progress_rows_result.scalars().all():
                    row.deleted_at = now

                # Reset enrollment so learners must re-complete (do NOT soft-delete
                # the enrollment row — _process_training_completion needs it).
                enrollment_rows_result = await db.execute(
                    select(Enrollment).where(
                        Enrollment.training_id == training_id,
                        Enrollment.user_id.in_(affected_users),
                    )
                )
                for enr in enrollment_rows_result.scalars().all():
                    enr.is_completed = False
                    enr.completed_at = None

                # Append-only audit log per affected user (BR rules #3 and #6).
                for uid in affected_users:
                    db.add(AuditLog(
                        tenant_id=tenant_id,
                        user_id=current_user.id,
                        action="progress_reset",
                        entity_type="Training",
                        entity_id=training_id,
                        metadata_json={
                            "version": training.version,
                            "affected_user_id": uid,
                            "cascade_from_sequence_order": min_changed_seq,
                            "modified_chapter_ids": list(modified_chapter_ids),
                        },
                    ))

    # 3. Bump version integer on each publish
    training.is_published = True
    training.version = (training.version or 0) + 1

    # 3a. Write a history snapshot so the /history endpoint has a record
    history_snapshot = TrainingHistory(
        tenant_id=tenant_id,
        training_id=training_id,
        version=training.version,
        snapshot={
            "title": training.title,
            "description": training.description,
            "category": training.category,
            "structure_type": training.structure_type,
            "version": training.version,
        },
    )
    db.add(history_snapshot)

    # 4. Audit log
    await log_audit(
        db, tenant_id, current_user.id,
        "PUBLISH", "training", training_id,
        {"title": training.title, "version": training.version}
    )

    await db.commit()

    # Re-fetch with eager-loaded collaborators to avoid MissingGreenlet on serialization
    refreshed_result = await db.execute(
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id)
        .options(selectinload(Training.collaborators))
    )
    training = refreshed_result.scalar_one()

    # Invalidate caches
    await invalidate_cache("training_detail", tenant_id)
    await invalidate_cache("training_structure", tenant_id)
    await invalidate_cache("assigned_trainings", tenant_id)

    return training

@router.get("/{training_id}/history", response_model=List[TrainingHistorySnapshot])
async def get_training_history(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Get the version history snapshots of a training.
    """
    is_authorized = any(role in ["Business Manager", "Training Creator", "Admin"] for role in current_user.roles)
    if not is_authorized:
        raise HTTPException(status_code=403, detail="Not enough permissions")
        
    history = await db.execute(
        select(TrainingHistory)
        .where(TrainingHistory.training_id == training_id)
        .where(TrainingHistory.tenant_id == tenant_id)
        .order_by(TrainingHistory.version.desc())
    )
    return history.scalars().all()

@router.get("/{training_id}/audit", response_model=List[TrainingAuditLog])
async def get_training_audit(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Get the audit log for a training (BR-309a).

    Role-based visibility:
    - Owner (Training Creator who owns the training): all events.
    - Active collaborator: all events.
    - Business Manager (not owner/collaborator): state-transition events only
      (MARK_READY, SEND_TO_DRAFT, PUBLISH, UNPUBLISH, ARCHIVE).
    - Anyone else: 403 Forbidden.
    """
    # State-transition actions visible to Business Managers
    STATE_TRANSITION_ACTIONS = {"MARK_READY", "SEND_TO_DRAFT", "PUBLISH", "UNPUBLISH", "ARCHIVE"}

    # 1. Load the training (tenant-scoped) — 404 if not found
    training_stmt = select(Training).where(
        Training.id == training_id,
        Training.tenant_id == tenant_id,
        Training.deleted_at.is_(None),
    )
    training_result = await db.execute(training_stmt)
    training = training_result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # 2. Determine relationship to the training
    is_owner = training.created_by_id == current_user.id
    is_manager = any(role in ["Business Manager", "Admin", "SysAdmin"] for role in current_user.roles)

    is_collaborator = False
    if not is_owner:
        collab_stmt = select(TrainingCollaborator).where(
            TrainingCollaborator.training_id == training_id,
            TrainingCollaborator.user_id == current_user.id,
        )
        collab_result = await db.execute(collab_stmt)
        is_collaborator = collab_result.scalar_one_or_none() is not None

    # 3. Access control: must be manager OR owner OR collaborator
    if not (is_manager or is_owner or is_collaborator):
        raise HTTPException(status_code=403, detail="Not enough permissions to view this training's audit log")

    # 4. Query audit_logs for the training
    audit_stmt = (
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .where(AuditLog.entity_id == training_id)
        .order_by(AuditLog.created_at.desc())
        .limit(200)
    )
    result = await db.execute(audit_stmt)
    logs = result.scalars().all()

    # 5. Role-based filtering: Managers (not owner, not collaborator) see only state transitions
    if is_manager and not is_owner and not is_collaborator:
        logs = [l for l in logs if l.action in STATE_TRANSITION_ACTIONS]

    # 6. Enrich with user names (best-effort)
    user_ids = list(set(l.user_id for l in logs))
    users_data = await deps.get_users_batch(user_ids)

    enriched = []
    for l in logs:
        schema = TrainingAuditLog.model_validate(l)
        if l.user_id in users_data:
            schema.user_name = users_data[l.user_id].get("full_name")
        enriched.append(schema)

    return enriched

@router.post("/{training_id}/modules/reorder", response_model=dict)
async def reorder_modules(
    training_id: str,
    reorder_in: BulkReorder,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Reorder modules within a training.
    """
    stmt = select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id)
    result = await db.execute(stmt)
    training = result.scalar_one_or_none()
    
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # BR-301/BR-302: editing only allowed in Draft state.
    if not await check_training_edit_permission(training, current_user, db):
        raise HTTPException(status_code=403, detail="Training must be in Draft state to edit content.")

    # Bulk update sequence orders
    for item in reorder_in.items:
        await db.execute(
            Module.__table__.update()
            .where(Module.id == item.id)
            .where(Module.training_id == training_id)
            .values(sequence_order=item.sequence_order)
        )
    
    await log_audit(db, tenant_id, current_user.id, "REORDER_MODULES", "training", training_id)
    await db.commit()
    await invalidate_cache("training_structure", tenant_id)
    return {"status": "success"}

@router.post("/{training_id}/modules/{module_id}/chapters/reorder", response_model=dict)
async def reorder_chapters(
    training_id: str,
    module_id: str,
    reorder_in: BulkReorder,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Reorder chapters within a module.
    """
    stmt = select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id)
    result = await db.execute(stmt)
    training = result.scalar_one_or_none()
    
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # BR-301/BR-302: editing only allowed in Draft state.
    if not await check_training_edit_permission(training, current_user, db):
        raise HTTPException(status_code=403, detail="Training must be in Draft state to edit content.")

    # Bulk update sequence orders
    for item in reorder_in.items:
        await db.execute(
            Chapter.__table__.update()
            .where(Chapter.id == item.id)
            .where(Chapter.module_id == module_id)
            .where(Chapter.training_id == training_id)
            .values(sequence_order=item.sequence_order)
        )

    await log_audit(db, tenant_id, current_user.id, "REORDER_CHAPTERS", "module", module_id, {"training_id": training_id})
    await db.commit()
    await invalidate_cache("training_structure", tenant_id)
    return {"status": "success"}

@router.post("/{training_id}/modules", response_model=ModuleSchema, status_code=status.HTTP_201_CREATED)
async def create_module(
    training_id: str,
    module_in: ModuleCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Create a module inside a training. Requires Training Creator role.
    """

    result = await db.execute(select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id))
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # BR-301/BR-302: editing only allowed in Draft state.
    if not await check_training_edit_permission(training, current_user, db):
        raise HTTPException(status_code=403, detail="Training must be in Draft state to edit content.")

    db_item = Module(
        id=str(uuid.uuid4()),
        training_id=training_id,
        tenant_id=tenant_id,
        title=module_in.title,
        sequence_order=module_in.sequence_order
    )
    db.add(db_item)
    await log_audit(db, tenant_id, current_user.id, "CREATE_MODULE", "module", db_item.id, {"training_id": training_id, "title": db_item.title})
    await db.commit()
    await db.refresh(db_item)
    
    # Invalidate structure for this training
    await invalidate_cache("training_structure", tenant_id)
    
    return db_item

@router.patch("/{training_id}/modules/{module_id}", response_model=ModuleSchema)
async def update_module(
    training_id: str,
    module_id: str,
    module_in: ModuleUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Update a module. Requires Training Creator role and training must be unpublished.
    """
    result = await db.execute(select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id))
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # BR-301/BR-302: editing only allowed in Draft state.
    if not await check_training_edit_permission(training, current_user, db):
        raise HTTPException(status_code=403, detail="Training must be in Draft state to edit content.")

    mod_result = await db.execute(select(Module).where(Module.id == module_id, Module.training_id == training_id))
    db_item = mod_result.scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="Module not found")

    update_data = module_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)

    db.add(db_item)
    await log_audit(db, tenant_id, current_user.id, "UPDATE_MODULE", "module", module_id, {"training_id": training_id, "changes": update_data})
    await db.commit()
    await db.refresh(db_item)
    
    await invalidate_cache("training_structure", tenant_id)
    return db_item

@router.delete("/{training_id}/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_module(
    training_id: str,
    module_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Delete a module. Requires Training Creator role and training must be unpublished.
    """
    result = await db.execute(select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id))
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # BR-301/BR-302: editing only allowed in Draft state.
    if not await check_training_edit_permission(training, current_user, db):
        raise HTTPException(status_code=403, detail="Training must be in Draft state to edit content.")

    mod_result = await db.execute(select(Module).where(Module.id == module_id, Module.training_id == training_id))
    db_item = mod_result.scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="Module not found")

    # Also delete associated chapters or let cascade handle it? 
    # Usually we should delete chapters associated with this module in this training.
    # The DB model might have cascade, but let's be explicit if needed or trust DB.
    
    await db.delete(db_item)
    await log_audit(db, tenant_id, current_user.id, "DELETE_MODULE", "module", module_id, {"training_id": training_id, "title": db_item.title})
    await db.commit()
    
    await invalidate_cache("training_structure", tenant_id)
    return None

@router.post("/{training_id}/chapters", response_model=ChapterSchema, status_code=status.HTTP_201_CREATED)
async def create_chapter(
    training_id: str,
    chapter_in: ChapterCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Create a chapter inside a training. Requires Training Creator role.
    """

    result = await db.execute(select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id))
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # BR-301/BR-302: editing only allowed in Draft state; check_training_edit_permission
    # returns False for is_ready, is_published, or is_archived, and for non-owners/non-collaborators.
    if not await check_training_edit_permission(training, current_user, db):
        raise HTTPException(status_code=403, detail="Training must be in Draft state to edit content.")

    if chapter_in.module_id:
        mod = await db.execute(select(Module).where(Module.id == chapter_in.module_id, Module.training_id == training_id))
        if not mod.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Module not found in this training")

    # Sequence_order is server-computed training-wide so that the previous-chapter
    # gating check in complete_chapter (which uses Chapter.sequence_order without
    # a module filter) stays deterministic. The client-supplied value is ignored.
    max_seq = await db.scalar(
        select(func.max(Chapter.sequence_order))
        .where(Chapter.training_id == training_id)
        .where(Chapter.deleted_at.is_(None))
    )
    next_seq = (max_seq or 0) + 1

    db_item = Chapter(
        id=str(uuid.uuid4()),
        training_id=training_id,
        tenant_id=tenant_id,
        module_id=chapter_in.module_id,
        title=chapter_in.title,
        content_type=chapter_in.content_type,
        content_data=chapter_in.content_data,
        sequence_order=next_seq,
    )
    db.add(db_item)
    await log_audit(db, tenant_id, current_user.id, "CREATE_CHAPTER", "chapter", db_item.id, {
        "training_id": training_id, 
        "module_id": chapter_in.module_id,
        "title": db_item.title,
        "type": db_item.content_type
    })
    await db.commit()
    await db.refresh(db_item)
    
    # Invalidate structure for this training
    await invalidate_cache("training_structure", tenant_id)
    
    return db_item

@router.patch("/{training_id}/chapters/{chapter_id}", response_model=ChapterSchema)
async def update_chapter(
    training_id: str,
    chapter_id: str,
    chapter_in: ChapterUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Update a chapter. Requires Training Creator role and training must be unpublished.
    """
    result = await db.execute(select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id))
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # BR-301/BR-302: editing only allowed in Draft state; check_training_edit_permission
    # returns False for is_ready, is_published, or is_archived, and for non-owners/non-collaborators.
    if not await check_training_edit_permission(training, current_user, db):
        raise HTTPException(status_code=403, detail="Training must be in Draft state to edit content.")

    chap_result = await db.execute(select(Chapter).where(Chapter.id == chapter_id, Chapter.training_id == training_id))
    db_item = chap_result.scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="Chapter not found")

    update_data = chapter_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)

    db.add(db_item)
    await log_audit(db, tenant_id, current_user.id, "UPDATE_CHAPTER", "chapter", chapter_id, {"training_id": training_id, "changes": update_data})
    await db.commit()
    await db.refresh(db_item)
    
    await invalidate_cache("training_structure", tenant_id)
    return db_item

@router.delete("/{training_id}/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chapter(
    training_id: str,
    chapter_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Delete a chapter. Requires Training Creator role and training must be unpublished.
    """
    result = await db.execute(select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id))
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # BR-301/BR-302: editing only allowed in Draft state; check_training_edit_permission
    # returns False for is_ready, is_published, or is_archived, and for non-owners/non-collaborators.
    if not await check_training_edit_permission(training, current_user, db):
        raise HTTPException(status_code=403, detail="Training must be in Draft state to edit content.")

    chap_result = await db.execute(select(Chapter).where(Chapter.id == chapter_id, Chapter.training_id == training_id))
    db_item = chap_result.scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="Chapter not found")

    await db.delete(db_item)
    await log_audit(db, tenant_id, current_user.id, "DELETE_CHAPTER", "chapter", chapter_id, {"training_id": training_id, "title": db_item.title})
    await db.commit()
    
    await invalidate_cache("training_structure", tenant_id)
    return None

@router.get("/{training_id}/chapters/{chapter_id}", response_model=ChapterSchema)
@cache_response("chapter_detail", expire=300)
async def get_chapter(
    training_id: str,
    chapter_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Get a specific chapter by ID.
    """
    stmt = (
        select(Chapter)
        .where(Chapter.id == chapter_id)
        .where(Chapter.training_id == training_id)
        .where(Chapter.tenant_id == tenant_id)
    )
    result = await db.execute(stmt)
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    # Enforce sequential gating for non-creators/managers
    is_privileged = any(role in ["Business Manager", "Training Creator", "Admin"] for role in current_user.roles)
    if not is_privileged:
        # Check if previous chapter is completed
        stmt_prev = (
            select(Chapter)
            .where(Chapter.training_id == training_id)
            .where(Chapter.sequence_order < chapter.sequence_order)
            .where(Chapter.tenant_id == tenant_id)
            .order_by(Chapter.sequence_order.desc())
            .limit(1)
        )
        prev_result = await db.execute(stmt_prev)
        prev_chapter = prev_result.scalar_one_or_none()
        
        if prev_chapter:
            stmt_prog = (
                select(UserProgress)
                .where(UserProgress.chapter_id == prev_chapter.id)
                .where(UserProgress.user_id == current_user.id)
                .where(UserProgress.tenant_id == tenant_id)
                .where(UserProgress.deleted_at.is_(None))
            )
            prog_result = await db.execute(stmt_prog)
            prev_progress = prog_result.scalar_one_or_none()
            if not prev_progress or prev_progress.status != ProgressStatus.COMPLETED:
                raise HTTPException(status_code=403, detail="Previous chapter must be completed first")

    return chapter

@router.post("/{training_id}/banner", response_model=schemas.training.Training)
async def upload_training_banner(
    training_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """Upload a custom banner image for a training. Requires Training Creator role."""
    is_authorized = any(role in ["Business Manager", "Training Creator", "Admin", "SysAdmin"] for role in current_user.roles)
    if not is_authorized:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    stmt = (
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id)
        .options(selectinload(Training.collaborators))
    )
    result = await db.execute(stmt)
    training = result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    if not await check_training_edit_permission(training, current_user, db):
        raise HTTPException(status_code=403, detail="Not enough permissions to edit this training")

    ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, WebP, or GIF images are accepted.")

    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    ext = ext_map.get(file.content_type, ".jpg")

    try:
        url = storage.save_banner_image(file, tenant_id, training_id, ext)
    except Exception as e:
        logger.error(f"Banner upload error for training {training_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save banner image: {e}")

    training.thumbnail = url
    await db.commit()

    await invalidate_cache("training_detail", tenant_id)
    await invalidate_cache("training_structure", tenant_id)
    await invalidate_cache("assigned_trainings", tenant_id)

    refreshed = await db.execute(
        select(Training)
        .where(Training.id == training_id, Training.tenant_id == tenant_id)
        .options(selectinload(Training.collaborators))
    )
    return refreshed.scalar_one()


@router.post("/{training_id}/chapters/{chapter_id}/upload", response_model=ChapterSchema)
async def upload_chapter_content(
    training_id: str,
    chapter_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Upload and process content for a chapter. Currently supports:
      - SCORM chapters: a .zip is extracted into the SCORM volume
      - PDF chapters:   a .pdf is stored under the images volume

    Requires Training Creator role and the training must be editable
    (draft, owner or collaborator).
    """

    # 1. Verify Chapter exists and belongs to the training
    stmt = (
        select(Chapter)
        .where(Chapter.id == chapter_id)
        .where(Chapter.training_id == training_id)
        .where(Chapter.tenant_id == tenant_id)
    )
    result = await db.execute(stmt)
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    # Check edit permission (owner or collaborator)
    stmt_t = select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id)
    res_t = await db.execute(stmt_t)
    training = res_t.scalar_one_or_none()
    if not training or not await check_training_edit_permission(training, current_user, db):
        raise HTTPException(status_code=403, detail="Not enough permissions to edit this training")

    chapter_type = str(chapter.content_type) if chapter.content_type else ""
    if chapter_type.endswith(".PDF") or chapter_type == "PDF":
        return await _handle_pdf_upload(
            db=db,
            file=file,
            chapter=chapter,
            tenant_id=tenant_id,
            training_id=training_id,
            current_user=current_user,
        )
    if not (chapter_type.endswith(".SCORM") or chapter_type == "SCORM"):
        raise HTTPException(
            status_code=400,
            detail="Only SCORM and PDF chapters accept file uploads on this endpoint.",
        )

    # MIME type check — reject anything that is clearly not a ZIP
    ALLOWED_SCORM_MIME_TYPES = {
        "application/zip",
        "application/x-zip-compressed",
        "application/octet-stream",  # some browsers send this for .zip
    }
    if file.content_type not in ALLOWED_SCORM_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type. Only ZIP files are accepted for SCORM packages.")

    # 2. Prepare storage path
    storage_path = storage.prepare_storage_path(tenant_id, training_id, chapter_id)
    zip_path = storage_path / f"content_{uuid.uuid4()}.zip"

    # 3. Save and extract
    try:
        storage.save_upload_file(file, zip_path)
        entry_point = storage.extract_scorm_package(zip_path, storage_path)
        
        if not entry_point:
            # Cleanup on failure
            if storage_path.exists():
                shutil.rmtree(storage_path)
            raise HTTPException(status_code=400, detail="Failed to find entry point in imsmanifest.xml")

        # 4. Update chapter content_data
        # Served by Nginx via /storage/scorm/ → /mnt/scorm/
        relative_base = f"{tenant_id}/{training_id}/{chapter_id}"
        chapter.content_data = {
            "index_url": f"/storage/scorm/{relative_base}/{entry_point}",
            "base_path": f"/storage/scorm/{relative_base}/",
            "original_filename": file.filename
        }
        
        await log_audit(db, tenant_id, current_user.id, "UPLOAD_SCORM", "chapter", chapter_id, {"training_id": training_id, "filename": file.filename})
        await db.commit()
        await db.refresh(chapter)
        
        # Cleanup ZIP after extraction
        if zip_path.exists():
            os.remove(zip_path)
            
        return chapter
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SCORM processing error for chapter {chapter_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process SCORM package. Please try again.")

@router.get("/{training_id}/structure", response_model=TrainingStructure)
@cache_response("training_structure", expire=300, include_user_id=True)
async def get_training_structure(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Get the full hierarchical structure of a training (Modules and Chapters).
    Calculates unlock status based on sequential progress rule:
    Chapter N is accessible only if Chapter N-1 is COMPLETED.
    """
    # 1. Fetch Training
    stmt = select(Training).where(
        Training.id == training_id, 
        Training.tenant_id == tenant_id,
        Training.deleted_at == None
    )
    result = await db.execute(stmt)
    training = result.scalar_one_or_none()
    
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # 2. Enforce Permissions
    # If not published, only Owner, Collaborator, or Admin can VIEW the structure.
    # Note: check_training_edit_permission enforces Draft-only WRITES; for VIEW access
    # we need a state-agnostic ownership/collaborator check.
    if not training.is_published:
        can_view = False
        if any(role in ["Business Manager", "Admin", "SysAdmin"] for role in current_user.roles):
            can_view = True
        elif training.created_by_id == current_user.id:
            can_view = True
        else:
            collab_stmt = select(TrainingCollaborator).where(
                TrainingCollaborator.training_id == training_id,
                TrainingCollaborator.user_id == current_user.id
            )
            collab_result = await db.execute(collab_stmt)
            if collab_result.scalar_one_or_none() is not None:
                can_view = True
        if not can_view:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access protected training structure"
            )
    
    # 3. Load full structure

    # 2. Fetch Modules
    modules = await db.execute(
        select(Module).where(Module.training_id == training_id).order_by(Module.sequence_order)
    )
    modules = modules.scalars().all()

    # 3. Fetch Chapters (live only — soft-deleted rows are excluded)
    chapters = await db.execute(
        select(Chapter)
        .where(Chapter.training_id == training_id)
        .where(Chapter.deleted_at.is_(None))
        .order_by(Chapter.sequence_order)
    )
    chapters = chapters.scalars().all()

    # 4. Fetch User Progress for this training (C-3 fix: exclude soft-deleted rows)
    progress = await db.execute(
        select(UserProgress).where(
            UserProgress.user_id == current_user.id,
            UserProgress.training_id == training_id,
            UserProgress.deleted_at.is_(None)
        )
    )
    progress_records = {p.chapter_id: p.status for p in progress.scalars().all()}

    # 4.5. Fetch Enrollment for overall status (filter soft-deleted rows)
    enroll_stmt = select(Enrollment).where(
        Enrollment.training_id == training_id,
        Enrollment.user_id == current_user.id,
        Enrollment.tenant_id == tenant_id,
        Enrollment.deleted_at.is_(None)
    )
    enroll_res = await db.execute(enroll_stmt)
    enroll = enroll_res.scalar_one_or_none()

    # 5. Apply Gating Logic & Build Response
    # In the frontend, the schema expects 'orphan_chapters' for chapters not in a module
    
    def transform_chapter(c):
        # ChapterSchema is ChapterSchema.model_validate(c)
        # But we need to add is_completed from progress_records
        from app.schemas.chapter import Chapter as ChapterSchema
        out = ChapterSchema.model_validate(c)
        out.is_completed = (progress_records.get(c.id) == ProgressStatus.COMPLETED)
        return out

    modules_out = []
    for m in modules:
        mod_chaps = [transform_chapter(c) for c in chapters if c.module_id == m.id]
        modules_out.append(ModuleWithChapters(
            id=m.id,
            training_id=m.training_id,
            title=m.title,
            sequence_order=m.sequence_order,
            chapters=mod_chaps
        ))
    
    standalone_chaps = [transform_chapter(c) for c in chapters if not c.module_id]

    # Build response dict from scalar columns so all Training fields (tags,
    # category, requires_certificate, template_id, is_ready, structure_type,
    # requires_recertification, etc.) are included automatically.
    # Relationship columns (collaborators, modules, chapters) are skipped here
    # because they are lazy-loaded; we supply them explicitly below.
    from sqlalchemy import inspect as sa_inspect
    mapper = sa_inspect(training.__class__)
    col_names = {col.key for col in mapper.column_attrs}
    training_dict = {k: getattr(training, k) for k in col_names}

    enrollment_status = (
        "completed" if (enroll and enroll.is_completed)
        else "in_progress" if enroll
        else "not_started"
    )
    training_dict.update({
        "modules": modules_out,
        "orphan_chapters": standalone_chaps,
        "total_chapters": len(chapters),
        "status": enrollment_status,
        "certificate_id": enroll.certificate_id if enroll else None,
        "collaborators": [],
    })
    return TrainingStructure.model_validate(training_dict)


@router.post("/{training_id}/chapters/{chapter_id}/complete")
async def complete_chapter(
    training_id: str,
    chapter_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Mark a chapter as completed.
    Enforces sequential progression: ensures the prior sequence chapter is COMPLETED.
    """
    
    # 1. Verify Chapter Belongs to Training/Tenant with row lock if modifying later
    chapter = await db.execute(
        select(Chapter)
        .where(Chapter.id == chapter_id, Chapter.training_id == training_id, Chapter.tenant_id == tenant_id)
    )
    chapter = chapter.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
        
    training = await db.execute(select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id))
    training = training.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")

    # 1.5. Expiry Check
    assignment_res = await db.execute(
        select(TrainingAssignment)
        .where(TrainingAssignment.training_id == training_id)
        .where(
            or_(
                TrainingAssignment.user_id == current_user.id,
                TrainingAssignment.group_id.in_(current_user.groups) if current_user.groups else False
            )
        )
        .order_by(TrainingAssignment.due_date.desc())
        .limit(1)
    )
    assignment = assignment_res.scalar_one_or_none()
    
    if assignment and assignment.due_date and assignment.due_date < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Training has expired and cannot be continued."
        )

    # 1.6. Progress Locking: Removed to allow review of completed content
    # (Individual chapter idempotency is handled below)

    # 2. Sequential Validation (Gating)
    if chapter.sequence_order > 1:
        # Look up the chapter immediately preceding this one in the training-wide
        # sequence. Soft-deleted rows are excluded so progress isn't gated on
        # a chapter the creator removed.
        prev_chapter = await db.execute(
            select(Chapter)
            .where(Chapter.training_id == training_id)
            .where(Chapter.deleted_at.is_(None))
            .where(Chapter.sequence_order < chapter.sequence_order)
            .order_by(Chapter.sequence_order.desc())
            .limit(1)
        )
        prev_chapter = prev_chapter.scalar_one_or_none()
        
        if prev_chapter:
            prev_prog = await db.execute(
                select(UserProgress).where(
                    UserProgress.user_id == current_user.id,
                    UserProgress.chapter_id == prev_chapter.id,
                    UserProgress.deleted_at.is_(None)
                )
            )
            prev_prog = prev_prog.scalar_one_or_none()

            if not prev_prog or prev_prog.status != ProgressStatus.COMPLETED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot complete chapter; previous chapter is not completed."
                )

    # 3. Mark Complete with lock on progress row (C-3 fix: exclude soft-deleted rows)
    prog = await db.execute(
        select(UserProgress)
        .where(
            UserProgress.user_id == current_user.id,
            UserProgress.chapter_id == chapter_id,
            UserProgress.deleted_at.is_(None)
        )
        .with_for_update()
    )
    prog = prog.scalar_one_or_none()

    if prog:
        if prog.status == ProgressStatus.COMPLETED:
            return {"status": "already_completed"}
        prog.status = ProgressStatus.COMPLETED
        prog.completed_at = datetime.now(timezone.utc)
    else:
        prog = UserProgress(
            tenant_id=tenant_id,
            user_id=current_user.id,
            training_id=training_id,
            chapter_id=chapter_id,
            status=ProgressStatus.COMPLETED,
            training_version_id=training.version,
            completed_at=datetime.now(timezone.utc)
        )
        db.add(prog)

    await db.commit()
    
    # Invalidate caches
    await invalidate_cache("user_stats", tenant_id, user_id=current_user.id)
    await invalidate_cache("training_detail", tenant_id)
    await invalidate_cache("training_structure", tenant_id)
    await invalidate_cache("assigned_trainings", tenant_id)

    # 4. Auto-Completion Trigger
    # If this was the last chapter, finalize training and issue certificate
    await _process_training_completion(training_id, db, current_user, tenant_id)
    
    return {"status": "success", "chapter_id": chapter_id}


ALLOWED_PDF_MIME_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/octet-stream",  # some clients send this for .pdf
}


async def _handle_pdf_upload(
    *,
    db: AsyncSession,
    file: UploadFile,
    chapter,
    tenant_id: str,
    training_id: str,
    current_user: deps.UserAuth,
):
    """Save an uploaded PDF and point the chapter's content_data.url at it.

    Mirrors the SCORM upload flow but stores into /mnt/images/pdfs/ and uses
    the /storage/pdfs/ nginx route. The viewer already renders PDFs from
    content_data.url via an iframe, so no viewer changes are required.
    """
    if file.content_type not in ALLOWED_PDF_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PDF files are accepted for PDF chapters.",
        )

    try:
        url = storage.save_pdf_file(file, tenant_id, training_id, chapter.id)
    except Exception as e:
        logger.error(f"PDF save error for chapter {chapter.id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save PDF: {e}")

    # Preserve any existing description the creator set on the chapter.
    existing = dict(chapter.content_data) if chapter.content_data else {}
    existing["url"] = url
    existing["original_filename"] = file.filename
    chapter.content_data = existing

    await log_audit(
        db, tenant_id, current_user.id, "UPLOAD_PDF", "chapter", chapter.id,
        {"training_id": training_id, "filename": file.filename},
    )
    await db.commit()
    await db.refresh(chapter)

    # Bust caches so the new URL surfaces immediately
    await invalidate_cache("training_structure", tenant_id)
    await invalidate_cache("training_detail", tenant_id)

    return chapter


async def _process_training_completion(
    training_id: str,
    db: AsyncSession,
    current_user: deps.UserAuth,
    tenant_id: str
):
    """Internal helper to finalize training and issue certificate if all chapters completed."""
    import uuid
    # 1. Fetch Training
    training_res = await db.execute(select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id))
    training = training_res.scalar_one_or_none()
    if not training:
        return None

    # 2. Check all chapters completed
    chapter_count_res = await db.execute(select(func.count(Chapter.id)).where(Chapter.training_id == training_id))
    chapter_count = chapter_count_res.scalar()

    completed_count_res = await db.execute(
        select(func.count(UserProgress.id))
        .where(UserProgress.training_id == training_id)
        .where(UserProgress.user_id == current_user.id)
        .where(UserProgress.status == ProgressStatus.COMPLETED)
        .where(UserProgress.deleted_at.is_(None))
    )
    completed_count = completed_count_res.scalar()

    if completed_count < chapter_count:
        return {"status": "in_progress", "completed": completed_count, "total": chapter_count}

    # 3. Check/Update Enrollment (C-1 fix: filter deleted rows; reset rows have is_completed=False
    # so they will NOT short-circuit here even if re-encountered after a pushback reset).
    existing_res = await db.execute(
        select(Enrollment)
        .where(Enrollment.training_id == training_id)
        .where(Enrollment.user_id == current_user.id)
        .where(Enrollment.deleted_at.is_(None))
    )
    existing = existing_res.scalar_one_or_none()

    if existing and existing.is_completed:
        return {"status": "already_completed", "certificate_id": existing.certificate_id}

    if not existing:
        existing = Enrollment(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=current_user.id,
            training_id=training_id,
            enrolled_at=datetime.now(timezone.utc)
        )
        db.add(existing)

    existing.is_completed = True
    existing.completed_at = datetime.now(timezone.utc)
    existing.training_version_id = training.version
    
    # 4. Issue Certificate if required
    if training.requires_certificate:
        # Use template assigned to training, fallback to tenant-wide active template
        template = None
        if training.template_id:
            tpl_res = await db.execute(select(CertificateTemplate).where(CertificateTemplate.id == training.template_id))
            template = tpl_res.scalar_one_or_none()
            
        if not template:
            # Fallback to any active template for tenant
            tpl_res = await db.execute(select(CertificateTemplate).where(
                CertificateTemplate.tenant_id == tenant_id,
                CertificateTemplate.is_active == True
            ).limit(1))
            template = tpl_res.scalar_one_or_none()
        
        if template:
            cert_id = str(uuid.uuid4())
            cert_no = f"CERT-{uuid.uuid4().hex[:8].upper()}"
            
            # Fetch tenant branding for certificate variables
            from app.api.deps import get_tenant_branding
            tenant_branding = await get_tenant_branding(tenant_id)

            first_name = ""
            last_name = ""
            if current_user.full_name:
                parts = current_user.full_name.split(" ", 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ""

            cert_data = {
                "learner_name": current_user.full_name or current_user.email,
                "training_title": training.title,
                "completion_date": datetime.now(timezone.utc).date().isoformat(),
                "certificate_number": cert_no,
                "tenant_name": tenant_branding.get("name", ""),
                "tenant_logo": tenant_branding.get("logo_url", "") or "",
                "tenant_primary_color": tenant_branding.get("primary_color", "") or "",
            }
            
            new_cert = Certificate(
                id=cert_id,
                user_id=current_user.id,
                training_id=training.id,
                template_id=template.id,
                certificate_number=cert_no,
                issued_at=datetime.now(timezone.utc),
                data=cert_data,
                tenant_id=tenant_id
            )
            db.add(new_cert)
            existing.certificate_id = cert_id
            existing.certificate_url = f"/api/certificates/{cert_id}/view"
    
    await db.commit()
    
    # 5. Invalidate Caches
    await invalidate_cache("user_stats", tenant_id, user_id=current_user.id)
    await invalidate_cache("training_detail", tenant_id)
    await invalidate_cache("training_structure", tenant_id)
    await invalidate_cache("assigned_trainings", tenant_id)
    
    # 6. Publish Event
    from app.core.events import publisher
    await publisher.publish_event(
        "TRAINING_COMPLETED",
        {
            "tenant_id": tenant_id,
            "user_id": current_user.id,
            "training_id": training_id,
            "training_title": training.title,
            "completed_at": existing.completed_at.isoformat(),
            "certificate_id": str(existing.certificate_id) if existing.certificate_id else None
        }
    )

    return {
        "status": "completed",
        "certificate_id": existing.certificate_id,
        "requires_certificate": training.requires_certificate
    }

@router.post("/{training_id}/complete-training")
async def complete_training(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Verify all chapters are completed and issue an Enrollment/Certificate.
    """
    # 0.5. Expiry Check
    assignment_res = await db.execute(
        select(TrainingAssignment)
        .where(TrainingAssignment.training_id == training_id)
        .where(
            or_(
                TrainingAssignment.user_id == current_user.id,
                TrainingAssignment.group_id.in_(current_user.groups) if current_user.groups else False
            )
        )
        .order_by(TrainingAssignment.due_date.desc())
        .limit(1)
    )
    assignment = assignment_res.scalar_one_or_none()
    if assignment and assignment.due_date and assignment.due_date < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Training has expired and cannot be completed."
        )

    result = await _process_training_completion(training_id, db, current_user, tenant_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Training not found")
    
    if result["status"] == "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Cannot complete training: {result['completed']}/{result['total']} chapters completed."
        )
        
    return result

@router.post("/{training_id}/chapters/{chapter_id}/submit-quiz", response_model=schemas.QuizResult)
async def submit_quiz(
    training_id: str,
    chapter_id: str,
    submission: schemas.QuizSubmission,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Grade a quiz submission, track attempts, and update progress.
    """
    chapter = await db.execute(
        select(Chapter).where(
            Chapter.id == chapter_id,
            Chapter.training_id == training_id,
            Chapter.tenant_id == tenant_id,
            Chapter.content_type == ContentType.QUIZ
        )
    )
    chapter = chapter.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Quiz chapter not found")

    content = chapter.content_data
    questions = content.get("questions", [])
    passing_score = content.get("passing_score", 80)
    max_attempts = content.get("max_attempts", 10)

    attempts_stmt = await db.execute(
        select(QuizAttempt)
        .where(
            QuizAttempt.user_id == current_user.id,
            QuizAttempt.chapter_id == chapter_id,
            QuizAttempt.deleted_at.is_(None),
        )
        .order_by(QuizAttempt.attempt_number.desc())
    )
    last_attempt = attempts_stmt.scalars().first()
    
    current_attempt_number = (last_attempt.attempt_number + 1) if last_attempt else 1
    
    if last_attempt and last_attempt.passed:
        return schemas.QuizResult(
            score=last_attempt.score,
            passed=True,
            attempt_number=last_attempt.attempt_number,
            max_attempts=max_attempts,
            is_locked=False
        )
        
    if max_attempts > 0 and current_attempt_number > max_attempts:
        # Publish QUIZ_LOCKOUT event to the manager (creator of course) or user directly
        from app.core.events import publisher
        # Note: We notify the user for simplicity, but the payload says "Usually manager ID to notify".
        # Let's notify the course creator.
        training_stmt = await db.execute(select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id))
        training = training_stmt.scalar_one_or_none()
        manager_id = training.created_by_id if training else current_user.id
        
        await publisher.publish_event(
            "QUIZ_LOCKOUT",
            {
                "tenant_id": tenant_id,
                "user_id": manager_id,
                "student_email": current_user.email,
                "training_id": training_id,
                "training_title": training.title if training else "Unknown",
            }
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maximum quiz attempts reached. Access locked."
        )

    # 1.6. Progress Locking: Removed to allow review of completed content

    correct_count = 0
    total_questions = len(questions)
    correct_answers_map = {}

    answers_map = {a.question_id: a for a in submission.answers}
    for question in questions:
        q_type = question.get("type", "multiple_choice")
        user_answer = answers_map.get(question["id"])

        # Handle both legacy single ID and new plural IDs
        correct_ids = question.get("correct_option_ids", [])
        if not correct_ids and "correct_option_id" in question:
            correct_ids = [question["correct_option_id"]]

        if user_answer is None:
            is_correct = False
        elif q_type in ("multiple_choice", "multiple_select", "true_false"):
            is_correct = sorted(user_answer.selected_option_ids) == sorted(correct_ids)
        elif q_type == "ordering":
            is_correct = user_answer.ordered_ids == correct_ids
        elif q_type == "matching":
            correct_pairs = set(tuple(sorted(p.items())) for p in question.get("correct_pairs", []))
            user_pairs = set(tuple(sorted(p.items())) for p in (user_answer.pairs or []))
            is_correct = user_pairs == correct_pairs
        else:
            is_correct = False

        if is_correct:
            correct_count += 1

        correct_answers_map[question["id"]] = correct_ids

    score = (correct_count / total_questions * 100) if total_questions > 0 else 0
    passed = score >= passing_score

    new_attempt = QuizAttempt(
        tenant_id=tenant_id,
        user_id=current_user.id,
        chapter_id=chapter_id,
        attempt_number=current_attempt_number,
        score=score,
        passed=passed,
        answers={a.question_id: a.selected_option_ids for a in submission.answers}
    )
    db.add(new_attempt)

    audit = AuditLog(
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="SUBMIT_QUIZ",
        entity_type="chapter",
        entity_id=chapter_id,
        metadata_json={
            "training_id": training_id,
            "score": score,
            "passed": passed,
            "attempt": current_attempt_number
        }
    )
    db.add(audit)

    if passed:
        prog = await db.execute(
            select(UserProgress)
            .where(UserProgress.user_id == current_user.id, UserProgress.chapter_id == chapter_id)
            .where(UserProgress.deleted_at.is_(None))
        )
        prog = prog.scalar_one_or_none()

        if prog:
            prog.status = ProgressStatus.COMPLETED
            prog.completed_at = datetime.now(timezone.utc)
        else:
            training = await db.execute(select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id))
            training = training.scalar_one_or_none()
            prog = UserProgress(
                tenant_id=tenant_id,
                user_id=current_user.id,
                training_id=training_id,
                chapter_id=chapter_id,
                status=ProgressStatus.COMPLETED,
                training_version_id=training.version if training else 1,
                completed_at=datetime.now(timezone.utc)
            )
            db.add(prog)

    await db.commit()
    
    # Invalidate user stats, detail, structure and assignments
    await invalidate_cache("user_stats", tenant_id, user_id=current_user.id)
    await invalidate_cache("training_detail", tenant_id)
    await invalidate_cache("training_structure", tenant_id)
    await invalidate_cache("assigned_trainings", tenant_id)
    
    # 4. Auto-Completion Trigger
    if passed:
        await _process_training_completion(training_id, db, current_user, tenant_id)

    return schemas.QuizResult(
        score=score,
        passed=passed,
        attempt_number=current_attempt_number,
        max_attempts=max_attempts,
        is_locked=current_attempt_number >= max_attempts and not passed,
        correct_answers=correct_answers_map if (passed or current_attempt_number >= max_attempts) else None
    )


@router.post("/{training_id}/chapters/{chapter_id}/quiz/reset/{user_id}")
async def reset_quiz_lockout(
    training_id: str,
    chapter_id: str,
    user_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Reset a learner's quiz lockout by soft-deleting all their quiz attempts for
    a given chapter. Only Business Managers and SysAdmins may call this endpoint.
    """
    is_authorized = any(role in ["Business Manager", "SysAdmin"] for role in current_user.roles)
    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Business Manager permissions required."
        )

    # 1. Verify training belongs to this tenant
    training_result = await db.execute(
        select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id)
    )
    training = training_result.scalar_one_or_none()
    if not training:
        raise HTTPException(status_code=404, detail="Training not found.")

    # 2. Soft-delete all quiz attempts for the target user + chapter + tenant
    attempts_result = await db.execute(
        select(QuizAttempt).where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.chapter_id == chapter_id,
            QuizAttempt.tenant_id == tenant_id,
            QuizAttempt.deleted_at.is_(None),
        )
    )
    attempts = attempts_result.scalars().all()
    now = datetime.now(timezone.utc)
    for attempt in attempts:
        attempt.deleted_at = now

    # 3. Audit log
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="quiz_reset",
        entity_type="Chapter",
        entity_id=chapter_id,
        metadata_json={"target_user_id": user_id, "training_id": training_id},
    ))
    await db.commit()
    return {"message": "Quiz lockout reset."}


@router.get("/{training_id}/export-scorm")
async def export_training_scorm(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Export a training as a SCORM 1.2 ZIP package.
    Requires Training Creator or Admin role.
    """
    from fastapi.responses import StreamingResponse
    import io
    import json as stdlib_json

    is_authorized = any(role in ["Training Creator", "Admin"] for role in current_user.roles)
    if not is_authorized:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    structure = await get_training_structure(training_id, db, current_user, tenant_id)

    # Gather all chapters in order
    all_chapters = []
    for mod in structure.modules:
        for ch in mod.chapters:
            all_chapters.append((mod.title, ch))
    for ch in structure.orphan_chapters:
        all_chapters.append((None, ch))

    # Sort by sequence_order
    all_chapters.sort(key=lambda x: x[1].sequence_order)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:

        # Build imsmanifest.xml
        items_xml = ""
        resources_xml = ""
        for idx, (mod_title, ch) in enumerate(all_chapters):
            item_id = f"item_{idx}"
            res_id = f"res_{idx}"
            ch_file = f"chapter_{idx}.html"
            items_xml += f'<item identifier="{item_id}" identifierref="{res_id}"><title>{ch.title}</title></item>\n'
            resources_xml += f'<resource identifier="{res_id}" type="webcontent" adlcp:scormtype="sco" href="{ch_file}"><file href="{ch_file}"/></resource>\n'

        manifest = f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="com.lms.{training_id}" version="1.2"
  xmlns="http://www.imsglobal.org/xsd/imscp_v1p1"
  xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>
  <organizations default="org1">
    <organization identifier="org1">
      <title>{structure.title}</title>
      {items_xml}
    </organization>
  </organizations>
  <resources>
    {resources_xml}
  </resources>
</manifest>"""
        zf.writestr("imsmanifest.xml", manifest)

        # Build a chapter HTML for each
        for idx, (mod_title, ch) in enumerate(all_chapters):
            ch_file = f"chapter_{idx}.html"
            if ch.content_type == "RICH_TEXT":
                body = ch.content_data.get("text", "") if isinstance(ch.content_data, dict) else str(ch.content_data or "")
            elif ch.content_type == "VIDEO":
                url = ch.content_data.get("url", "") if isinstance(ch.content_data, dict) else ""
                body = f'<video controls style="width:100%;max-width:800px"><source src="{url}"></video>'
            elif ch.content_type == "QUIZ":
                questions = ch.content_data.get("questions", []) if isinstance(ch.content_data, dict) else []
                body = f"<h2>Quiz</h2><p>This training contains {len(questions)} quiz question(s). Please access the LMS to take the quiz.</p>"
            else:
                body = "<p>Content not available for export.</p>"

            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{ch.title}</title>
  <style>body{{font-family:sans-serif;max-width:900px;margin:40px auto;padding:0 20px;line-height:1.6}}</style>
</head>
<body>
  <h1>{ch.title}</h1>
  {body}
  <script>
    // Minimal SCORM 1.2 API stub - marks SCO as completed on load
    window.onload = function() {{
      if (window.parent && window.parent.API) {{
        try {{
          window.parent.API.LMSInitialize("");
          window.parent.API.LMSSetValue("cmi.core.lesson_status","completed");
          window.parent.API.LMSFinish("");
        }} catch(e) {{}}
      }}
    }};
  </script>
</body>
</html>"""
            zf.writestr(ch_file, html)

        # Top-level index
        toc_items = "".join(f'<li><a href="chapter_{i}.html" target="content">{ch.title}</a></li>' for i, (_, ch) in enumerate(all_chapters))
        index_html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{structure.title}</title>
<style>body{{font-family:sans-serif;margin:0}}frameset{{border:0}}</style>
</head>
<frameset cols="250,*">
  <frame src="toc.html" name="toc">
  <frame src="chapter_0.html" name="content">
</frameset>
</html>"""
        zf.writestr("index.html", index_html)

        toc_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>body{{font-family:sans-serif;padding:16px}}ul{{list-style:none;padding:0}}li{{margin:8px 0}}a{{text-decoration:none;color:#0066cc}}</style></head>
<body><h3>{structure.title}</h3><ul>{toc_items}</ul></body></html>"""
        zf.writestr("toc.html", toc_html)

    buf.seek(0)
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in structure.title)
    filename = f"{safe_title}_scorm.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.post("/{training_id}/unpublish", response_model=TrainingSchema)
async def unpublish_training(
    training_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_training_creator),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Unpublish a training to make it editable again.
    Only the initial creator can unpublish.
    """
    stmt = select(Training).where(Training.id == training_id, Training.tenant_id == tenant_id).options(selectinload(Training.collaborators))
    result = await db.execute(stmt)
    training = result.scalar_one_or_none()
    
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
        
    if training.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the initial creator can unpublish the training")

    training.is_published = False
    # When unpublishing, we keep it active if it was already, but usually it means taking it off market
    # Actually, the user wants "unpublished then edit option is enabled". 
    # Let's keep is_active as True so managers can still PREVIEW it, but it won't be in the learner "Published" list.
    # Wait, the learner list filters by is_published or is_active?
    # Trainings endpoint /trainings/ filters by is_published=True (usually).
    
    await db.commit()
    await db.refresh(training)
    
    # Invalidate caches
    await invalidate_cache("training_detail", tenant_id)
    await invalidate_cache("training_structure", tenant_id)
    await invalidate_cache("assigned_trainings", tenant_id)
    
    return training

@router.get("/internal/metrics", response_model=GlobalMetrics)
async def get_internal_metrics(
    db: AsyncSession = Depends(deps.get_db),
    _ = Depends(deps.validate_internal_api)
):
    """
    Internal endpoint for auth-service to fetch global training metrics.
    """
    # 1. Total Trainings (exclude soft-deleted)
    total_trainings = await db.scalar(
        select(func.count(Training.id)).where(Training.deleted_at == None)
    )
    
    # 2. Total Certificates (Completed Enrollments)
    total_certificates = await db.scalar(
        select(func.count(Enrollment.id)).where(Enrollment.is_completed == True)
    )
    
    # 3. Tenant breakdown
    # Trainings per tenant
    t_stmt = (
        select(Training.tenant_id, func.count(Training.id))
        .where(Training.deleted_at == None)
        .group_by(Training.tenant_id)
    )
    t_result = await db.execute(t_stmt)
    t_counts = {row[0]: row[1] for row in t_result.all()}
    
    # Certificates per tenant
    c_stmt = (
        select(Enrollment.tenant_id, func.count(Enrollment.id))
        .where(Enrollment.is_completed == True)
        .group_by(Enrollment.tenant_id)
    )
    c_result = await db.execute(c_stmt)
    c_counts = {row[0]: row[1] for row in c_result.all()}
    
    # Combine
    tenant_ids = set(t_counts.keys()) | set(c_counts.keys())
    breakdown = {}
    for tid in tenant_ids:
        breakdown[tid] = TenantMetric(
            training_count=t_counts.get(tid, 0),
            certificate_count=c_counts.get(tid, 0)
        )
        
    return GlobalMetrics(
        total_trainings=total_trainings or 0,
        total_certificates=total_certificates or 0,
        tenant_breakdown=breakdown
    )
