from pydantic import BaseModel
from typing import List

class ReorderItem(BaseModel):
    id: str
    sequence_order: int

class BulkReorder(BaseModel):
    items: List[ReorderItem]
