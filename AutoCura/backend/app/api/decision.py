"""
AutoCura - Decision API

POST /api/decision/evaluate - run the full anomaly+ML+rules decision chain on live metrics
GET  /api/decision/history  - persisted decision history
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml.model_manager import model_exists
from app.schemas.decision_schema import DecisionResponse, DecisionResult
from app.services.decision_service import DecisionService

router = APIRouter(prefix="/api/decision", tags=["Decision"])


@router.post("/evaluate", response_model=DecisionResult)
def evaluate_decision(db: Session = Depends(get_db)) -> dict:
    if not model_exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No trained model found. Run `python scripts/generate_dataset.py` "
                "then `python scripts/train_model.py` first."
            ),
        )
    return DecisionService.evaluate_current(db)


@router.get("/history", response_model=list[DecisionResponse])
def get_decision_history(limit: int = 50, db: Session = Depends(get_db)) -> list:
    return DecisionService.get_history(db, limit=limit)
