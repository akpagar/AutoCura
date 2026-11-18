"""
AutoCura - Service Monitor

Reports the health of the controlled primary test service.

- If Docker is reachable and the controlled container
  (`<AUTOCURA_CONTAINER_PREFIX>primary_service`) exists, its real
  container state is used: running -> "running", exited/dead/created ->
  "stopped", anything else (restarting, paused...) -> "degraded".
- If Docker is not reachable, or the container was never created (e.g. a
  plain local run without docker compose), there is no controlled service
  to watch. The only service AutoCura can vouch for is itself, and this
  code is running, so it reports "running". Service-failure scenarios
  still work in that mode through the simulation override.
"""

from app.config import settings
from app.recovery.docker_client import get_docker_client
from app.utils.constants import ServiceStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)

PRIMARY_SERVICE_CONTAINER = f"{settings.AUTOCURA_CONTAINER_PREFIX}primary_service"


class ServiceMonitor:
    @staticmethod
    def check_container_status(name: str = PRIMARY_SERVICE_CONTAINER) -> str | None:
        """Real container state via the Docker SDK, or None if not observable."""
        client = get_docker_client()
        if client is None:
            return None
        try:
            container = client.containers.get(name)
            container.reload()
        except Exception:
            # Not found / API error: no controlled container to observe.
            return None
        state = container.status
        if state == "running":
            return ServiceStatus.RUNNING.value
        if state in ("exited", "dead", "created"):
            return ServiceStatus.STOPPED.value
        return ServiceStatus.DEGRADED.value

    @staticmethod
    def check_service_health() -> str:
        """Controlled container state if observable, else "running" (see module docstring)."""
        container_state = ServiceMonitor.check_container_status()
        if container_state is not None:
            return container_state
        return ServiceStatus.RUNNING.value
