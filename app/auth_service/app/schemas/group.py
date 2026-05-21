from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class GroupMemberOut(BaseModel):
    user_id: str
    added_at: datetime
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    user_avatar_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class GroupOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    member_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class AddGroupMembersPayload(BaseModel):
    user_ids: List[str]


class AssignmentOut(BaseModel):
    id: str
    training_id: str
    tenant_id: str
    group_id: Optional[str] = None
    user_id: Optional[str] = None
    assigned_at: datetime
    group_name: Optional[str] = None
    user_name: Optional[str] = None
    training_title: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class AssignmentCreate(BaseModel):
    training_id: str
    group_id: Optional[str] = None
    user_id: Optional[str] = None
