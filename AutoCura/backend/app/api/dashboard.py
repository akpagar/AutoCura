"""
AutoCura - Dashboard API

Read-only aggregation endpoints the React dashboard (Phase 7) consumes.
GET /api/dashboard/summary   - top KPI cards
GET /api/dashboard/metrics   - time series for charts
GET /api/dashboard/failures  - recent failures table
GET /api/dashboard/recoveries - recent recovery actions table
GET /api/dashboard/alerts    - active alerts table
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.alert_schema import AlertResponse
from app.schemas.dashboard_schema import DashboardSummary
from app.schemas.failure_schema import FailureResponse
from app.schemas.metrics_schema import MetricResponse
from app.schemas.recovery_schema import RecoveryResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_summary(db: Session = Depends(get_db)) -> dict:
    return DashboardService.summary(db)


@router.get("/metrics", response_model=list[MetricResponse])
def get_metrics_series(limit: int = 100, db: Session = Depends(get_db)) -> list:
    return DashboardService.metrics_series(db, limit=limit)


@router.get("/failures", response_model=list[FailureResponse])
def get_recent_failures(limit: int = 20, db: Session = Depends(get_db)) -> list:
    return DashboardService.recent_failures(db, limit=limit)


@router.get("/recoveries", response_model=list[RecoveryResponse])
def get_recent_recoveries(limit: int = 20, db: Session = Depends(get_db)) -> list:
    return DashboardService.recent_recoveries(db, limit=limit)


@router.get("/alerts", response_model=list[AlertResponse])
def get_active_alerts(limit: int = 20, db: Session = Depends(get_db)) -> list:
    return DashboardService.active_alerts(db, limit=limit)
