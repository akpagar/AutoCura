"""
AutoCura - Phase 4 Decision Engine Tests

Unit tests against decision_engine/recovery_rules directly (fast,
deterministic, no trained model needed) plus API-level smoke tests
(which do use the shared trained_test_model fixture via `client`).
"""

from app.decision.decision_engine import evaluate, requires_recovery
from app.decision.recovery_rules import resolve_action


def _prediction(failure_type: str, severity: str = "HIGH", confidence: float = 0.9) -> dict:
    return {
        "failure_type": failure_type,
        "failure_probability": 0.9,
        "confidence": confidence,
        "severity": severity,
    }


def _no_anomaly() -> dict:
    return {"is_anomaly": False, "threshold_reasons": [], "isolation_forest_flagged": False}


def test_cpu_overload_maps_to_scale_service():
    action, _ = resolve_action("cpu_overload", "HIGH")
    assert action == "scale_service"


def test_service_failure_maps_to_restart_service():
    action, _ = resolve_action("service_failure", "HIGH")
    assert action == "restart_service"


def test_disk_exhaustion_stays_on_cleanup_even_at_critical():
    # Regression test: restarting a service does nothing to free disk
    # space, so CRITICAL must not blanket-override this to a restart.
    action, _ = resolve_action("disk_exhaustion", "CRITICAL")
    assert action == "cleanup_disk"


def test_network_degradation_escalates_to_restart_at_critical():
    normal_action, _ = resolve_action("network_degradation", "MEDIUM")
    critical_action, _ = resolve_action("network_degradation", "CRITICAL")
    assert normal_action == "redistribute_workload"
    assert critical_action == "restart_service"


def test_normal_requires_no_recovery():
    decision = evaluate(_prediction("normal", severity="LOW"), _no_anomaly())
    assert decision["recommended_action"] == "no_action"
    assert requires_recovery(decision) is False


def test_failure_requires_recovery():
    decision = evaluate(_prediction("cpu_overload"), _no_anomaly())
    assert requires_recovery(decision) is True


def test_multiple_threshold_breaches_escalate_severity():
    single_breach = {"is_anomaly": True, "threshold_reasons": ["cpu_usage 90 > 85"], "isolation_forest_flagged": False}
    multi_breach = {
        "is_anomaly": True,
        "threshold_reasons": ["cpu_usage 90 > 85", "latency 600 > 500", "error_rate 0.1 > 0.05"],
        "isolation_forest_flagged": False,
    }
    decision_single = evaluate(_prediction("cpu_overload", severity="LOW"), single_breach)
    decision_multi = evaluate(_prediction("cpu_overload", severity="LOW"), multi_breach)

    severity_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert severity_order.index(decision_multi["severity"]) >= severity_order.index(decision_single["severity"])


def test_decision_evaluate_endpoint(client):
    response = client.post("/api/decision/evaluate")
    assert response.status_code == 200
    body = response.json()
    for key in ("failure_type", "severity", "recommended_action", "reason", "confidence"):
        assert key in body


def test_decision_history_returns_list(client):
    client.post("/api/decision/evaluate")
    response = client.get("/api/decision/history?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert "recommended_action" in body[0]


def test_new_failure_types_have_actions():
    assert resolve_action("high_error_rate", "HIGH")[0] == "restart_service"
    assert resolve_action("service_degraded", "HIGH")[0] == "redistribute_workload"
    assert resolve_action("resource_saturation", "CRITICAL")[0] == "scale_and_restart"


def test_hybrid_detects_new_failure_types_from_metric_patterns():
    from app.decision.hybrid import reconcile

    base = {"cpu_usage": 20, "memory_usage": 30, "disk_usage": 40, "latency": 15, "error_rate": 0.0, "service_status": "running"}
    ml_normal = {"failure_type": "normal", "severity": "LOW", "confidence": 0.9}

    spike = reconcile(dict(ml_normal), {**base, "error_rate": 0.18})
    assert spike["failure_type"] == "high_error_rate"

    degraded = reconcile(dict(ml_normal), {**base, "service_status": "degraded"})
    assert degraded["failure_type"] == "service_degraded"

    stopped = reconcile(dict(ml_normal), {**base, "service_status": "stopped"})
    assert stopped["failure_type"] == "service_failure"

    both = reconcile({"failure_type": "cpu_overload", "severity": "HIGH", "confidence": 0.9}, {**base, "cpu_usage": 94, "memory_usage": 91})
    assert both["failure_type"] == "resource_saturation"
    assert both["severity"] == "CRITICAL"

    cpu_only = reconcile({"failure_type": "cpu_overload", "severity": "HIGH", "confidence": 0.9}, {**base, "cpu_usage": 96})
    assert cpu_only["failure_type"] == "cpu_overload"
