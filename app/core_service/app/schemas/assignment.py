from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class TrainingAssignmentBase(BaseModel):
    training_id: str
    user_id: Optional[str] = None
    group_id: Optional[str] = None
    due_date: Optional[datetime] = None

class TrainingAssignmentCreate(TrainingAssignmentBase):
    pass

class TrainingAssignmentUpdate(BaseModel):
    due_date: Optional[datetime] = None

class TrainingAssignment(TrainingAssignmentBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    tenant_id: str
    assigned_at: datetime
    user_name: Optional[str] = None
    group_name: Optional[str] = None

class BulkAssignmentCreate(BaseModel):
    user_ids: List[str] = []
    group_ids: List[str] = []
    due_date: Optional[datetime] = None
