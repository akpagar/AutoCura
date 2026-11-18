"""
AutoCura - Phase 6 Dashboard + Pipeline Integration Tests
"""


def test_dashboard_summary_endpoint(client):
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    body = response.json()
    for key in (
        "system_health", "current_cpu", "current_memory", "current_disk",
        "service_status", "active_failures", "recovery_success_rate",
        "average_recovery_time_seconds",
    ):
        assert key in body
    assert body["system_health"] in ("healthy", "degraded", "critical")


def test_dashboard_metrics_series(client):
    response = client.get("/api/dashboard/metrics?limit=5")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_dashboard_failures_recoveries_alerts(client):
    for path in ("/api/dashboard/failures", "/api/dashboard/recoveries", "/api/dashboard/alerts"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert isinstance(response.json(), list), path


def test_full_pipeline_via_simulation_and_recovery(client):
    """
    End-to-end smoke test of the demo scenario from the README: inject a
    CPU-overload simulation, confirm the decision engine picks it up,
    execute recovery, then reset.
    """
    sim_resp = client.post("/api/simulation/cpu", json={"value": 97})
    assert sim_resp.status_code == 200

    decision_resp = client.post("/api/decision/evaluate")
    assert decision_resp.status_code == 200
    decision_body = decision_resp.json()
    assert decision_body["failure_type"] == "cpu_overload"
    assert decision_body["recommended_action"] == "scale_service"

    recovery_resp = client.post("/api/recovery/execute")
    assert recovery_resp.status_code == 200
    recovery_body = recovery_resp.json()
    assert recovery_body["action"] == "scale_service"
    # The recovery action resolves the simulated CPU override on success,
    # so verification should see a genuine drop back to real (low) host CPU.
    assert recovery_body["success"] is True

    reset_resp = client.post("/api/simulation/reset")
    assert reset_resp.status_code == 200
