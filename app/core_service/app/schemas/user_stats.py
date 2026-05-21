from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

class UserStats(BaseModel):
    completed_courses: int
    in_progress_courses: int
    total_enrollments: int
    certificates_earned: int

class UserCertificate(BaseModel):
    id: str
    training_id: str
    training_title: str
    completed_at: datetime
    certificate_url: Optional[str] = None
    certificate_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
