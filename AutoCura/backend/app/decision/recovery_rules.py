"""
AutoCura - Recovery Rules

The rule table mapping each failure type to its recovery action, per
spec section 12. Kept as pure data + a lookup function so the decision
engine's control flow stays simple and this table is easy to audit/
extend without touching engine logic.

CRITICAL severity does not blanket-override every failure type to the
same "strongest" action -- restarting a service does nothing to free
disk space, for example. Instead, each failure type defines its own
already-appropriate action, and only network degradation escalates to
a different action at CRITICAL (matching spec section 12's explicit
"redistribute workload / restart controlled service if appropriate"),
since redistribution alone may not be enough once things are that bad.
"""

from app.utils.constants import FailureType, RecoveryAction, Severity

_RULES: dict[FailureType, tuple[RecoveryAction, str]] = {
    FailureType.CPU_OVERLOAD: (
        RecoveryAction.SCALE_SERVICE,
        "High CPU utilization detected; scaling the affected service to redistribute load.",
    ),
    FailureType.MEMORY_EXHAUSTION: (
        RecoveryAction.RESTART_SERVICE,
        "Memory exhaustion detected; restarting the affected service to reclaim memory.",
    ),
    FailureType.DISK_EXHAUSTION: (
        RecoveryAction.CLEANUP_DISK,
        "Disk space critically low; running controlled cleanup of temporary resources.",
    ),
    FailureType.SERVICE_FAILURE: (
        RecoveryAction.RESTART_SERVICE,
        "Service health check failed; restarting the affected service.",
    ),
    FailureType.NETWORK_DEGRADATION: (
        RecoveryAction.REDISTRIBUTE_WORKLOAD,
        "Network degradation detected; redistributing workload across available workers.",
    ),
    FailureType.HIGH_ERROR_RATE: (
        RecoveryAction.RESTART_SERVICE,
        "Error rate spiked while resources look normal; restarting the affected service to clear a faulty process state.",
    ),
    FailureType.SERVICE_DEGRADED: (
        RecoveryAction.REDISTRIBUTE_WORKLOAD,
        "Service is degraded but not down; redistributing workload to healthy workers.",
    ),
    FailureType.RESOURCE_SATURATION: (
        RecoveryAction.SCALE_AND_RESTART,
        "CPU and memory are both saturated; scaling out the worker pool and restarting the affected service.",
    ),
    FailureType.NORMAL: (
        RecoveryAction.NO_ACTION,
        "No failure detected; system operating within normal parameters.",
    ),
}

# Per-failure-type CRITICAL escalation. Only failure types where a
# stronger *different* action genuinely helps get an entry here; the
# rest already use their strongest appropriate action at any severity.
_CRITICAL_ESCALATION: dict[FailureType, tuple[RecoveryAction, str]] = {
    FailureType.NETWORK_DEGRADATION: (
        RecoveryAction.RESTART_SERVICE,
        "Network degradation is CRITICAL and redistribution alone is unlikely to be "
        "sufficient; restarting the affected service as the stronger safe action.",
    ),
}


def resolve_action(failure_type: str, severity: str) -> tuple[str, str]:
    """Returns (recovery_action, reason) for a given failure type + severity."""
    try:
        ftype = FailureType(failure_type)
    except ValueError:
        ftype = FailureType.NORMAL

    action, reason = _RULES[ftype]

    if severity == Severity.CRITICAL.value and ftype in _CRITICAL_ESCALATION:
        action, reason = _CRITICAL_ESCALATION[ftype]

    return action.value, reason
