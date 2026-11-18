"""
AutoCura - Alerts API

GET  /api/alerts                    - list recent alerts
POST /api/alerts/{alert_id}/acknowledge - mark an alert acknowledged
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.alert_schema import AlertResponse
from app.services.alert_service import AlertService

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("", response_model=list[AlertResponse])
def get_all_alerts(limit: int = 50, db: Session = Depends(get_db)) -> list:
    return AlertService.get_alerts(db, limit=limit)


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)) -> dict:
    success = AlertService.acknowledge_alert(db, alert_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert ID not found")
    return {"message": f"Alert {alert_id} acknowledged successfully"}
