"""
AutoCura - Model Manager

Handles saving/loading the trained classifier, its label encoder, and
its evaluation metadata via joblib. All model I/O goes through this
module so nothing else needs to know the on-disk file layout.
"""

import json
import os
from dataclasses import dataclass
from typing import Any

import joblib

from app.config import settings


@dataclass
class LoadedModel:
    model: Any
    label_encoder: Any
    feature_columns: list[str]
    metadata: dict


def _model_dir() -> str:
    # Always an absolute path anchored to backend/ (see
    # Settings.model_dir_path), regardless of the caller's CWD -- this
    # used to be settings.MODEL_DIR directly, which silently resolved
    # relative to whatever directory the process happened to be
    # launched from and could save/load from two different locations
    # depending on whether training was run via scripts/train_model.py
    # (from the project root) or the app itself (from backend/).
    return settings.model_dir_path


def model_path() -> str:
    return os.path.join(_model_dir(), settings.ACTIVE_MODEL_NAME)


def label_encoder_path() -> str:
    return os.path.join(_model_dir(), "label_encoder.joblib")


def metadata_path() -> str:
    return os.path.join(_model_dir(), "model_metadata.json")


def save_model(model: Any, label_encoder: Any, feature_columns: list[str], metadata: dict) -> None:
    os.makedirs(_model_dir(), exist_ok=True)
    joblib.dump(model, model_path())
    joblib.dump(label_encoder, label_encoder_path())
    full_metadata = {**metadata, "feature_columns": feature_columns}
    with open(metadata_path(), "w") as fh:
        json.dump(full_metadata, fh, indent=2)


def load_model() -> LoadedModel:
    if not os.path.exists(model_path()):
        raise FileNotFoundError(
            f"No trained model found at {model_path()}. Run `python -m app.ml.train` "
            "(or scripts/train_model.py) first."
        )
    model = joblib.load(model_path())
    label_encoder = joblib.load(label_encoder_path())
    with open(metadata_path()) as fh:
        metadata = json.load(fh)
    return LoadedModel(
        model=model,
        label_encoder=label_encoder,
        feature_columns=metadata["feature_columns"],
        metadata=metadata,
    )


def model_exists() -> bool:
    return os.path.exists(model_path())
