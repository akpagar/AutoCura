"""
AutoCura - Phase 3 ML / Prediction Tests

Covers preprocessing, model loading (via the shared trained_test_model
fixture in conftest.py), and prediction output shape/correctness.
"""

import pandas as pd

from app.ml.model_manager import model_exists
from app.ml.preprocess import SERVICE_STATUS_MAP, clean_dataset, encode_categorical


def test_model_exists_after_fixture_training(client):
    # `client` depends on trained_test_model, so requesting it guarantees
    # training has already happened by the time this assertion runs.
    assert model_exists()


def test_clean_dataset_drops_invalid_rows():
    df = pd.DataFrame([
        {"cpu_usage": 50, "memory_usage": 50, "disk_usage": 50, "network_in": 100,
         "network_out": 100, "process_count": 100, "service_status": "running",
         "latency": 50, "error_rate": 0.01, "restart_count": 0,
         "failure_type": "normal", "failure": 0},
        {"cpu_usage": 150, "memory_usage": 50, "disk_usage": 50, "network_in": 100,  # invalid: >100%
         "network_out": 100, "process_count": 100, "service_status": "running",
         "latency": 50, "error_rate": 0.01, "restart_count": 0,
         "failure_type": "normal", "failure": 0},
    ])
    cleaned = clean_dataset(df)
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["cpu_usage"] == 50


def test_encode_categorical_maps_known_and_unknown_status():
    df = pd.DataFrame([{"service_status": "running"}, {"service_status": "totally_unknown"}])
    encoded = encode_categorical(df)
    assert encoded.iloc[0]["service_status_encoded"] == SERVICE_STATUS_MAP["running"]
    assert encoded.iloc[1]["service_status_encoded"] == SERVICE_STATUS_MAP["degraded"]


def test_predict_endpoint_returns_valid_shape(client):
    response = client.post("/api/prediction/predict", json={})
    assert response.status_code == 200
    body = response.json()
    for key in ("failure_type", "failure_probability", "confidence", "severity", "anomaly"):
        assert key in body
    assert 0.0 <= body["failure_probability"] <= 1.0
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["severity"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def test_predict_with_cpu_overload_override(client):
    payload = {
        "cpu_usage": 96,
        "memory_usage": 55,
        "disk_usage": 50,
        "network_in": 5_000_000,
        "network_out": 3_000_000,
        "latency": 320,
        "error_rate": 0.03,
        "service_status": "running",
    }
    response = client.post("/api/prediction/predict", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["failure_type"] == "cpu_overload"
    assert body["severity"] in ("HIGH", "CRITICAL")


def test_prediction_history_returns_list(client):
    client.post("/api/prediction/predict", json={})
    response = client.get("/api/prediction/history?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert "predicted_failure_type" in body[0]
