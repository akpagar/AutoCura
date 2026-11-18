"""
AutoCura - ML Preprocessing

Cleans the raw monitoring dataset: drops invalid records, handles
missing values, and encodes the one categorical input feature
(service_status). Kept separate from feature_engineering.py so
"clean the data" and "derive new signal from the data" stay distinct
responsibilities.
"""

import pandas as pd

REQUIRED_COLUMNS = [
    "cpu_usage", "memory_usage", "disk_usage", "network_in", "network_out",
    "process_count", "service_status", "latency", "error_rate",
    "restart_count", "failure_type", "failure",
]

SERVICE_STATUS_MAP = {"running": 0, "degraded": 1, "stopped": 2, "unknown": 1}


def load_raw_dataset(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing_cols = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing_cols)}")
    return df


def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with missing values in required columns and out-of-range values."""
    df = df.copy()
    df = df.dropna(subset=REQUIRED_COLUMNS)

    # Remove physically invalid records (negative usage, >100% usage, etc.)
    for col in ("cpu_usage", "memory_usage", "disk_usage"):
        df = df[(df[col] >= 0) & (df[col] <= 100)]
    df = df[df["error_rate"].between(0, 1)]
    df = df[df["latency"] >= 0]
    df = df[df["network_in"] >= 0]
    df = df[df["network_out"] >= 0]
    df = df[df["restart_count"] >= 0]

    return df.reset_index(drop=True)


def encode_categorical(df: pd.DataFrame) -> pd.DataFrame:
    """Encode `service_status` as an ordinal int; unseen values fall back to 'degraded'."""
    df = df.copy()
    df["service_status_encoded"] = (
        df["service_status"].map(SERVICE_STATUS_MAP).fillna(SERVICE_STATUS_MAP["degraded"]).astype(int)
    )
    return df


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """Full preprocessing pass: clean -> encode. Feature engineering happens separately."""
    df = clean_dataset(df)
    df = encode_categorical(df)
    return df
