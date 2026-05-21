from pydantic import BaseModel, ConfigDict
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

# Properties to receive on item creation
class TrainingCreate(TrainingBase):
    title: str

# Properties to receive on item update
class TrainingUpdate(TrainingBase):
    pass

# Properties shared by models stored in DB
class TrainingInDBBase(TrainingBase):
    id: str
    model_config = ConfigDict(from_attributes=True)

# Properties to return to client
class Training(TrainingInDBBase):
    created_by_id: Optional[str] = None
    creator_name: Optional[str] = None

# Structure return payload
class TrainingStructure(Training):
    modules: List[ModuleWithChapters] = []
    # Standalone chapters not in a module
    chapters: List[Chapter] = []

class TrainingHistorySnapshot(BaseModel):
    id: str
    tenant_id: str
    training_id: str
    version: int
    snapshot: dict
    created_at: Any

    model_config = ConfigDict(from_attributes=True)
