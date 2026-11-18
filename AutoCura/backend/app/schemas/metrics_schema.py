"""
AutoCura - Metrics Pydantic Schemas
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MetricCreate(BaseModel):
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_in: float = 0.0
    network_out: float = 0.0
    latency: float = 0.0
    error_rate: float = 0.0
    service_status: str = "running"
    hostname: str = "localhost"


class MetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_in: float
    network_out: float
    latency: float
    error_rate: float
    service_status: str
    hostname: str
