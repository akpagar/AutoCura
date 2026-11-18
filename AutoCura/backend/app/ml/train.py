"""
AutoCura - Model Training Pipeline

Loads the raw dataset, preprocesses it, engineers features, trains
multiple candidate classifiers, evaluates each on a held-out test split,
and saves the best-performing one (by weighted F1) via model_manager.

Run as: python -m app.ml.train  (from backend/, with the venv active)
"""

import argparse
import os

from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from app.ml.evaluate import evaluate_model
from app.ml.feature_engineering import FEATURE_COLUMNS, engineer_features, select_feature_matrix
from app.ml.model_manager import model_path, save_model
from app.ml.preprocess import load_raw_dataset, preprocess
from app.utils.logger import get_logger

logger = get_logger(__name__)

CANDIDATE_MODELS = {
    "logistic_regression": LogisticRegression(max_iter=1000),
    "random_forest": RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42),
    "gradient_boosting": GradientBoostingClassifier(n_estimators=150, max_depth=3, random_state=42),
}


def _prepare_dataset(raw_path: str, processed_path: str):
    raw_df = load_raw_dataset(raw_path)
    clean_df = preprocess(raw_df)
    featured_df = engineer_features(clean_df)

    os.makedirs(os.path.dirname(processed_path), exist_ok=True)
    featured_df.to_csv(processed_path, index=False)

    X = select_feature_matrix(featured_df)
    y_raw = featured_df["failure_type"]

    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(y_raw)

    return X, y, label_encoder, featured_df


def train_and_select_best(raw_path: str, processed_path: str, test_size: float = 0.2, random_state: int = 42) -> dict:
    X, y, label_encoder, featured_df = _prepare_dataset(raw_path, processed_path)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    class_names = list(label_encoder.classes_)

    results = {}
    for name, model in CANDIDATE_MODELS.items():
        logger.info("Training candidate model: %s", name)
        model.fit(X_train_scaled, y_train)
        metrics = evaluate_model(model, X_test_scaled, y_test, class_names)
        results[name] = {"model": model, "metrics": metrics}
        logger.info(
            "%s -> accuracy=%.4f f1=%.4f", name, metrics["accuracy"], metrics["f1_score"]
        )

    best_name = max(results, key=lambda n: results[n]["metrics"]["f1_score"])
    best_model = results[best_name]["model"]
    best_metrics = results[best_name]["metrics"]

    # Wrap the scaler + model together so predict.py only needs one artifact.
    from sklearn.pipeline import Pipeline
    pipeline = Pipeline([("scaler", scaler), ("classifier", best_model)])

    metadata = {
        "selected_model": best_name,
        "metrics": best_metrics,
        "all_candidate_metrics": {n: r["metrics"] for n, r in results.items()},
        "class_names": class_names,
        "training_rows": int(len(featured_df)),
    }

    save_model(pipeline, label_encoder, FEATURE_COLUMNS, metadata)
    logger.info("Selected model: %s (saved to %s)", best_name, model_path())

    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the AutoCura failure-prediction model.")
    parser.add_argument("--raw", default="datasets/raw/monitoring_dataset.csv")
    parser.add_argument("--processed", default="datasets/processed/monitoring_dataset_processed.csv")
    args = parser.parse_args()

    if not os.path.exists(args.raw):
        raise SystemExit(
            f"Raw dataset not found at {args.raw}. Run scripts/generate_dataset.py first."
        )

    metadata = train_and_select_best(args.raw, args.processed)

    print(f"Selected model: {metadata['selected_model']}")
    print(f"Test accuracy:  {metadata['metrics']['accuracy']}")
    print(f"Test F1 score:  {metadata['metrics']['f1_score']}")
    print(f"Test precision: {metadata['metrics']['precision']}")
    print(f"Test recall:    {metadata['metrics']['recall']}")


if __name__ == "__main__":
    main()
