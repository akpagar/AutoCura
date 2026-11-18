"""
AutoCura - Recovery Verification

Per spec section 14: recovery is NOT successful just because an action
executed without raising. This module waits for stabilization, takes a
fresh metrics sample, and compares it against the pre-recovery sample
to decide whether the situation actually improved.
"""

import asyncio
import time

from app.config import settings
from app.services.monitoring_service import MonitoringService
from app.utils.constants import FailureType
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Which metric should have gone DOWN for each failure type to call the
# recovery genuinely successful (service_failure is judged on service
# status instead, handled separately below).
_RELEVANT_METRIC = {
    FailureType.CPU_OVERLOAD.value: "cpu_usage",
    FailureType.MEMORY_EXHAUSTION.value: "memory_usage",
    FailureType.DISK_EXHAUSTION.value: "disk_usage",
    FailureType.NETWORK_DEGRADATION.value: "latency",
    FailureType.HIGH_ERROR_RATE.value: "error_rate",
}


# Re-check quickly and return as soon as recovery is observed, instead of
# always sleeping the full stabilization window. The window is only an
# upper bound for slow recoveries (e.g. a container still starting).
_FIRST_CHECK_DELAY_SECONDS = 0.3
_POLL_INTERVAL_SECONDS = 0.7
# A drop of at least this fraction counts as improvement even if the
# metric is still above its alert threshold.
_MIN_IMPROVEMENT_FRACTION = 0.2


def _metric_recovered(metric_key: str, before_metrics: dict, after_metrics: dict, simulation_resolved: bool) -> bool:
    before_value = before_metrics.get(metric_key, 0)
    after_value = after_metrics.get(metric_key, 0)
    healthy = after_value < _healthy_baseline(metric_key)
    improved = after_value <= before_value * (1 - _MIN_IMPROVEMENT_FRACTION)
    if healthy or improved:
        return True
    # The action cleared a simulated condition. If the host's own reading is
    # still high (e.g. a real disk that was already 92% full), any drop from
    # the simulated value still shows the simulated fault is gone.
    return simulation_resolved and after_value < before_value


def _judge(failure_type: str, before_metrics: dict, after_metrics: dict, simulation_resolved: bool = False) -> bool:
    if failure_type in (FailureType.SERVICE_FAILURE.value, FailureType.SERVICE_DEGRADED.value):
        return after_metrics.get("service_status") == "running"
    if failure_type == FailureType.RESOURCE_SATURATION.value:
        return all(
            _metric_recovered(key, before_metrics, after_metrics, simulation_resolved)
            for key in ("cpu_usage", "memory_usage")
        )
    metric_key = _RELEVANT_METRIC.get(failure_type)
    if metric_key is None:
        return True  # 'normal' or an unrecognized type -- nothing to compare
    return _metric_recovered(metric_key, before_metrics, after_metrics, simulation_resolved)


async def verify_recovery(
    failure_type: str, before_metrics: dict, action_started_at: float, simulation_resolved: bool = False
) -> dict:
    """
    Polls fresh metrics for up to RECOVERY_STABILIZATION_WAIT_SECONDS and
    judges success against the metric relevant to this failure type.
    Never reports success just because an action ran (spec section 14).
    """
    deadline = time.monotonic() + settings.RECOVERY_STABILIZATION_WAIT_SECONDS
    await asyncio.sleep(_FIRST_CHECK_DELAY_SECONDS)

    while True:
        after_metrics = await asyncio.to_thread(MonitoringService.collect_current_metrics)
        success = _judge(failure_type, before_metrics, after_metrics, simulation_resolved)
        if success or time.monotonic() >= deadline:
            break
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    return {
        "success": success,
        "recovery_time_seconds": round(time.monotonic() - action_started_at, 2),
        "before": before_metrics,
        "after": after_metrics,
    }


def _healthy_baseline(metric_key: str) -> float:
    return {
        "cpu_usage": settings.CPU_THRESHOLD,
        "memory_usage": settings.MEMORY_THRESHOLD,
        "disk_usage": settings.DISK_THRESHOLD,
        "latency": settings.LATENCY_THRESHOLD,
        "error_rate": settings.ERROR_RATE_THRESHOLD,
    }.get(metric_key, 0.0)
