"""
AutoCura - Decision Engine

Combines the ML prediction, anomaly signals, and the recovery rule
table into one decision. This module has no I/O of its own (no DB, no
Docker) -- decision_service.py handles persistence, recovery_service.py
handles execution. Keeping this pure makes it directly unit-testable.
"""

from app.decision.recovery_rules import resolve_action
from app.decision.severity import compute_severity
from app.utils.constants import RecoveryAction


def evaluate(prediction_result: dict, anomaly_info: dict) -> dict:
    """
    prediction_result: output of app.ml.predict.predict_from_metrics()
    anomaly_info: output of app.ml.anomaly.detect_anomaly()

    Returns:
        {
            "failure_type": ...,
            "severity": ...,
            "recommended_action": ...,
            "reason": ...,
            "confidence": ...,
        }
    """
    failure_type = prediction_result["failure_type"]
    severity = compute_severity(prediction_result["severity"], anomaly_info)
    action, reason = resolve_action(failure_type, severity)
    if prediction_result.get("source") == "rule_override":
        reason = (
            f"Threshold rule override (ML classifier said "
            f"'{prediction_result.get('ml_failure_type', 'normal')}'): {reason}"
        )

    return {
        "failure_type": failure_type,
        "severity": severity,
        "recommended_action": action,
        "reason": reason,
        "confidence": prediction_result["confidence"],
    }


def requires_recovery(decision: dict) -> bool:
    """A NO_ACTION decision (healthy system) needs no recovery execution."""
    return decision["recommended_action"] != RecoveryAction.NO_ACTION.value
