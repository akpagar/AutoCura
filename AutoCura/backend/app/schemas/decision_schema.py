"""
AutoCura - Decision Pydantic Schemas
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DecisionResult(BaseModel):
    failure_type: str
    severity: str
    recommended_action: str
    reason: str
    confidence: float


class DecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    failure_type: str
    severity: str
    recommended_action: str
    reason: str
    confidence: float
    timestamp: datetime
