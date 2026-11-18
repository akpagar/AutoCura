"""
AutoCura - Decision Service

Runs the full monitoring -> anomaly -> ML prediction -> decision chain
and persists the resulting decision. This is the module Phase 6's
automated pipeline calls after a metric sample comes in.
"""

from sqlalchemy.orm import Session

from app.decision.decision_engine import evaluate
from app.decision.hybrid import reconcile
from app.ml.anomaly import detect_anomaly
from app.ml.predict import predict_from_metrics
from app.models.decision import Decision
from app.services.monitoring_service import MonitoringService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DecisionService:
    @staticmethod
    def evaluate_current(db: Session) -> dict:
        """Pulls a fresh live sample and runs the full decision chain on it."""
        metrics = MonitoringService.collect_current_metrics()
        return DecisionService.evaluate_metrics(db, metrics)

    @staticmethod
    def evaluate_metrics(db: Session, metrics: dict) -> dict:
        anomaly_info = detect_anomaly(metrics)
        prediction_result = reconcile(predict_from_metrics(metrics), metrics)
        decision = evaluate(prediction_result, anomaly_info)

        record = Decision(
            failure_type=decision["failure_type"],
            severity=decision["severity"],
            recommended_action=decision["recommended_action"],
            reason=decision["reason"],
            confidence=decision["confidence"],
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        logger.info(
            "Decision stored: failure_type=%s severity=%s action=%s",
            decision["failure_type"], decision["severity"], decision["recommended_action"],
        )

        return {**decision, "decision_id": record.id, "metrics_used": metrics}

    @staticmethod
    def get_history(db: Session, limit: int = 50) -> list[Decision]:
        return db.query(Decision).order_by(Decision.timestamp.desc()).limit(limit).all()
