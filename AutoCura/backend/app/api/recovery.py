"""
AutoCura - Recovery API

POST /api/recovery/execute - run the decision chain (or an explicit override) and execute + verify recovery
GET  /api/recovery/history - persisted recovery attempt history
GET  /api/recovery/status  - current simulation + monitoring snapshot, for a quick dashboard check
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml.model_manager import model_exists
from app.recovery.simulation_state import simulation_state
from app.schemas.recovery_schema import RecoveryExecuteRequest, RecoveryResponse, RecoveryResult
from app.services.monitoring_service import MonitoringService
from app.services.recovery_service import RecoveryService

router = APIRouter(prefix="/api/recovery", tags=["Recovery"])


@router.post("/execute", response_model=RecoveryResult)
async def execute_recovery(payload: RecoveryExecuteRequest | None = None, db: Session = Depends(get_db)) -> dict:
    override_action = payload.action if payload else None
    override_failure_type = payload.failure_type if payload else None

    if not override_action and not model_exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No trained model found, and no explicit action override was given. "
                "Run `python scripts/generate_dataset.py` then `python scripts/train_model.py`, "
                "or pass {\"action\": ..., \"failure_type\": ...} explicitly."
            ),
        )
    return await RecoveryService.execute(db, override_action=override_action, override_failure_type=override_failure_type)


@router.get("/history", response_model=list[RecoveryResponse])
def get_recovery_history(limit: int = 50, db: Session = Depends(get_db)) -> list:
    return RecoveryService.get_history(db, limit=limit)


@router.get("/status")
def get_recovery_status() -> dict:
    return {
        "current_metrics": MonitoringService.collect_current_metrics(),
        "active_simulations": simulation_state.status(),
    }
