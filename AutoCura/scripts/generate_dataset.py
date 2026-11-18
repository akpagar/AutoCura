"""
AutoCura - Synthetic Monitoring Dataset Generator

Generates a project-specific dataset shaped like real AutoCura monitoring
samples, with labeled failure classes. This is synthetic data (there is
no year of production history to mine for a student project) built from
plausible statistical distributions for each failure type -- not a claim
of real-world provenance. Class boundaries are intentionally noisy/
overlapping so the downstream classifier has a genuine (imperfect)
learning problem rather than a trivially separable one.

Usage:
    python scripts/generate_dataset.py --rows 6000
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

FAILURE_TYPES = [
    "normal",
    "cpu_overload",
    "memory_exhaustion",
    "disk_exhaustion",
    "service_failure",
    "network_degradation",
]

# Approximate class mix -- mostly healthy, as in a real system.
CLASS_WEIGHTS = {
    "normal": 0.55,
    "cpu_overload": 0.10,
    "memory_exhaustion": 0.10,
    "disk_exhaustion": 0.08,
    "service_failure": 0.09,
    "network_degradation": 0.08,
}


def _sample_row(rng: np.random.Generator, failure_type: str, timestamp: datetime) -> dict:
    """
    Draw one synthetic row for a given failure_type. Each branch uses a
    distribution centered where that failure "should" push the metric,
    with enough spread that classes overlap at the edges (realistic).
    """
    if failure_type == "normal":
        cpu = rng.normal(35, 12)
        memory = rng.normal(45, 12)
        disk = rng.normal(50, 15)
        latency = rng.normal(80, 25)
        error_rate = abs(rng.normal(0.01, 0.01))
        restart_count = rng.poisson(0.02)
        process_count = rng.integers(80, 160)

    elif failure_type == "cpu_overload":
        cpu = rng.normal(92, 6)
        memory = rng.normal(55, 15)
        disk = rng.normal(50, 15)
        latency = rng.normal(320, 90)
        error_rate = abs(rng.normal(0.03, 0.02))
        restart_count = rng.poisson(0.05)
        process_count = rng.integers(140, 260)

    elif failure_type == "memory_exhaustion":
        cpu = rng.normal(55, 15)
        memory = rng.normal(93, 5)
        disk = rng.normal(55, 15)
        latency = rng.normal(280, 80)
        error_rate = abs(rng.normal(0.04, 0.02))
        restart_count = rng.poisson(0.15)
        process_count = rng.integers(120, 220)

    elif failure_type == "disk_exhaustion":
        cpu = rng.normal(40, 15)
        memory = rng.normal(50, 15)
        disk = rng.normal(95, 4)
        latency = rng.normal(220, 70)
        error_rate = abs(rng.normal(0.05, 0.03))
        restart_count = rng.poisson(0.05)
        process_count = rng.integers(80, 160)

    elif failure_type == "service_failure":
        cpu = rng.normal(30, 15)
        memory = rng.normal(45, 15)
        disk = rng.normal(50, 15)
        latency = rng.normal(600, 200)
        error_rate = abs(rng.normal(0.35, 0.15))
        restart_count = rng.poisson(1.2)
        process_count = rng.integers(20, 90)

    else:  # network_degradation
        cpu = rng.normal(40, 15)
        memory = rng.normal(50, 15)
        disk = rng.normal(50, 15)
        latency = rng.normal(750, 220)
        error_rate = abs(rng.normal(0.12, 0.06))
        restart_count = rng.poisson(0.1)
        process_count = rng.integers(80, 160)

    cpu = float(np.clip(cpu, 0, 100))
    memory = float(np.clip(memory, 0, 100))
    disk = float(np.clip(disk, 0, 100))
    latency = float(max(latency, 1))
    error_rate = float(np.clip(error_rate, 0, 1))

    network_in = float(abs(rng.normal(5_000_000, 2_000_000)))
    network_out = float(abs(rng.normal(3_000_000, 1_500_000)))
    if failure_type == "network_degradation":
        network_in *= rng.uniform(0.2, 0.5)
        network_out *= rng.uniform(0.2, 0.5)

    service_status = "running"
    if failure_type == "service_failure":
        service_status = rng.choice(["stopped", "degraded"], p=[0.6, 0.4])
    elif failure_type in ("cpu_overload", "memory_exhaustion", "network_degradation"):
        service_status = rng.choice(["running", "degraded"], p=[0.7, 0.3])

    failure = 0 if failure_type == "normal" else 1

    return {
        "timestamp": timestamp.isoformat(),
        "cpu_usage": round(cpu, 2),
        "memory_usage": round(memory, 2),
        "disk_usage": round(disk, 2),
        "network_in": round(network_in, 2),
        "network_out": round(network_out, 2),
        "process_count": int(process_count),
        "service_status": service_status,
        "latency": round(latency, 2),
        "error_rate": round(error_rate, 4),
        "restart_count": int(restart_count),
        "failure_type": failure_type,
        "failure": failure,
    }


def generate_dataset(n_rows: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    types = list(CLASS_WEIGHTS.keys())
    weights = list(CLASS_WEIGHTS.values())
    chosen_types = rng.choice(types, size=n_rows, p=weights)

    start = datetime.now(UTC) - timedelta(seconds=10 * n_rows)
    rows = []
    for i, failure_type in enumerate(chosen_types):
        ts = start + timedelta(seconds=10 * i)
        rows.append(_sample_row(rng, str(failure_type), ts))

    df = pd.DataFrame(rows)
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the AutoCura synthetic monitoring dataset.")
    parser.add_argument("--rows", type=int, default=6000, help="Number of rows to generate.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    backend_dir = os.path.join(os.path.dirname(__file__), "..", "backend")
    raw_dir = os.path.join(backend_dir, "datasets", "raw")
    os.makedirs(raw_dir, exist_ok=True)

    df = generate_dataset(args.rows, seed=args.seed)
    out_path = os.path.join(raw_dir, "monitoring_dataset.csv")
    df.to_csv(out_path, index=False)

    print(f"Generated {len(df)} rows -> {out_path}")
    print(df["failure_type"].value_counts())


if __name__ == "__main__":
    sys.exit(main() or 0)
