"""
AutoCura - Docker Client Wrapper

All recovery actions that touch Docker go through this module. It
never raises on connection failure -- if Docker Desktop isn't running
(a realistic state during a quick `pytest` run), callers get `None`
back and fall into their documented simulated-action fallback instead
of crashing the whole recovery pipeline over an optional dependency.

Every action elsewhere in app/recovery/ additionally checks
`is_controlled_container()` before touching any container, refusing to
act on anything outside AutoCura's own test environment.
"""

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_client = None
_client_checked = False


def get_docker_client():
    """
    Returns a docker.DockerClient, or None if the Docker daemon isn't
    reachable. Caches the result for the process lifetime (Docker
    availability doesn't usually change mid-run; restart the app if it
    does).
    """
    global _client, _client_checked
    if _client_checked:
        return _client

    _client_checked = True
    try:
        import docker  # imported lazily so the package is optional at import time
        client = docker.from_env()
        client.ping()
        _client = client
        logger.info("Docker daemon reachable -- recovery actions will run for real.")
    except Exception as exc:
        logger.warning(
            "Docker daemon not reachable (%s). Recovery actions will run in "
            "simulated mode instead of touching real containers.", exc,
        )
        _client = None

    return _client


def is_controlled_container(name: str) -> bool:
    """
    Safety guard: recovery actions must only ever touch containers that
    belong to AutoCura's own controlled test environment, never an
    arbitrary container name passed in from elsewhere.
    """
    return name.startswith(settings.AUTOCURA_CONTAINER_PREFIX)
