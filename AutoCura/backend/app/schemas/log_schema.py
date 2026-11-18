"""
AutoCura - Log Pydantic Schemas
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    source: str
    level: str
    message: str
    service_name: str
