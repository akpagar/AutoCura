"""
AutoCura - Application Configuration

Centralized configuration loaded from environment variables (.env file).
No secrets or thresholds should be hard-coded elsewhere in the codebase --
import `settings` from this module instead.
"""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# The backend/ directory (parent of app/), used to anchor any relative
# filesystem paths in settings below to a fixed location instead of
# trusting the process's current working directory -- CWD varies
# depending on whether the caller is uvicorn (run from backend/),
# scripts/train_model.py (run from the project root), pytest, etc.
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    # ---- App ----
    APP_NAME: str = "AutoCura"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api"

    # ---- Database ----
    DATABASE_URL: str = "postgresql+psycopg2://autocura:autocura@localhost:5432/autocura"

    # ---- Security / Auth ----
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ---- Monitoring thresholds (configurable, not hard-coded in logic) ----
    CPU_THRESHOLD: float = 85.0
    MEMORY_THRESHOLD: float = 85.0
    DISK_THRESHOLD: float = 90.0
    LATENCY_THRESHOLD: float = 500.0       # milliseconds
    ERROR_RATE_THRESHOLD: float = 0.05     # 5%

    # ---- Monitoring scheduler ----
    MONITORING_INTERVAL_SECONDS: int = 5

    # ---- Recovery policy ----
    RECOVERY_RETRY_LIMIT: int = 3
    RECOVERY_STABILIZATION_WAIT_SECONDS: int = 4
    # Pause between DETECTING a failure and ACTING on it in the automated
    # pipeline. The failure is already recorded (dashboard health turns
    # critical, an alert is raised) during this window, so the incident is
    # visible before recovery starts. Set to 0 for instant recovery.
    RECOVERY_RESPONSE_DELAY_SECONDS: float = 8.0

    # ---- Automated end-to-end pipeline (Phase 6) ----
    # Whether the background monitoring scheduler automatically runs
    # decide->act->verify after each collection cycle, not just on
    # demand via the API. Safe to leave on: every recovery action
    # already refuses to touch anything outside AutoCura's own
    # controlled test containers.
    AUTO_RECOVERY_ENABLED: bool = True
    # Minimum time between automated recovery attempts, regardless of
    # scheduler frequency -- prevents a persistent simulated/real
    # failure from triggering a new recovery attempt on every single
    # monitoring tick.
    AUTO_RECOVERY_COOLDOWN_SECONDS: int = 30

    # ---- Docker (controlled test environment only) ----
    DOCKER_BASE_URL: str = "unix://var/run/docker.sock"
    AUTOCURA_CONTAINER_PREFIX: str = "autocura_test_"

    # ---- ML ----
    # Stored as a plain relative-looking default for readability in .env,
    # but always resolved to an absolute path via `model_dir_path` below --
    # never used directly for filesystem access.
    MODEL_DIR: str = "trained_models"
    ACTIVE_MODEL_NAME: str = "failure_classifier.joblib"

    # ---- CORS ----
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    model_config = SettingsConfigDict(
        # Absolute path -- .env is always found regardless of which
        # directory a script (train_model.py, pytest, uvicorn) was
        # actually launched from.
        env_file=os.path.join(_BACKEND_ROOT, ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def model_dir_path(self) -> str:
        """Absolute path to the trained-model directory, regardless of CWD."""
        if os.path.isabs(self.MODEL_DIR):
            return self.MODEL_DIR
        return os.path.join(_BACKEND_ROOT, self.MODEL_DIR)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton so the .env file is parsed only once."""
    return Settings()


settings = get_settings()
