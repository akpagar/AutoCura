"""
AutoCura - Anomaly Detection

Deliberately separate from the failure-type classifier (predict.py):
this module answers "is this sample unusual at all?" using two
independent signals --
  1. configurable threshold checks (fast, interpretable, no training needed)
  2. an Isolation Forest fit on the historical/processed dataset (catches
     unusual combinations that no single threshold would flag)

Combining both gives a threshold-anomaly OR a model-anomaly path, since
either one firing is a legitimate reason to look closer.
"""

import os

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.config import settings

_ISOLATION_FOREST_FEATURES = [
    "cpu_usage", "memory_usage", "disk_usage", "latency", "error_rate",
]


def _isolation_forest_path() -> str:
    return os.path.join(settings.model_dir_path, "isolation_forest.joblib")


def train_isolation_forest(processed_dataset_path: str, contamination: float = 0.15) -> None:
    df = pd.read_csv(processed_dataset_path)
    X = df[_ISOLATION_FOREST_FEATURES]
    model = IsolationForest(contamination=contamination, random_state=42)
    model.fit(X)
    os.makedirs(settings.model_dir_path, exist_ok=True)
    joblib.dump(model, _isolation_forest_path())
    invalidate_isolation_forest_cache()


def _load_isolation_forest() -> IsolationForest | None:
    path = _isolation_forest_path()
    if not os.path.exists(path):
        return None
    return joblib.load(path)


# Process-wide cache, mirroring predict.py's _cached_model pattern.
# Without this, every single anomaly check re-reads and deserializes the
# .joblib file from disk -- measured at ~4x slower than reusing an
# in-memory instance, for a model that never changes at runtime.
_cached_isolation_forest: IsolationForest | None = None
_cache_checked = False


def _get_cached_isolation_forest() -> IsolationForest | None:
    global _cached_isolation_forest, _cache_checked
    if not _cache_checked:
        _cached_isolation_forest = _load_isolation_forest()
        _cache_checked = True
    return _cached_isolation_forest


def invalidate_isolation_forest_cache() -> None:
    """Call after train_isolation_forest() retrains, so the next check picks up the new model."""
    global _cached_isolation_forest, _cache_checked
    _cached_isolation_forest = None
    _cache_checked = False


def check_thresholds(metrics: dict) -> list[str]:
    """Returns the list of threshold rules that fired (empty if none)."""
    reasons = []
    if metrics.get("cpu_usage", 0) > settings.CPU_THRESHOLD:
        reasons.append(f"cpu_usage {metrics['cpu_usage']} > {settings.CPU_THRESHOLD}")
    if metrics.get("memory_usage", 0) > settings.MEMORY_THRESHOLD:
        reasons.append(f"memory_usage {metrics['memory_usage']} > {settings.MEMORY_THRESHOLD}")
    if metrics.get("disk_usage", 0) > settings.DISK_THRESHOLD:
        reasons.append(f"disk_usage {metrics['disk_usage']} > {settings.DISK_THRESHOLD}")
    if metrics.get("latency", 0) > settings.LATENCY_THRESHOLD:
        reasons.append(f"latency {metrics['latency']} > {settings.LATENCY_THRESHOLD}")
    if metrics.get("error_rate", 0) > settings.ERROR_RATE_THRESHOLD:
        reasons.append(f"error_rate {metrics['error_rate']} > {settings.ERROR_RATE_THRESHOLD}")
    return reasons


def check_isolation_forest(metrics: dict) -> bool | None:
    """
    Returns True if the Isolation Forest flags this sample as an outlier,
    False if not, or None if no trained Isolation Forest model exists yet
    (train.py's `train_isolation_forest` must be run at least once).
    """
    model = _get_cached_isolation_forest()
    if model is None:
        return None
    row = {k: metrics.get(k, 0.0) for k in _ISOLATION_FOREST_FEATURES}
    X = pd.DataFrame([row])[_ISOLATION_FOREST_FEATURES]
    prediction = model.predict(X)[0]  # -1 = anomaly, 1 = normal
    return bool(prediction == -1)


def detect_anomaly(metrics: dict) -> dict:
    threshold_reasons = check_thresholds(metrics)
    isolation_flag = check_isolation_forest(metrics)

    is_anomaly = bool(threshold_reasons) or bool(isolation_flag)
    return {
        "is_anomaly": is_anomaly,
        "threshold_reasons": threshold_reasons,
        "isolation_forest_flagged": isolation_flag,
    }
