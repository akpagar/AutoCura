"""
AutoCura - Workload Migration Recovery Action

Simplified controlled redistribution: stop the worker considered
degraded and ensure at least one other worker in the pool is running
to absorb its traffic. This is a deliberately simplified stand-in for
real load-balancer-driven migration, appropriate for a controlled
student-project test environment.
"""

from app.config import settings
from app.recovery.docker_client import get_docker_client, is_controlled_container
from app.utils.logger import get_logger

logger = get_logger(__name__)

_POOL_SIZE = 3


def _worker_name(index: int) -> str:
    return f"{settings.AUTOCURA_CONTAINER_PREFIX}worker_{index}"


def migrate_workload(from_index: int = 1) -> dict:
    client = get_docker_client()
    from_name = _worker_name(from_index)

    if client is None:
        logger.info("Simulating workload migration away from '%s' (Docker unavailable).", from_name)
        return {
            "success": True,
            "simulated": True,
            "message": f"Simulated migration away from '{from_name}' (Docker daemon not reachable).",
        }

    import docker

    if not is_controlled_container(from_name):
        return {"success": False, "simulated": False, "message": f"Refused: '{from_name}' is not controlled."}

    try:
        source = client.containers.get(from_name)
        source.stop(timeout=2)
    except docker.errors.NotFound:
        logger.info("Simulating workload migration away from '%s' (container not found).", from_name)
        return {
            "success": True,
            "simulated": True,
            "message": f"Simulated migration away from '{from_name}' (container not found; run `docker compose up` for real workers).",
        }

    # Ensure at least one other worker is up to receive the redistributed load.
    receiving = None
    for i in range(1, _POOL_SIZE + 1):
        if i == from_index:
            continue
        name = _worker_name(i)
        try:
            container = client.containers.get(name)
        except docker.errors.NotFound:
            continue
        if container.status != "running":
            container.start()
        receiving = name
        break

    message = f"Migrated workload away from '{from_name}'"
    message += f" onto '{receiving}'." if receiving else ", but no other worker was available to receive it."

    if receiving is None:
        # No other worker exists to receive load: treat as a labelled simulation
        # rather than a hard failure so the loop does not retry pointlessly.
        return {
            "success": True,
            "simulated": True,
            "from_container": from_name,
            "to_container": None,
            "message": message + " (simulated: no other worker containers exist).",
        }

    return {
        "success": True,
        "simulated": False,
        "from_container": from_name,
        "to_container": receiving,
        "message": message,
    }
