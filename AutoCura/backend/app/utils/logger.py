"""
AutoCura - Structured Logging

Provides a single configured logger factory used across the application.
Never log secrets, passwords, or tokens.
"""

import logging
import sys

from app.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root_logger() -> None:
    global _configured
    if _configured:
        return

    level = logging.DEBUG if settings.DEBUG else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root = logging.getLogger("autocura")
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a namespaced logger, e.g. get_logger(__name__).
    All AutoCura loggers live under the 'autocura' namespace.
    """
    _configure_root_logger()
    return logging.getLogger(f"autocura.{name}")
