from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional
from app.models.progress import ProgressStatus

# Shared
class UserProgressBase(BaseModel):
    status: Optional[ProgressStatus] = None

# Create
class UserProgressCreate(BaseModel):
    chapter_id: str
    training_id: str
    training_version_id: int
    status: ProgressStatus = ProgressStatus.IN_PROGRESS

# Update
class UserProgressUpdate(UserProgressBase):
    completed_at: Optional[datetime] = None

# In DB
class UserProgressInDBBase(UserProgressBase):
    id: str
    user_id: str
    chapter_id: str
    training_id: str
    training_version_id: int
    completed_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

# Public
class UserProgress(UserProgressInDBBase):
    pass
