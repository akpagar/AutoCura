"""
AutoCura - Restart Service Recovery Action

Restarts a named controlled test container via the Docker SDK. Never
executes an arbitrary shell command -- uses the SDK's typed
`container.restart()` call, and refuses any container name outside
AutoCura's own test-container prefix.
"""

from app.recovery.docker_client import get_docker_client, is_controlled_container
from app.utils.logger import get_logger

logger = get_logger(__name__)


def restart_container(container_name: str) -> dict:
    if not is_controlled_container(container_name):
        return {
            "success": False,
            "simulated": False,
            "message": f"Refused: '{container_name}' is not a controlled AutoCura test container.",
        }

    client = get_docker_client()
    if client is None:
        logger.info("Simulating restart of '%s' (Docker unavailable).", container_name)
        return {
            "success": True,
            "simulated": True,
            "message": f"Simulated restart of '{container_name}' (Docker daemon not reachable).",
        }

    try:
        import docker
        container = client.containers.get(container_name)
        container.restart(timeout=2)
        logger.info("Restarted container '%s'.", container_name)
        return {
            "success": True,
            "simulated": False,
            "message": f"Container '{container_name}' restarted successfully.",
        }
    except docker.errors.NotFound:
        # Docker is running but the controlled test container was never
        # created (e.g. `docker compose up` was not run). There is nothing
        # real to restart, so this is a labelled simulation, not a failure.
        logger.info("Simulating restart of '%s' (container not found).", container_name)
        return {
            "success": True,
            "simulated": True,
            "message": f"Simulated restart of '{container_name}' (container not found; run `docker compose up` for real restarts).",
        }
    except Exception as exc:
        logger.exception("Failed to restart container '%s'", container_name)
        return {"success": False, "simulated": False, "message": f"Restart failed: {exc}"}
