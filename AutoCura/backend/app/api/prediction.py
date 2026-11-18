"""
AutoCura - Prediction API

POST /api/prediction/predict - run a failure prediction (live metrics, or overrides for demo/testing)
GET  /api/prediction/history - persisted prediction history
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml.model_manager import model_exists
from app.schemas.prediction_schema import PredictionRequest, PredictionResponse, PredictionResult
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/api/prediction", tags=["Prediction"])


@router.post("/predict", response_model=PredictionResult)
def predict(payload: PredictionRequest | None = None, db: Session = Depends(get_db)) -> dict:
    if not model_exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No trained model found. Run `python scripts/generate_dataset.py` "
                "then `python scripts/train_model.py` first."
            ),
        )
    return PredictionService.predict(db, override=payload)


@router.get("/history", response_model=list[PredictionResponse])
def get_prediction_history(limit: int = 50, db: Session = Depends(get_db)) -> list:
    return PredictionService.get_history(db, limit=limit)
