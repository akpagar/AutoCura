"""
AutoCura - Dashboard Service

Aggregates data already persisted by the other services into the
shapes the dashboard needs. Deliberately does no new computation of its
own (no re-running ML, no new Docker calls) -- it only reads.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.alerts import Alert
from app.models.metrics import Metric
from app.models.prediction import Failure
from app.models.recovery import Recovery
from app.services.alert_service import AlertService
from app.services.monitoring_service import MonitoringService
from app.utils.constants import RecoveryStatus


class DashboardService:
    @staticmethod
    def summary(db: Session) -> dict:
        latest_metric = db.query(Metric).order_by(Metric.timestamp.desc()).first()
        current = MonitoringService.collect_current_metrics()

        active_failures = db.query(func.count(Failure.id)).filter(Failure.status != "resolved").scalar() or 0

        total_recoveries = db.query(func.count(Recovery.id)).scalar() or 0
        successful_recoveries = (
            db.query(func.count(Recovery.id)).filter(Recovery.status == RecoveryStatus.SUCCESS.value).scalar() or 0
        )
        success_rate = round(successful_recoveries / total_recoveries, 4) if total_recoveries else None

        avg_recovery_time = db.query(func.avg(Recovery.recovery_time)).filter(
            Recovery.status == RecoveryStatus.SUCCESS.value
        ).scalar()

        serious_open_failures = (
            db.query(func.count(Failure.id))
            .filter(Failure.status != "resolved", Failure.severity.in_(["HIGH", "CRITICAL"]))
            .scalar()
            or 0
        )
        service_down = current["service_status"] in ("stopped", "unknown")
        if (
            current["cpu_usage"] > 90 or current["memory_usage"] > 90 or current["disk_usage"] > 90
            or service_down or serious_open_failures > 0
        ):
            system_health = "critical"
        elif active_failures > 0 or current["service_status"] != "running":
            system_health = "degraded"
        else:
            system_health = "healthy"

        return {
            "system_health": system_health,
            "current_cpu": current["cpu_usage"],
            "current_memory": current["memory_usage"],
            "current_disk": current["disk_usage"],
            "service_status": current["service_status"],
            "active_failures": active_failures,
            "recovery_success_rate": success_rate,
            "average_recovery_time_seconds": round(avg_recovery_time, 2) if avg_recovery_time else None,
            "last_metric_timestamp": latest_metric.timestamp if latest_metric else None,
        }

    @staticmethod
    def metrics_series(db: Session, limit: int = 100) -> list[Metric]:
        rows = db.query(Metric).order_by(Metric.timestamp.desc()).limit(limit).all()
        return list(reversed(rows))  # chronological order for charting

    @staticmethod
    def recent_failures(db: Session, limit: int = 20) -> list[Failure]:
        return db.query(Failure).order_by(Failure.detected_at.desc()).limit(limit).all()

    @staticmethod
    def recent_recoveries(db: Session, limit: int = 20) -> list[Recovery]:
        return db.query(Recovery).order_by(Recovery.started_at.desc()).limit(limit).all()

    @staticmethod
    def active_alerts(db: Session, limit: int = 20) -> list[Alert]:
        return AlertService.get_alerts(db, limit=limit)
