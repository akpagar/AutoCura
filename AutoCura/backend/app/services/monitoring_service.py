"""
AutoCura - Monitoring Service

Orchestrates the individual collectors (CPU/memory/disk/network/service),
persists samples to the `metrics` table, and raises alerts + log entries
when configured thresholds are crossed. This is the module the background
scheduler and the /api/monitoring endpoints both call into.
"""

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.metrics import Metric
from app.monitoring.cpu_monitor import CPUMonitor
from app.monitoring.disk_monitor import DiskMonitor
from app.monitoring.log_collector import LogCollector
from app.monitoring.memory_monitor import MemoryMonitor
from app.monitoring.network_monitor import NetworkMonitor
from app.monitoring.service_monitor import ServiceMonitor
from app.recovery.simulation_state import simulation_state
from app.services.alert_service import AlertService
from app.services.log_service import LogService
from app.utils.constants import ServiceStatus
from app.utils.helpers import round2
from app.utils.logger import get_logger
from app.utils.scheduler import PeriodicTask

logger = get_logger(__name__)

# Phase 2 baseline: latency and error_rate are not yet derived from a real
# request pipeline (no load-generating client exists yet). They are
# reported as a fixed healthy baseline so downstream consumers (ML,
# decision engine) have the fields populated; Phase 5's failure
# simulation module overrides these with real simulated values on demand.
_BASELINE_LATENCY_MS = 15.2
_BASELINE_ERROR_RATE = 0.0


class MonitoringService:
    @staticmethod
    def collect_current_metrics() -> dict:
        """Collect a single fresh sample from all monitors (no DB write)."""
        cpu = CPUMonitor.get_metrics()
        memory = MemoryMonitor.get_metrics()
        disk = DiskMonitor.get_metrics()
        network = NetworkMonitor.get_metrics()
        status = ServiceMonitor.check_service_health()

        metrics = {
            "cpu_usage": round2(cpu),
            "memory_usage": round2(memory["percentage"]),
            "disk_usage": round2(disk["percentage"]),
            "network_in": float(network["bytes_recv"]),
            "network_out": float(network["bytes_sent"]),
            "latency": _BASELINE_LATENCY_MS,
            "error_rate": _BASELINE_ERROR_RATE,
            "service_status": status,
            "hostname": "localhost",
        }
        # Failure simulation overrides (api/simulation.py) are applied here
        # so every consumer -- the API, the background scheduler, the ML
        # pipeline -- sees the same simulated state consistently.
        return simulation_state.apply(metrics)

    @staticmethod
    def record_metrics(db: Session) -> Metric:
        """Collect a sample, persist it, and raise alerts on threshold breaches."""
        data = MonitoringService.collect_current_metrics()

        metric = Metric(
            cpu_usage=data["cpu_usage"],
            memory_usage=data["memory_usage"],
            disk_usage=data["disk_usage"],
            network_in=data["network_in"],
            network_out=data["network_out"],
            latency=data["latency"],
            error_rate=data["error_rate"],
            service_status=data["service_status"],
            hostname=data["hostname"],
        )
        db.add(metric)
        db.commit()
        db.refresh(metric)

        MonitoringService._check_thresholds(db, metric)
        return metric

    @staticmethod
    def _check_thresholds(db: Session, metric: Metric) -> None:
        """Raise an alert (and a log entry) for any metric over its configured threshold."""
        if metric.cpu_usage > settings.CPU_THRESHOLD:
            MonitoringService._raise_alert(
                db, "HIGH_CPU", "HIGH",
                f"CPU utilization exceeded threshold: {metric.cpu_usage}% (limit {settings.CPU_THRESHOLD}%)",
            )
        if metric.memory_usage > settings.MEMORY_THRESHOLD:
            MonitoringService._raise_alert(
                db, "HIGH_MEMORY", "HIGH",
                f"Memory utilization exceeded threshold: {metric.memory_usage}% (limit {settings.MEMORY_THRESHOLD}%)",
            )
        if metric.disk_usage > settings.DISK_THRESHOLD:
            MonitoringService._raise_alert(
                db, "HIGH_DISK", "CRITICAL",
                f"Disk space utilization critical: {metric.disk_usage}% (limit {settings.DISK_THRESHOLD}%)",
            )
        if metric.latency > settings.LATENCY_THRESHOLD:
            MonitoringService._raise_alert(
                db, "HIGH_LATENCY", "HIGH",
                f"Latency exceeded threshold: {metric.latency} ms (limit {settings.LATENCY_THRESHOLD} ms)",
            )
        if metric.error_rate > settings.ERROR_RATE_THRESHOLD:
            MonitoringService._raise_alert(
                db, "HIGH_ERROR_RATE", "HIGH",
                f"Error rate exceeded threshold: {metric.error_rate:.0%} (limit {settings.ERROR_RATE_THRESHOLD:.0%})",
            )
        if metric.service_status != ServiceStatus.RUNNING.value:
            MonitoringService._raise_alert(
                db, "SERVICE_DEGRADED", "HIGH",
                f"Service health check reported status: {metric.service_status}",
            )

    @staticmethod
    def _raise_alert(db: Session, alert_type: str, severity: str, message: str) -> None:
        AlertService.create_alert(db, alert_type, severity, message, source="monitoring_engine")
        log_data = LogCollector.generate_system_log(
            source="monitoring_service", level="WARNING", message=message
        )
        LogService.record_log(
            db,
            source=log_data["source"],
            level=log_data["level"],
            message=log_data["message"],
            service_name=log_data["service_name"],
        )

    @staticmethod
    def get_history(db: Session, limit: int = 50) -> list[Metric]:
        return db.query(Metric).order_by(Metric.timestamp.desc()).limit(limit).all()


def _collect_and_store() -> None:
    """One scheduler tick: open a short-lived session, record a sample, close it."""
    db = SessionLocal()
    try:
        MonitoringService.record_metrics(db)
    except Exception:
        logger.exception("Background monitoring cycle failed")
    finally:
        db.close()

    # Phase 6: run the automated decide->act->verify pipeline after every
    # collection cycle. Imported lazily -- pipeline_service ultimately
    # depends back on this module (via recovery_service), so importing
    # it at module load time would create a circular import.
    try:
        import threading

        from app.services.pipeline_service import run_pipeline_sync
        from app.services.recovery_service import RECOVERY_LOCK

        # Run on its own thread (skipped while a recovery is in flight) so the
        # response delay and verification never pause metric collection --
        # the dashboard keeps showing live values during recovery.
        if not RECOVERY_LOCK.locked():
            threading.Thread(target=run_pipeline_sync, name="autocura-pipeline", daemon=True).start()
    except Exception:
        logger.exception("Automated pipeline step failed")


# Singleton background task, started/stopped from the app lifespan and
# from the /api/monitoring/start and /stop endpoints.
monitoring_scheduler = PeriodicTask(
    name="monitoring_collection",
    func=_collect_and_store,
    interval_seconds=settings.MONITORING_INTERVAL_SECONDS,
)
