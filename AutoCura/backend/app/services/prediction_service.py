"""
AutoCura - Prediction Service

Combines live/override metrics, anomaly detection, and the trained
classifier into a single failure prediction, and persists it. This is
the module the API and (in Phase 6) the automated pipeline both call.
"""

from sqlalchemy.orm import Session

from app.ml.anomaly import detect_anomaly
from app.ml.predict import predict_from_metrics
from app.models.prediction import Prediction
from app.schemas.prediction_schema import PredictionRequest
from app.services.monitoring_service import MonitoringService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PredictionService:
    @staticmethod
    def _resolve_metrics(override: PredictionRequest | None) -> dict:
        """Start from a live sample, then apply any manually-provided overrides."""
        metrics = MonitoringService.collect_current_metrics()
        if override is not None:
            for field, value in override.model_dump(exclude_none=True).items():
                metrics[field] = value
        return metrics

    @staticmethod
    def predict(db: Session, override: PredictionRequest | None = None, metric_id: int | None = None) -> dict:
        metrics = PredictionService._resolve_metrics(override)

        anomaly_info = detect_anomaly(metrics)
        prediction_result = predict_from_metrics(metrics)

        prediction = Prediction(
            metric_id=metric_id,
            failure_probability=prediction_result["failure_probability"],
            predicted_failure_type=prediction_result["failure_type"],
            confidence=prediction_result["confidence"],
            severity=prediction_result["severity"],
        )
        db.add(prediction)
        db.commit()
        db.refresh(prediction)

        logger.info(
            "Prediction stored: type=%s probability=%.3f severity=%s",
            prediction.predicted_failure_type,
            prediction.failure_probability,
            prediction.severity,
        )

        return {
            **prediction_result,
            "anomaly": anomaly_info,
            "prediction_id": prediction.id,
            "metrics_used": metrics,
        }

    @staticmethod
    def get_history(db: Session, limit: int = 50) -> list[Prediction]:
        return db.query(Prediction).order_by(Prediction.timestamp.desc()).limit(limit).all()
