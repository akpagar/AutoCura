"""
AutoCura - Failure Simulation State

Per spec section 3's safety constraint, AutoCura must never perform
dangerous operations on the user's actual OS -- so CPU/memory/network
"failures" are not induced by actually stressing the host's real CPU
or RAM (which would be unsafe on a student's own laptop and highly
OS-dependent to do portably). Instead, this module holds a simple
in-memory override that MonitoringService.collect_current_metrics()
applies before returning a sample, making the *reported* metrics
reflect a simulated failure. This still exercises the full observe ->
predict -> decide -> act -> verify loop end-to-end and is honestly
labeled as a simulation, not a real fault injection.

Service-failure simulation is the one exception -- see api/simulation.py
-- since stopping a controlled Docker container is a real, safe action.
"""

import threading
from dataclasses import dataclass, field


@dataclass
class SimulationOverride:
    cpu_usage: float | None = None
    memory_usage: float | None = None
    disk_usage: float | None = None
    latency: float | None = None
    error_rate: float | None = None
    network_multiplier: float | None = None
    service_status: str | None = None
    active_scenarios: list[str] = field(default_factory=list)


class SimulationState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._override = SimulationOverride()

    def set_cpu(self, value: float) -> None:
        with self._lock:
            self._override.cpu_usage = value
            self._track("cpu_overload")

    def set_memory(self, value: float) -> None:
        with self._lock:
            self._override.memory_usage = value
            self._track("memory_exhaustion")

    def set_disk(self, value: float) -> None:
        with self._lock:
            self._override.disk_usage = value
            self._track("disk_exhaustion")

    def set_network(self, latency: float, multiplier: float) -> None:
        with self._lock:
            self._override.latency = latency
            self._override.network_multiplier = multiplier
            self._track("network_degradation")

    def set_service_down(self, status: str = "stopped") -> None:
        """Simulated service outage (used when there is no real container to stop)."""
        with self._lock:
            self._override.service_status = status
            self._track("service_failure")

    def set_error_rate(self, value: float) -> None:
        with self._lock:
            self._override.error_rate = value
            self._track("high_error_rate")

    def set_resource_saturation(self, cpu: float, memory: float) -> None:
        with self._lock:
            self._override.cpu_usage = cpu
            self._override.memory_usage = memory
            self._track("resource_saturation")

    def set_service_degraded(self) -> None:
        with self._lock:
            self._override.service_status = "degraded"
            self._track("service_degraded")

    def _track(self, scenario: str) -> None:
        if scenario not in self._override.active_scenarios:
            self._override.active_scenarios.append(scenario)

    def mark_scenario(self, scenario: str) -> None:
        """Records a scenario as active without changing any metric override (e.g. service-failure, which acts on a real container instead)."""
        with self._lock:
            self._track(scenario)

    def resolve_scenario(self, scenario: str) -> bool:
        """
        Called by the recovery engine when an action targeting this
        scenario completes, so verification can observe genuine
        improvement instead of the simulated failure persisting forever
        regardless of what recovery action ran. Returns True if the
        scenario was actually active (and is now cleared).

        This is the one place recovery code is allowed to touch
        simulation state -- representing "the corrective action
        resolved the simulated condition," not a real host-level
        change (there is no real change to represent; the failure was
        never real to begin with).
        """
        with self._lock:
            if scenario not in self._override.active_scenarios:
                return False
            self._override.active_scenarios.remove(scenario)
            if scenario == "cpu_overload":
                self._override.cpu_usage = None
            elif scenario == "memory_exhaustion":
                self._override.memory_usage = None
            elif scenario == "disk_exhaustion":
                self._override.disk_usage = None
            elif scenario == "network_degradation":
                self._override.latency = None
                self._override.network_multiplier = None
            elif scenario in ("service_failure", "service_degraded"):
                self._override.service_status = None
            elif scenario == "high_error_rate":
                self._override.error_rate = None
            elif scenario == "resource_saturation":
                self._override.cpu_usage = None
                self._override.memory_usage = None
            return True

    def clear(self) -> None:
        with self._lock:
            self._override = SimulationOverride()

    # Secondary symptoms that accompany each simulated incident, matching
    # how the training data was generated (a CPU overload also slows the
    # service down, a failed service also errors, and so on). Applied only
    # while the scenario is active, and only as a floor, so they never
    # lower a real reading. Each stays below its alert threshold except
    # where the scenario is itself about that metric.
    _COMPANIONS = {
        "cpu_overload": {"latency": 320.0, "error_rate": 0.03},
        "memory_exhaustion": {"latency": 280.0, "error_rate": 0.04},
        "disk_exhaustion": {"latency": 220.0, "error_rate": 0.045},
        "network_degradation": {"error_rate": 0.04},
        "service_failure": {"latency": 600.0, "error_rate": 0.2},
        "high_error_rate": {"latency": 180.0},
        "service_degraded": {"latency": 350.0, "error_rate": 0.03},
        "resource_saturation": {"latency": 450.0, "error_rate": 0.04},
    }

    def apply(self, metrics: dict) -> dict:
        with self._lock:
            ov = self._override
            for scenario in ov.active_scenarios:
                for key, floor in self._COMPANIONS.get(scenario, {}).items():
                    metrics[key] = max(metrics.get(key, 0.0), floor)
            if ov.service_status is not None:
                metrics["service_status"] = ov.service_status
            if ov.cpu_usage is not None:
                metrics["cpu_usage"] = ov.cpu_usage
            if ov.memory_usage is not None:
                metrics["memory_usage"] = ov.memory_usage
            if ov.disk_usage is not None:
                metrics["disk_usage"] = ov.disk_usage
            if ov.latency is not None:
                metrics["latency"] = ov.latency
            if ov.error_rate is not None:
                metrics["error_rate"] = ov.error_rate
            if ov.network_multiplier is not None:
                metrics["network_in"] *= ov.network_multiplier
                metrics["network_out"] *= ov.network_multiplier
            return metrics

    def status(self) -> dict:
        with self._lock:
            return {
                "active_scenarios": list(self._override.active_scenarios),
                "cpu_usage": self._override.cpu_usage,
                "memory_usage": self._override.memory_usage,
                "disk_usage": self._override.disk_usage,
                "latency": self._override.latency,
                "error_rate": self._override.error_rate,
                "network_multiplier": self._override.network_multiplier,
                "service_status": self._override.service_status,
            }


# Process-wide singleton -- deliberately simple (no persistence) since
# simulation state should reset on every server restart.
simulation_state = SimulationState()
