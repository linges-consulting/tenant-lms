from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Optional
from datetime import datetime

class QuizAnswer(BaseModel):
    question_id: str
    selected_option_ids: List[str] = []
    ordered_ids: Optional[List[str]] = None      # for ordering questions
    pairs: Optional[List[Dict[str, str]]] = None  # for matching questions

class QuizSubmission(BaseModel):
    answers: List[QuizAnswer]

class QuizResult(BaseModel):
    score: int
    passed: bool
    attempt_number: int
    max_attempts: int
    is_locked: bool
    correct_answers: Optional[Dict[str, List[str]]] = None # question_id -> correct_option_ids (returned on success/completion)

class QuizAttemptBase(BaseModel):
    score: int
    passed: bool
    attempt_number: int

class QuizAttempt(QuizAttemptBase):
    id: str
    user_id: str
    chapter_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AuditLogCreate(BaseModel):
    action: str
    entity_type: str
    entity_id: str
    metadata_json: Optional[dict] = None

class AuditLog(AuditLogCreate):
    id: str
    tenant_id: str
    user_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
