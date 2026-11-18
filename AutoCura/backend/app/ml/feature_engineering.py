"""
AutoCura - Feature Engineering

Derives additional signal from the cleaned/encoded monitoring columns.
Kept separate from preprocess.py: this module *adds* columns, it never
drops or validates rows.
"""

import pandas as pd

FEATURE_COLUMNS = [
    "cpu_usage", "memory_usage", "disk_usage", "network_in", "network_out",
    "process_count", "service_status_encoded", "latency", "error_rate",
    "restart_count", "resource_pressure", "network_total",
]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds:
      - resource_pressure: mean of CPU/memory/disk usage, a single
        "how stressed is this box" signal.
      - network_total: combined in+out traffic, useful when only
        overall load (not direction) matters.
    """
    df = df.copy()
    df["resource_pressure"] = df[["cpu_usage", "memory_usage", "disk_usage"]].mean(axis=1)
    df["network_total"] = df["network_in"] + df["network_out"]
    return df


def select_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Returns only the model input columns, in a fixed, documented order."""
    return df[FEATURE_COLUMNS]
