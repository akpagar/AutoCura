"""
AutoCura - Shared Test Fixtures

Points the app at a throwaway SQLite database and a throwaway MODEL_DIR
so the test suite doesn't require a live PostgreSQL instance or a
pre-trained model on disk. Yields a TestClient inside a `with` block so
the FastAPI lifespan (DB init + monitoring scheduler start/stop) runs
around each test module.
"""

import os
import shutil
import sys
import tempfile

_TEST_MODEL_DIR = tempfile.mkdtemp(prefix="autocura_test_models_")

os.environ["DATABASE_URL"] = "sqlite:///./test_autocura.db"
# Keep the background monitoring loop from firing mid-test-run.
os.environ["MONITORING_INTERVAL_SECONDS"] = "3600"
# Train-and-load a real model from a temp dir rather than relying on
# whatever (if anything) exists in the real backend/trained_models/.
os.environ["MODEL_DIR"] = _TEST_MODEL_DIR
# Keep recovery verification fast in tests -- these default to 5s wait
# x 3 retries in production, which would make the test suite noticeably
# slow for no benefit here.
os.environ["RECOVERY_STABILIZATION_WAIT_SECONDS"] = "1"
os.environ["RECOVERY_RESPONSE_DELAY_SECONDS"] = "0"
os.environ["RECOVERY_RETRY_LIMIT"] = "2"

import pytest
from fastapi.testclient import TestClient

# Make scripts/generate_dataset.py importable from the test session.
_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
sys.path.insert(0, _SCRIPTS_DIR)

from app.database import engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def trained_test_model():
    """
    Trains a real (small, fast) model into MODEL_DIR before any test
    runs, so /api/prediction and /api/decision have something to load.
    Uses the same generator/trainer the real project uses -- just on a
    smaller dataset for test speed.
    """
    from generate_dataset import generate_dataset

    from app.ml.anomaly import train_isolation_forest
    from app.ml.train import train_and_select_best

    raw_path = os.path.join(_TEST_MODEL_DIR, "raw_dataset.csv")
    processed_path = os.path.join(_TEST_MODEL_DIR, "processed_dataset.csv")

    df = generate_dataset(1000, seed=1)
    df.to_csv(raw_path, index=False)

    train_and_select_best(raw_path, processed_path)
    train_isolation_forest(processed_path)

    yield

    shutil.rmtree(_TEST_MODEL_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def client(trained_test_model):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    # Dispose the connection pool first -- on Windows, SQLite keeps the
    # file locked as long as any pooled connection handle is open, and
    # os.remove() below would otherwise fail with WinError 32.
    engine.dispose()
    if os.path.exists("test_autocura.db"):
        os.remove("test_autocura.db")
