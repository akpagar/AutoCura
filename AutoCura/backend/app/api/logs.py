"""
AutoCura - Logs API

GET /api/logs            - recent log entries (optionally filtered by service)
GET /api/logs/{service}  - recent log entries for one named service
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.log_schema import LogResponse
from app.services.log_service import LogService

router = APIRouter(prefix="/api/logs", tags=["Logs"])


@router.get("", response_model=list[LogResponse])
def get_system_logs(
    service_name: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list:
    return LogService.get_logs(db, service_name=service_name, limit=limit)


@router.get("/{service_name}", response_model=list[LogResponse])
def get_logs_for_service(
    service_name: str,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list:
    return LogService.get_logs(db, service_name=service_name, limit=limit)
