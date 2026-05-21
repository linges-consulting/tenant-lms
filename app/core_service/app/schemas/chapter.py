from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from app.models.chapter import ContentType

# Shared properties
class ChapterBase(BaseModel):
    title: Optional[str] = None
    content_type: Optional[ContentType] = None
    content_data: Optional[dict] = None
    sequence_order: Optional[int] = None
    module_id: Optional[str] = None
    completion_mode: Optional[str] = "can_continue"

# Properties to receive on item creation
class ChapterCreate(ChapterBase):
    title: str
    content_type: ContentType
    content_data: dict
    sequence_order: int

# Properties to receive on item update
class ChapterUpdate(ChapterBase):
    pass

# Properties shared by models stored in DB
class ChapterInDBBase(ChapterBase):
    id: str
    training_id: str
    
    # We never want to leak tenant_id in normal responses
    model_config = ConfigDict(from_attributes=True)

# Properties to return to client
class Chapter(ChapterInDBBase):
    is_completed: bool = False
