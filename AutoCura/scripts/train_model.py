"""
AutoCura - Train Model CLI

Thin wrapper around app.ml.train + app.ml.anomaly so training can be
triggered from the project root without remembering the module path.

Usage (from backend/, with the venv active):
    python ../scripts/train_model.py
"""

import os
import sys

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, BACKEND_DIR)

from app.ml.anomaly import train_isolation_forest  # noqa: E402
from app.ml.train import train_and_select_best  # noqa: E402


def main() -> None:
    raw_path = os.path.join(BACKEND_DIR, "datasets", "raw", "monitoring_dataset.csv")
    processed_path = os.path.join(BACKEND_DIR, "datasets", "processed", "monitoring_dataset_processed.csv")

    if not os.path.exists(raw_path):
        raise SystemExit(f"Raw dataset not found at {raw_path}. Run scripts/generate_dataset.py first.")

    print("Training failure classifier...")
    metadata = train_and_select_best(raw_path, processed_path)
    print(f"Selected model: {metadata['selected_model']}")
    print(f"Test accuracy: {metadata['metrics']['accuracy']}  F1: {metadata['metrics']['f1_score']}")

    print("Training Isolation Forest for anomaly detection...")
    train_isolation_forest(processed_path)
    from app.config import settings
    print(f"Done. Artifacts saved under {settings.model_dir_path}")


if __name__ == "__main__":
    main()
