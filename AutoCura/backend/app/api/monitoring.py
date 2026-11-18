"""
AutoCura - Monitoring API

GET  /api/monitoring/current  - one fresh sample, not persisted
GET  /api/monitoring/history  - persisted samples from the metrics table
GET  /api/monitoring/health   - monitoring subsystem liveness + scheduler state
POST /api/monitoring/start    - start the background collection loop
POST /api/monitoring/stop     - stop the background collection loop
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.metrics_schema import MetricResponse
from app.services.monitoring_service import MonitoringService, monitoring_scheduler

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


@router.get("/current")
def get_current_metrics() -> dict:
    """Returns a live sample straight from the collectors (no DB write)."""
    return MonitoringService.collect_current_metrics()


@router.get("/history", response_model=list[MetricResponse])
def get_metrics_history(limit: int = 50, db: Session = Depends(get_db)) -> list:
    return MonitoringService.get_history(db, limit=limit)


@router.get("/health")
def monitoring_health() -> dict:
    """Liveness check for the monitoring subsystem, including scheduler state."""
    return {
        "status": "ok",
        "module": "monitoring",
        "monitoring_active": monitoring_scheduler.is_running,
    }


@router.post("/start", status_code=status.HTTP_200_OK)
async def start_monitoring() -> dict:
    # Must be async: FastAPI runs sync `def` endpoints in a worker thread,
    # but PeriodicTask.start() calls asyncio.create_task(), which requires
    # running on the actual event loop thread.
    monitoring_scheduler.start()
    return {"message": "Background monitoring agent started successfully"}


@router.post("/stop", status_code=status.HTTP_200_OK)
async def stop_monitoring() -> dict:
    await monitoring_scheduler.stop()
    return {"message": "Background monitoring agent stopped successfully"}
