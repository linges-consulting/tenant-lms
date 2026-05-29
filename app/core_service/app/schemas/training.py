from datetime import datetime
from pydantic import BaseModel, ConfigDict, computed_field, model_validator, field_validator
from typing import Optional, List, Any
from app.schemas.module import ModuleWithChapters
from app.schemas.chapter import Chapter

# Shared properties
class TrainingBase(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    duration: Optional[str] = None
    thumbnail: Optional[str] = None
    version: Optional[int] = 1
    is_published: Optional[bool] = False
    requires_certificate: Optional[bool] = True
    template_id: Optional[str] = None
    is_archived: Optional[bool] = False
    is_active: Optional[bool] = True
    is_ready: Optional[bool] = False
    content_expires_at: Optional[datetime] = None

class TrainingCollaboratorBase(BaseModel):
    user_id: str

class TrainingCollaboratorCreate(TrainingCollaboratorBase):
    pass

class TrainingCollaborator(TrainingCollaboratorBase):
    model_config = ConfigDict(from_attributes=True)

# Properties to receive on item creation
class TrainingCreate(TrainingBase):
    title: str
    category: str  # required — no default
    structure_type: str = "flat"
    tags: List[str] = []
    requires_recertification: bool = False
    recertification_period_days: Optional[int] = None

# Properties to receive on item update
class TrainingUpdate(TrainingBase):
    structure_type: Optional[str] = None
    tags: Optional[List[str]] = None
    requires_recertification: Optional[bool] = None
    recertification_period_days: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def category_must_not_be_null_if_provided(cls, values):
        """Reject explicit null for category to avoid DB integrity error."""
        if "category" in values and values["category"] is None:
            raise ValueError("category cannot be null")
        return values

# Properties shared by models stored in DB
class TrainingInDBBase(TrainingBase):
    id: str
    structure_type: str = "flat"
    tags: List[str] = []
    requires_recertification: bool = False
    recertification_period_days: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

    @field_validator('tags', mode='before')
    @classmethod
    def coerce_tags(cls, v: Any) -> List[str]:
        # Defensive: legacy / mis-seeded rows occasionally store the JSON column
        # as `{}` (empty dict) instead of `[]`. Treat it as no tags rather than
        # blowing up serialization of the whole training.
        if v is None:
            return []
        if isinstance(v, dict):
            return []
        return v

# Properties to return to client
class Training(TrainingInDBBase):
    created_by_id: Optional[str] = None
    creator_name: Optional[str] = None
    collaborators: List[TrainingCollaborator] = []

    # Progress fields (Calculated for learners)
    progress_percentage: float = 0.0
    completed_chapters: int = 0
    total_chapters: int = 0
    status: str = "not_started"  # not_started, in_progress, completed, expired
    certificate_id: Optional[str] = None
    completed_at: Optional[Any] = None
    due_date: Optional[datetime] = None  # per-user assignment due_date (manager-set)

    @computed_field
    @property
    def lifecycle_status(self) -> str:
        if self.is_archived:
            return "archived"
        elif self.is_published:
            return "published"
        elif self.is_ready:
            return "ready"
        return "draft"

# Structure return payload
class TrainingStructure(Training):
    modules: List[ModuleWithChapters] = []
    # Standalone chapters not in a module
    orphan_chapters: List[Chapter] = []

class TrainingHistorySnapshot(BaseModel):
    id: str
    tenant_id: str
    training_id: str
    version: int
    snapshot: dict
    created_at: Any

    model_config = ConfigDict(from_attributes=True)

class TrainingAuditLog(BaseModel):
    id: str
    user_id: str
    action: str
    entity_type: str
    entity_id: str
    metadata_json: Optional[dict] = None
    created_at: Any
    user_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
