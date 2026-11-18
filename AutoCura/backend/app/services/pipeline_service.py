"""
AutoCura - Automated Pipeline Orchestrator

This is what makes AutoCura self-healing rather than just a monitoring
dashboard with an on-demand API (spec section 22/39's core identity:
OBSERVE -> ANALYZE -> PREDICT -> DECIDE -> ACT -> VERIFY -> LEARN).
The background monitoring scheduler calls run_pipeline_sync() after
every collection cycle; this module decides whether it's time to run
the full decide->act->verify chain automatically.

Deliberately does NOT import app.services.monitoring_service at module
load time -- it's imported lazily inside the functions that need it,
since monitoring_service.py imports this module's caller in the other
direction (scheduler -> pipeline -> recovery -> monitoring_service),
and importing it eagerly here would create a circular import.
"""

import asyncio

from app.config import settings
from app.database import SessionLocal
from app.ml.model_manager import model_exists
from app.models.prediction import Failure
from app.utils.helpers import seconds_since
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Logged once (not every 10s) while no trained model exists yet, so the
# console doesn't fill with repeated tracebacks before the user has run
# scripts/train_model.py -- this is an expected, common first-run state,
# not a real failure.
_warned_no_model = False


def _cooldown_active(db) -> bool:
    """
    True only after a recovery that did NOT succeed (status "escalated"),
    for AUTO_RECOVERY_COOLDOWN_SECONDS. This is the guard against
    endlessly re-running a recovery that keeps failing (spec section 14).
    A successfully resolved failure needs no cooldown, so the next
    incident is handled immediately.
    """
    latest = db.query(Failure).order_by(Failure.detected_at.desc()).first()
    if latest is None or latest.status != "escalated":
        return False
    return seconds_since(latest.detected_at) < settings.AUTO_RECOVERY_COOLDOWN_SECONDS


def run_pipeline_sync(ignore_cooldown: bool = False) -> None:
    """
    Called from the (sync, worker-thread) monitoring scheduler tick.
    Runs the async recovery chain via asyncio.run() -- safe here because
    this executes in its own worker thread with no other event loop
    already running on it.
    """
    global _warned_no_model

    if not settings.AUTO_RECOVERY_ENABLED:
        return

    if not model_exists():
        if not _warned_no_model:
            logger.info(
                "Automated recovery pipeline is waiting for a trained model. "
                "Run `python scripts/generate_dataset.py` then `python scripts/train_model.py` "
                "from the project root to enable it (this message won't repeat)."
            )
            _warned_no_model = True
        return
    _warned_no_model = False

    from app.services.recovery_service import RecoveryService

    db = SessionLocal()
    try:
        if not ignore_cooldown and _cooldown_active(db):
            return

        result = asyncio.run(RecoveryService.execute(
            db, wait_for_lock=ignore_cooldown, response_delay=settings.RECOVERY_RESPONSE_DELAY_SECONDS,
        ))

        if result.get("action") != "no_action":
            logger.info(
                "Automated pipeline: failure_type=%s action=%s success=%s recovery_time=%.2fs",
                result.get("failure_type"), result.get("action"),
                result.get("success"), result.get("recovery_time_seconds", 0.0),
            )
    except Exception:
        logger.exception("Automated recovery pipeline cycle failed")
    finally:
        db.close()
