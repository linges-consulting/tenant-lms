from pydantic import BaseModel
from typing import Dict

class TenantMetric(BaseModel):
    training_count: int
    certificate_count: int

class GlobalMetrics(BaseModel):
    total_trainings: int
    total_certificates: int
    # Map of tenant_id -> counts
    tenant_breakdown: Dict[str, TenantMetric]
