"""
AutoCura - Alert Pydantic Schemas
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_type: str
    severity: str
    message: str
    source: str
    timestamp: datetime
    acknowledged: bool
