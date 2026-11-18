"""
AutoCura - Phase 1 API Smoke Tests

Verifies the application boots, the health endpoint responds, and the
register/login flow works end-to-end. Uses the shared `client` fixture
from conftest.py (throwaway SQLite DB, lifespan entered via `with`).
"""


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "AutoCura"


def test_monitoring_health_stub(client):
    response = client.get("/api/monitoring/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_and_login_flow(client):
    register_payload = {
        "name": "Test User",
        "email": "test.user@example.com",
        "password": "StrongPassword123",
    }
    reg_response = client.post("/api/auth/register", json=register_payload)
    assert reg_response.status_code in (201, 400)  # 400 if re-run against existing db

    login_response = client.post(
        "/api/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert login_response.status_code == 200
    token_body = login_response.json()
    assert "access_token" in token_body
    assert token_body["token_type"] == "bearer"


def test_login_with_wrong_password_fails(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "test.user@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
