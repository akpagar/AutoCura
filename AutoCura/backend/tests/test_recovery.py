"""
AutoCura - Phase 5 Recovery + Simulation Tests

Runs without a live Docker daemon: every recovery action degrades to a
documented "simulated" result when Docker is unreachable (see
recovery/docker_client.py), so these tests exercise real code paths
either way.
"""

import os
import shutil

from app.recovery.cleanup_disk import cleanup_disk, fill_scratch_dir, scratch_dir
from app.recovery.docker_client import is_controlled_container
from app.recovery.restart_service import restart_container
from app.recovery.simulation_state import SimulationState


def test_is_controlled_container_enforces_prefix():
    assert is_controlled_container("autocura_test_worker_1")
    assert not is_controlled_container("some_random_container")
    assert not is_controlled_container("postgres")


def test_restart_refuses_uncontrolled_container():
    result = restart_container("not_an_autocura_container")
    assert result["success"] is False
    assert "Refused" in result["message"]


def test_restart_simulates_when_docker_unavailable():
    # In this test environment Docker is very unlikely to be reachable;
    # either way the call must not raise and must return a valid shape.
    result = restart_container("autocura_test_primary_service")
    assert "success" in result
    assert "simulated" in result
    assert "message" in result


def test_disk_cleanup_removes_created_junk():
    fill_scratch_dir(num_files=3, size_mb=1)
    path = scratch_dir()
    assert len(os.listdir(path)) >= 3

    result = cleanup_disk()
    assert result["success"] is True
    assert result["removed_items"] >= 3
    assert os.listdir(path) == []

    shutil.rmtree(path, ignore_errors=True)


def test_simulation_state_apply_and_clear():
    state = SimulationState()
    metrics = {"cpu_usage": 20, "memory_usage": 30, "disk_usage": 40, "network_in": 100, "network_out": 100, "latency": 10, "error_rate": 0.0}

    state.set_cpu(96)
    state.set_disk(97)
    applied = state.apply(dict(metrics))
    assert applied["cpu_usage"] == 96
    assert applied["disk_usage"] == 97
    assert applied["memory_usage"] == 30  # untouched

    status = state.status()
    assert "cpu_overload" in status["active_scenarios"]
    assert "disk_exhaustion" in status["active_scenarios"]

    state.clear()
    cleared = state.apply(dict(metrics))
    assert cleared == metrics


def test_resolve_scenario_clears_only_that_scenario():
    state = SimulationState()
    metrics = {"cpu_usage": 20, "memory_usage": 30, "disk_usage": 40, "network_in": 100, "network_out": 100, "latency": 10, "error_rate": 0.0}

    state.set_cpu(96)
    state.set_memory(90)

    assert state.resolve_scenario("cpu_overload") is True
    assert state.resolve_scenario("disk_exhaustion") is False  # was never active

    applied = state.apply(dict(metrics))
    assert applied["cpu_usage"] == 20  # resolved -- back to real value
    assert applied["memory_usage"] == 90  # still overridden, untouched by the cpu resolve


def test_simulate_cpu_endpoint(client):
    response = client.post("/api/simulation/cpu", json={"value": 96})
    assert response.status_code == 200
    body = response.json()
    assert body["active"]["cpu_usage"] == 96

    current = client.get("/api/monitoring/current")
    assert current.json()["cpu_usage"] == 96

    reset = client.post("/api/simulation/reset")
    assert reset.status_code == 200

    after_reset = client.get("/api/simulation/status")
    assert after_reset.json()["cpu_usage"] is None


def test_simulate_disk_creates_real_junk_and_reset_cleans_it(client):
    response = client.post("/api/simulation/disk", json={"value": 96, "junk_files": 4, "junk_file_size_mb": 1})
    assert response.status_code == 200
    path = scratch_dir()
    assert len(os.listdir(path)) >= 4

    client.post("/api/simulation/reset")
    assert os.listdir(path) == []


def test_recovery_execute_with_explicit_override(client):
    response = client.post(
        "/api/recovery/execute",
        json={"action": "cleanup_disk", "failure_type": "disk_exhaustion"},
    )
    assert response.status_code == 200
    body = response.json()
    for key in ("success", "recovery_time_seconds", "action", "before", "after"):
        assert key in body
    assert body["action"] == "cleanup_disk"


def test_recovery_history_returns_list(client):
    client.post("/api/recovery/execute", json={"action": "cleanup_disk", "failure_type": "disk_exhaustion"})
    response = client.get("/api/recovery/history?limit=5")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_recovery_status_endpoint(client):
    response = client.get("/api/recovery/status")
    assert response.status_code == 200
    body = response.json()
    assert "current_metrics" in body
    assert "active_simulations" in body


def test_restart_missing_container_is_labelled_simulation(monkeypatch):
    """Docker running but no test container created: simulated success, not a hard failure."""
    import docker
    import app.recovery.restart_service as rs

    class _Containers:
        def get(self, name):
            raise docker.errors.NotFound("no such container")

    class _FakeClient:
        containers = _Containers()

    monkeypatch.setattr(rs, "get_docker_client", lambda: _FakeClient())
    result = rs.restart_container("autocura_test_primary_service")
    assert result["success"] is True
    assert result["simulated"] is True


def test_judge_accepts_resolved_simulation_when_host_reading_still_high():
    from app.recovery.recovery_verifier import _judge

    before = {"disk_usage": 96.0}
    after = {"disk_usage": 92.0}  # real disk already above threshold, but below the simulated value
    assert _judge("disk_exhaustion", before, after, simulation_resolved=False) is False
    assert _judge("disk_exhaustion", before, after, simulation_resolved=True) is True


def test_new_simulation_scenarios_apply_and_resolve():
    state = SimulationState()
    metrics = {"cpu_usage": 20, "memory_usage": 30, "disk_usage": 40, "network_in": 1, "network_out": 1, "latency": 10, "error_rate": 0.0, "service_status": "running"}

    state.set_error_rate(0.2)
    state.set_resource_saturation(94, 91)
    state.set_service_degraded()
    applied = state.apply(dict(metrics))
    assert applied["error_rate"] == 0.2
    assert applied["cpu_usage"] == 94 and applied["memory_usage"] == 91
    assert applied["service_status"] == "degraded"

    for scenario in ("high_error_rate", "resource_saturation", "service_degraded"):
        assert state.resolve_scenario(scenario) is True
    cleared = state.apply(dict(metrics))
    assert cleared["error_rate"] == 0.0 and cleared["cpu_usage"] == 20 and cleared["service_status"] == "running"


def test_judge_covers_new_failure_types():
    from app.recovery.recovery_verifier import _judge

    assert _judge("high_error_rate", {"error_rate": 0.2}, {"error_rate": 0.0}) is True
    assert _judge("high_error_rate", {"error_rate": 0.2}, {"error_rate": 0.19}) is False
    assert _judge("service_degraded", {}, {"service_status": "running"}) is True
    assert _judge("resource_saturation", {"cpu_usage": 94, "memory_usage": 91}, {"cpu_usage": 10, "memory_usage": 90}) is False
    assert _judge("resource_saturation", {"cpu_usage": 94, "memory_usage": 91}, {"cpu_usage": 10, "memory_usage": 30}) is True
