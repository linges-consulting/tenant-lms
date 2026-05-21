from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from app.schemas.chapter import Chapter

# Shared properties
class ModuleBase(BaseModel):
    title: Optional[str] = None
    sequence_order: Optional[int] = None

# Properties to receive on item creation
class ModuleCreate(ModuleBase):
    title: str
    sequence_order: int

# Properties to receive on item update
class ModuleUpdate(ModuleBase):
    pass

# Properties shared by models stored in DB
class ModuleInDBBase(ModuleBase):
    id: str
    training_id: str
    model_config = ConfigDict(from_attributes=True)

# Properties to return to client
class Module(ModuleInDBBase):
    pass

# Special schema for structural return
class ModuleWithChapters(Module):
    chapters: List[Chapter] = []
