"""
AutoCura - Phase 2 Monitoring Tests

Covers the monitoring/alerts/logs endpoints and the underlying collector
+ threshold-alerting logic. Uses the shared `client` fixture (throwaway
SQLite DB) from conftest.py.
"""

from app.monitoring.cpu_monitor import CPUMonitor
from app.monitoring.disk_monitor import DiskMonitor
from app.monitoring.memory_monitor import MemoryMonitor
from app.monitoring.network_monitor import NetworkMonitor
from app.services.alert_service import AlertService
from app.services.monitoring_service import MonitoringService


def test_get_current_metrics(client):
    response = client.get("/api/monitoring/current")
    assert response.status_code == 200
    data = response.json()
    assert "cpu_usage" in data
    assert "memory_usage" in data
    assert "disk_usage" in data
    assert "service_status" in data


def test_monitoring_history_returns_list(client):
    # Record one sample directly so history has something to return.
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        MonitoringService.record_metrics(db)
    finally:
        db.close()

    response = client.get("/api/monitoring/history?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert "cpu_usage" in body[0]


def test_monitoring_start_stop(client):
    stop_resp = client.post("/api/monitoring/stop")
    assert stop_resp.status_code == 200

    start_resp = client.post("/api/monitoring/start")
    assert start_resp.status_code == 200

    health_resp = client.get("/api/monitoring/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["monitoring_active"] is True

    # Leave it stopped so it doesn't keep running after the test session.
    client.post("/api/monitoring/stop")


def test_get_alerts_and_logs(client):
    alert_resp = client.get("/api/alerts")
    assert alert_resp.status_code == 200
    assert isinstance(alert_resp.json(), list)

    logs_resp = client.get("/api/logs")
    assert logs_resp.status_code == 200
    assert isinstance(logs_resp.json(), list)


def test_alert_created_on_threshold_breach(client):
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        alert = AlertService.create_alert(
            db, "HIGH_CPU", "HIGH", "CPU utilization exceeded threshold: 99.0%"
        )
        assert alert.id is not None
        assert alert.acknowledged is False
    finally:
        db.close()

    list_resp = client.get("/api/alerts")
    assert list_resp.status_code == 200
    alerts = list_resp.json()
    assert any(a["alert_type"] == "HIGH_CPU" for a in alerts)


def test_acknowledge_alert(client):
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        alert = AlertService.create_alert(db, "HIGH_MEMORY", "HIGH", "Memory high")
        alert_id = alert.id
    finally:
        db.close()

    ack_resp = client.post(f"/api/alerts/{alert_id}/acknowledge")
    assert ack_resp.status_code == 200

    missing_resp = client.post("/api/alerts/999999/acknowledge")
    assert missing_resp.status_code == 404


def test_individual_collectors_return_expected_shape():
    assert isinstance(CPUMonitor.get_metrics(), float)

    memory = MemoryMonitor.get_metrics()
    assert "percentage" in memory

    disk = DiskMonitor.get_metrics()
    assert "percentage" in disk

    network = NetworkMonitor.get_metrics()
    assert "bytes_sent" in network
    assert "bytes_recv" in network
