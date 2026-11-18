"""
AutoCura - Failure Pydantic Schema
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FailureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    failure_type: str
    severity: str
    detected_at: datetime
    predicted: bool
    status: str
