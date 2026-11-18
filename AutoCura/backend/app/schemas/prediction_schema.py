"""
AutoCura - Prediction Pydantic Schemas
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PredictionRequest(BaseModel):
    """Optional manual override input; if omitted, the current live metrics are used."""
    cpu_usage: float | None = None
    memory_usage: float | None = None
    disk_usage: float | None = None
    network_in: float | None = None
    network_out: float | None = None
    latency: float | None = None
    error_rate: float | None = None
    service_status: str | None = None
    process_count: int | None = None
    restart_count: int | None = None


class AnomalyInfo(BaseModel):
    is_anomaly: bool
    threshold_reasons: list[str] = Field(default_factory=list)
    isolation_forest_flagged: bool | None = None


class PredictionResult(BaseModel):
    failure_type: str
    failure_probability: float
    confidence: float
    severity: str
    anomaly: AnomalyInfo


class PredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    metric_id: int | None
    predicted_failure_type: str
    failure_probability: float
    confidence: float
    severity: str
    timestamp: datetime
