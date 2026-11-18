"""
AutoCura - Real-Time Prediction

Loads the trained pipeline (scaler + classifier) via model_manager and
turns a single incoming metrics sample into a failure prediction. This
is the module the prediction API and the decision engine both call.
"""

import pandas as pd

from app.ml.feature_engineering import engineer_features
from app.ml.model_manager import LoadedModel, load_model
from app.ml.preprocess import SERVICE_STATUS_MAP
from app.utils.constants import Severity

# Cache the loaded model in-process; reloaded on first use after a
# server restart or after /api/prediction/reload is called.
_cached_model: LoadedModel | None = None


def get_loaded_model(force_reload: bool = False) -> LoadedModel:
    global _cached_model
    if _cached_model is None or force_reload:
        _cached_model = load_model()
    return _cached_model


def _severity_from_probability(probability: float) -> str:
    if probability >= 0.85:
        return Severity.CRITICAL.value
    if probability >= 0.65:
        return Severity.HIGH.value
    if probability >= 0.35:
        return Severity.MEDIUM.value
    return Severity.LOW.value


def predict_from_metrics(metrics: dict) -> dict:
    """
    metrics: a dict shaped like MonitoringService.collect_current_metrics()
    plus optional 'process_count' / 'restart_count' (defaulted if absent,
    since the live monitoring pipeline does not yet track these -- see
    docs/api_contracts.md).

    Returns: {failure_type, failure_probability, confidence, severity}
    """
    loaded = get_loaded_model()

    row = {
        "cpu_usage": metrics.get("cpu_usage", 0.0),
        "memory_usage": metrics.get("memory_usage", 0.0),
        "disk_usage": metrics.get("disk_usage", 0.0),
        "network_in": metrics.get("network_in", 0.0),
        "network_out": metrics.get("network_out", 0.0),
        "process_count": metrics.get("process_count", 100),
        "service_status": metrics.get("service_status", "running"),
        "latency": metrics.get("latency", 0.0),
        "error_rate": metrics.get("error_rate", 0.0),
        "restart_count": metrics.get("restart_count", 0),
    }
    df = pd.DataFrame([row])
    df["service_status_encoded"] = (
        df["service_status"].map(SERVICE_STATUS_MAP).fillna(SERVICE_STATUS_MAP["degraded"]).astype(int)
    )
    df = engineer_features(df)
    X = df[loaded.feature_columns]

    probabilities = loaded.model.predict_proba(X)[0]
    predicted_index = int(probabilities.argmax())
    predicted_label = loaded.label_encoder.inverse_transform([predicted_index])[0]
    confidence = float(probabilities[predicted_index])

    # failure_probability = 1 - P(normal), i.e. "how likely is *some* failure"
    normal_index = list(loaded.label_encoder.classes_).index("normal") if "normal" in loaded.label_encoder.classes_ else None
    failure_probability = float(1 - probabilities[normal_index]) if normal_index is not None else confidence

    severity = Severity.LOW.value if predicted_label == "normal" else _severity_from_probability(failure_probability)

    return {
        "failure_type": str(predicted_label),
        "failure_probability": round(failure_probability, 4),
        "confidence": round(confidence, 4),
        "severity": severity,
    }
