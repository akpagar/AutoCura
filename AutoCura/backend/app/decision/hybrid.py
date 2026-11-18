"""
AutoCura - Hybrid Detection (ML + threshold rules)

The Random Forest was trained on synthetic samples where each failure
type moves several metrics together (a CPU overload also raises latency
and error rate, for example). A live sample that breaches only ONE
metric -- which is what a real single-resource incident, or a controlled
simulation, often looks like -- can fall between those learned clusters
and be classified "normal" even though a configured threshold is clearly
exceeded.

So the threshold rules are treated as hard evidence: if a configured
threshold is breached and the ML prediction does not explain it, the
failure type is taken from the rule instead, and the decision records
that it was a rule-based override (honest labelling -- the ML model is
not credited for it).
"""

from app.config import settings
from app.utils.constants import FailureType, Severity

# Metric(s) that justify each failure type being the diagnosis.
_TYPE_EVIDENCE: dict[str, set[str]] = {
    FailureType.CPU_OVERLOAD.value: {"cpu_usage"},
    FailureType.MEMORY_EXHAUSTION.value: {"memory_usage"},
    FailureType.DISK_EXHAUSTION.value: {"disk_usage"},
    FailureType.NETWORK_DEGRADATION.value: {"latency"},
    FailureType.SERVICE_FAILURE.value: {"service_status"},
    FailureType.HIGH_ERROR_RATE.value: {"error_rate"},
    FailureType.SERVICE_DEGRADED.value: {"service_status"},
    FailureType.RESOURCE_SATURATION.value: {"cpu_usage", "memory_usage"},
}

_METRIC_TO_TYPE = {
    "cpu_usage": FailureType.CPU_OVERLOAD.value,
    "memory_usage": FailureType.MEMORY_EXHAUSTION.value,
    "disk_usage": FailureType.DISK_EXHAUSTION.value,
    "latency": FailureType.NETWORK_DEGRADATION.value,
    "error_rate": FailureType.HIGH_ERROR_RATE.value,
}


def breached_metrics(metrics: dict) -> dict[str, float]:
    """Returns {metric_name: breach_ratio} for every configured threshold exceeded (ratio = value / threshold)."""
    limits = {
        "cpu_usage": settings.CPU_THRESHOLD,
        "memory_usage": settings.MEMORY_THRESHOLD,
        "disk_usage": settings.DISK_THRESHOLD,
        "latency": settings.LATENCY_THRESHOLD,
        "error_rate": settings.ERROR_RATE_THRESHOLD,
    }
    breached: dict[str, float] = {}
    for name, limit in limits.items():
        value = metrics.get(name, 0) or 0
        if limit > 0 and value > limit:
            breached[name] = value / limit
    if metrics.get("service_status", "running") != "running":
        breached["service_status"] = 10.0  # a down service outranks any resource breach
    return breached


def special_failure_type(metrics: dict) -> str | None:
    """
    Failure types identified by a *pattern* of metrics rather than the single
    worst metric: both CPU and memory saturated, a service that is degraded
    (as opposed to stopped), or an error-rate spike with everything else
    healthy. These take priority over the generic single-metric rule.
    """
    breached = breached_metrics(metrics)
    if "cpu_usage" in breached and "memory_usage" in breached:
        return FailureType.RESOURCE_SATURATION.value
    status = metrics.get("service_status", "running")
    if status != "running":
        return FailureType.SERVICE_DEGRADED.value if status == "degraded" else FailureType.SERVICE_FAILURE.value
    if set(breached) == {"error_rate"}:
        return FailureType.HIGH_ERROR_RATE.value
    return None


def rule_based_failure_type(metrics: dict) -> str | None:
    """The failure type implied by the worst threshold breach, or None if nothing is breached."""
    breached = breached_metrics(metrics)
    if not breached:
        return None
    worst = max(breached, key=breached.get)
    if worst == "service_status":
        return special_failure_type(metrics) or FailureType.SERVICE_FAILURE.value
    return _METRIC_TO_TYPE[worst]


def reconcile(prediction_result: dict, metrics: dict) -> dict:
    """
    Returns the prediction unchanged when the ML result is consistent
    with the threshold evidence (or there is none). Otherwise returns a
    copy whose failure_type comes from the rules, with severity raised to
    at least HIGH and `source` set to "rule_override".
    """
    breached = breached_metrics(metrics)
    result = dict(prediction_result)
    result.setdefault("source", "ml")
    if not breached:
        return result

    ml_type = prediction_result["failure_type"]
    special = special_failure_type(metrics)
    if special is not None:
        if ml_type == special:
            return result
        rule_type = special
    else:
        if _TYPE_EVIDENCE.get(ml_type, set()) & set(breached):
            return result  # ML diagnosis is backed by a breached metric
        rule_type = rule_based_failure_type(metrics)
        if rule_type is None:
            return result

    result["ml_failure_type"] = ml_type
    result["failure_type"] = rule_type
    result["source"] = "rule_override"
    if rule_type == FailureType.RESOURCE_SATURATION.value:
        result["severity"] = Severity.CRITICAL.value
    elif result.get("severity") not in (Severity.HIGH.value, Severity.CRITICAL.value):
        result["severity"] = Severity.HIGH.value
    # Confidence reflects the evidence, not the (disagreeing) classifier.
    result["confidence"] = round(min(1.0, 0.7 + 0.1 * len(breached)), 2)
    return result
