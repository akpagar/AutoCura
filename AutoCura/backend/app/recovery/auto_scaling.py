"""
AutoCura - Auto-Scaling Recovery Action

Plain Docker containers (not Swarm/Kubernetes) have no native "scale"
verb, so this operates over a fixed, pre-defined pool of worker
containers (autocura_test_worker_1..N, defined in
infrastructure/docker-compose.yml) and starts/stops members of that
pool to reach a target replica count -- exactly the "safe simulation
within a controlled pool" the spec explicitly allows when true elastic
scaling isn't available.
"""

from app.config import settings
from app.recovery.docker_client import get_docker_client, is_controlled_container
from app.utils.logger import get_logger

logger = get_logger(__name__)

MAX_WORKER_POOL_SIZE = 3


def _worker_name(index: int) -> str:
    return f"{settings.AUTOCURA_CONTAINER_PREFIX}worker_{index}"


def scale_service(target_replicas: int) -> dict:
    target_replicas = max(0, min(target_replicas, MAX_WORKER_POOL_SIZE))
    client = get_docker_client()

    if client is None:
        logger.info("Simulating scale to %d replicas (Docker unavailable).", target_replicas)
        return {
            "success": True,
            "simulated": True,
            "target_replicas": target_replicas,
            "message": f"Simulated scale to {target_replicas} replicas (Docker daemon not reachable).",
        }

    import docker
    started, stopped, missing = [], [], []
    for i in range(1, MAX_WORKER_POOL_SIZE + 1):
        name = _worker_name(i)
        if not is_controlled_container(name):
            continue  # unreachable given the prefix is applied above, but keep the guard explicit
        try:
            container = client.containers.get(name)
        except docker.errors.NotFound:
            missing.append(name)
            continue

        should_run = i <= target_replicas
        is_running = container.status == "running"
        if should_run and not is_running:
            container.start()
            started.append(name)
        elif not should_run and is_running:
            container.stop(timeout=2)
            stopped.append(name)

    message = f"Scaled worker pool to {target_replicas} replicas."
    if missing:
        message += f" Missing containers (not created by `docker compose up`): {missing}."

    return {
        "success": True,
        "simulated": False,
        "target_replicas": target_replicas,
        "started": started,
        "stopped": stopped,
        "missing": missing,
        "message": message,
    }
