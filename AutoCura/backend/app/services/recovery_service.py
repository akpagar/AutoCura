"""
AutoCura - Recovery Service

Dispatches a decision's recommended action to the right recovery
module, verifies the outcome, retries up to RECOVERY_RETRY_LIMIT on
failure, and escalates (alert + Failure.status="escalated") if every
attempt fails. Every attempt is persisted as its own Recovery row for
a complete audit trail -- per spec section 14, "Do not create infinite
retries."
"""

import asyncio
import threading
import time

from sqlalchemy.orm import Session

from app.config import settings
from app.decision.decision_engine import evaluate, requires_recovery
from app.decision.hybrid import reconcile
from app.ml.anomaly import detect_anomaly
from app.ml.predict import predict_from_metrics
from app.models.decision import Decision
from app.models.recovery import Recovery
from app.models.prediction import Failure
from app.recovery.auto_scaling import scale_service
from app.recovery.cleanup_disk import cleanup_disk
from app.recovery.recovery_verifier import verify_recovery
from app.recovery.restart_service import restart_container
from app.recovery.simulation_state import simulation_state
from app.recovery.workload_migration import migrate_workload
from app.services.alert_service import AlertService
from app.services.monitoring_service import MonitoringService
from app.utils.constants import RecoveryAction, RecoveryStatus
from app.utils.helpers import utc_now
from app.utils.logger import get_logger

logger = get_logger(__name__)

_PRIMARY_SERVICE_CONTAINER = f"{settings.AUTOCURA_CONTAINER_PREFIX}primary_service"


# Only one recovery chain may run at a time (automated pipeline, the
# simulation endpoints' immediate trigger and the manual button all share
# it) so two chains can never fight over the same container.
RECOVERY_LOCK = threading.Lock()
_MANUAL_LOCK_WAIT_SECONDS = 30


def _busy_result(metrics: dict) -> dict:
    return {
        "success": True, "recovery_time_seconds": 0.0, "action": "no_action",
        "failure_type": "normal", "before": metrics, "after": metrics,
        "execution_detail": {"message": "Another recovery is already in progress; skipped."},
    }


def _dispatch_action(action: str, failure_type: str) -> dict:
    """
    Runs the actual recovery action module for a given action string,
    then -- only on success -- resolves any active simulation override
    matching this failure_type. Without this, a *simulated* scenario
    would never show measurable improvement no matter what recovery
    action ran (there's no real host condition for a real action to
    fix), which would make verification always and misleadingly fail.
    A genuinely real failure (not simulation-injected) has no matching
    active scenario, so this is a no-op for it.
    """
    if action == RecoveryAction.RESTART_SERVICE.value:
        result = restart_container(_PRIMARY_SERVICE_CONTAINER)
    elif action == RecoveryAction.SCALE_SERVICE.value:
        result = scale_service(target_replicas=3)
    elif action == RecoveryAction.REDISTRIBUTE_WORKLOAD.value:
        result = migrate_workload(from_index=1)
    elif action == RecoveryAction.CLEANUP_DISK.value:
        result = cleanup_disk()
    elif action == RecoveryAction.SCALE_AND_RESTART.value:
        scaled = scale_service(target_replicas=3)
        restarted = restart_container(_PRIMARY_SERVICE_CONTAINER)
        result = {
            "success": bool(scaled.get("success") and restarted.get("success")),
            "simulated": bool(scaled.get("simulated") and restarted.get("simulated")),
            "message": f"{scaled.get('message', '')} {restarted.get('message', '')}".strip(),
        }
    else:
        result = {"success": True, "simulated": True, "message": "No action required."}

    if result.get("success"):
        result["simulation_resolved"] = simulation_state.resolve_scenario(failure_type)

    return result


class RecoveryService:
    @staticmethod
    async def execute(
        db: Session,
        override_action: str | None = None,
        override_failure_type: str | None = None,
        wait_for_lock: bool = True,
        response_delay: float = 0.0,
    ) -> dict:
        """
        wait_for_lock=True (manual button): waits for an in-flight recovery to
        finish, then evaluates fresh state. wait_for_lock=False (background
        pipeline): skips this cycle if a recovery is already running.
        """
        if wait_for_lock:
            acquired = await asyncio.to_thread(RECOVERY_LOCK.acquire, True, _MANUAL_LOCK_WAIT_SECONDS)
        else:
            acquired = RECOVERY_LOCK.acquire(False)
        if not acquired:
            return _busy_result(MonitoringService.collect_current_metrics())
        try:
            return await RecoveryService._execute_locked(db, override_action, override_failure_type, response_delay)
        finally:
            RECOVERY_LOCK.release()

    @staticmethod
    async def _execute_locked(
        db: Session, override_action: str | None, override_failure_type: str | None, response_delay: float = 0.0
    ) -> dict:
        before_metrics = await asyncio.to_thread(MonitoringService.collect_current_metrics)

        if override_action and override_failure_type:
            failure_type = override_failure_type
            action = override_action
            severity = "HIGH"
            confidence = 1.0
            reason = "Manually specified action (bypassing the decision chain)."
        else:
            anomaly_info = detect_anomaly(before_metrics)
            prediction_result = reconcile(predict_from_metrics(before_metrics), before_metrics)
            decision = evaluate(prediction_result, anomaly_info)

            if not requires_recovery(decision):
                # Healthy cycles are not persisted: the background loop runs
                # every few seconds and would otherwise flood the decisions table.
                return {
                    "success": True, "recovery_time_seconds": 0.0,
                    "action": "no_action", "failure_type": decision["failure_type"],
                    "before": before_metrics, "after": before_metrics,
                    "execution_detail": {"message": "System healthy; no recovery needed."},
                }

            db.add(Decision(
                failure_type=decision["failure_type"], severity=decision["severity"],
                recommended_action=decision["recommended_action"], reason=decision["reason"],
                confidence=decision["confidence"],
            ))
            db.commit()

            failure_type = decision["failure_type"]
            action = decision["recommended_action"]
            severity = decision["severity"]
            confidence = decision["confidence"]
            reason = decision["reason"]

        failure = Failure(failure_type=failure_type, severity=severity, predicted=True, status="detected")
        db.add(failure)
        db.commit()
        db.refresh(failure)

        if response_delay > 0:
            # Detection is visible first: the failure row is open (dashboard
            # health turns critical) and an alert is raised before any action.
            AlertService.create_alert(
                db, "FAILURE_DETECTED", severity if severity in ("HIGH", "CRITICAL") else "HIGH",
                f"{failure_type} detected ({severity}); automated recovery '{action}' starts in {response_delay:.0f}s.",
                source="recovery_engine",
            )
            await asyncio.sleep(response_delay)
        failure.status = "recovering"
        db.commit()

        result = await RecoveryService._execute_with_retries(db, failure, action, failure_type, before_metrics)
        result["failure_type"] = failure_type
        result["reason"] = reason
        result["confidence"] = confidence
        return result

    @staticmethod
    async def _execute_with_retries(db: Session, failure: Failure, action: str, failure_type: str, before_metrics: dict) -> dict:
        last_verification: dict = {}
        last_execution: dict = {}

        for attempt in range(1, settings.RECOVERY_RETRY_LIMIT + 1):
            started_at = time.monotonic()
            execution = await asyncio.to_thread(_dispatch_action, action, failure_type)
            verification = await verify_recovery(
                failure_type, before_metrics, started_at,
                simulation_resolved=bool(execution.get("simulation_resolved")),
            )

            recovery_row = Recovery(
                failure_id=failure.id,
                action=action,
                status=RecoveryStatus.SUCCESS.value if verification["success"] else RecoveryStatus.FAILED.value,
                result=execution.get("message", ""),
                recovery_time=verification["recovery_time_seconds"],
                completed_at=utc_now(),
            )
            db.add(recovery_row)
            db.commit()

            last_verification, last_execution = verification, execution

            if verification["success"]:
                failure.status = "resolved"
                db.commit()
                logger.info("Recovery succeeded for failure_id=%s action=%s (attempt %d)", failure.id, action, attempt)
                break

            logger.warning(
                "Recovery attempt %d/%d failed for failure_id=%s action=%s",
                attempt, settings.RECOVERY_RETRY_LIMIT, failure.id, action,
            )
        else:
            failure.status = "escalated"
            db.commit()
            AlertService.create_alert(
                db, "RECOVERY_FAILED", "CRITICAL",
                f"Recovery action '{action}' failed after {settings.RECOVERY_RETRY_LIMIT} attempts "
                f"for failure_type={failure_type}. Escalating for manual intervention.",
                source="recovery_engine",
            )

        return {
            "success": last_verification.get("success", False),
            "recovery_time_seconds": last_verification.get("recovery_time_seconds", 0.0),
            "action": action,
            "before": last_verification.get("before", before_metrics),
            "after": last_verification.get("after", before_metrics),
            "execution_detail": last_execution,
        }

    @staticmethod
    def get_history(db: Session, limit: int = 50) -> list[Recovery]:
        return db.query(Recovery).order_by(Recovery.started_at.desc()).limit(limit).all()
