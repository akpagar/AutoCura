"""
AutoCura - Dashboard Pydantic Schema
"""

from datetime import datetime

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    system_health: str
    current_cpu: float
    current_memory: float
    current_disk: float
    service_status: str
    active_failures: int
    recovery_success_rate: float | None
    average_recovery_time_seconds: float | None
    last_metric_timestamp: datetime | None
