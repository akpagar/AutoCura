"""
AutoCura - Recovery Pydantic Schemas
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RecoveryExecuteRequest(BaseModel):
    """Optional explicit override; if omitted, the full decision chain runs first."""
    action: str | None = None
    failure_type: str | None = None


class RecoveryResult(BaseModel):
    success: bool
    recovery_time_seconds: float
    action: str
    failure_type: str
    before: dict
    after: dict
    execution_detail: dict


class RecoveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    failure_id: int | None
    action: str
    started_at: datetime
    completed_at: datetime | None
    status: str
    result: str
    recovery_time: float
