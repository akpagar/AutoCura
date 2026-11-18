"""
AutoCura - Severity Calculation

The ML classifier's own severity (predict.py) is derived purely from
its probability output. The decision engine needs a broader view --
it also weighs how many threshold rules fired and whether the
Isolation Forest independently flagged the sample -- since a
borderline ML probability alongside multiple threshold breaches is a
stronger signal than either alone.
"""

from app.utils.constants import Severity

_SEVERITY_ORDER = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]


def _escalate(base: Severity, steps: int) -> Severity:
    index = min(_SEVERITY_ORDER.index(base) + steps, len(_SEVERITY_ORDER) - 1)
    return _SEVERITY_ORDER[index]


def compute_severity(prediction_severity: str, anomaly_info: dict) -> str:
    """
    Starts from the ML model's own severity estimate, then escalates by
    one level per additional threshold rule breached (beyond the first)
    and one more level if the Isolation Forest independently flags the
    sample -- i.e. corroborating signals push severity up, but a single
    borderline ML call alone does not.
    """
    try:
        base = Severity(prediction_severity)
    except ValueError:
        base = Severity.LOW

    threshold_count = len(anomaly_info.get("threshold_reasons", []))
    escalation_steps = max(0, threshold_count - 1)

    if anomaly_info.get("isolation_forest_flagged"):
        escalation_steps += 1

    return _escalate(base, escalation_steps).value
