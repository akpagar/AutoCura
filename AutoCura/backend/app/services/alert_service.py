"""
AutoCura - Alert Service

Creates, lists, and acknowledges alerts. Called by monitoring_service.py
whenever a metric crosses a configured threshold, and later by the
decision/recovery layers for predicted-failure and failed-recovery alerts.
"""

from sqlalchemy.orm import Session

from app.models.alerts import Alert
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AlertService:
    @staticmethod
    def create_alert(
        db: Session,
        alert_type: str,
        severity: str,
        message: str,
        source: str = "monitoring_engine",
    ) -> Alert:
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            source=source,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        logger.warning("ALERT CREATED [%s] (%s): %s", severity, alert_type, message)
        return alert

    @staticmethod
    def get_alerts(db: Session, limit: int = 50) -> list[Alert]:
        return db.query(Alert).order_by(Alert.timestamp.desc()).limit(limit).all()

    @staticmethod
    def acknowledge_alert(db: Session, alert_id: int) -> bool:
        alert = db.get(Alert, alert_id)
        if alert is None:
            return False
        alert.acknowledged = True
        db.commit()
        return True
