"""
AutoCura - Failure Simulation API

Lets the dashboard trigger safe, controlled test failures so the full
observe->analyze->predict->decide->act->verify->learn loop can be
demonstrated live. CPU/memory/disk/network scenarios only ever change
what MonitoringService.collect_current_metrics() *reports* (see
recovery/simulation_state.py's docstring for why); service-failure
actually stops a controlled Docker container, since that is safe to do
for real.

POST /api/simulation/cpu             - simulate CPU overload
POST /api/simulation/memory          - simulate memory exhaustion
POST /api/simulation/disk            - simulate disk exhaustion (also creates real scratch-dir junk to clean up)
POST /api/simulation/network         - simulate network degradation
POST /api/simulation/error-rate       - simulate an error-rate spike
POST /api/simulation/resource-saturation - simulate CPU + memory saturation together
POST /api/simulation/service-degraded - simulate a degraded (not stopped) service
POST /api/simulation/service-failure - actually stop a controlled test container
POST /api/simulation/reset           - clear all active simulations
GET  /api/simulation/status          - currently active simulations
"""

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from app.config import settings
from app.recovery.cleanup_disk import fill_scratch_dir
from app.recovery.restart_service import restart_container
from app.recovery.simulation_state import simulation_state
from app.services.pipeline_service import run_pipeline_sync
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/simulation", tags=["Failure Simulation"])

_PRIMARY_SERVICE_CONTAINER = f"{settings.AUTOCURA_CONTAINER_PREFIX}primary_service"


class CpuSimulationRequest(BaseModel):
    value: float = 95.0


class MemorySimulationRequest(BaseModel):
    value: float = 92.0


class DiskSimulationRequest(BaseModel):
    value: float = 95.0
    junk_files: int = 10
    junk_file_size_mb: int = 2


class ErrorRateSimulationRequest(BaseModel):
    value: float = 0.18


class SaturationSimulationRequest(BaseModel):
    cpu: float = 94.0
    memory: float = 91.0


class NetworkSimulationRequest(BaseModel):
    latency_ms: float = 800.0
    throughput_multiplier: float = 0.3


def _kick_pipeline(background: BackgroundTasks) -> None:
    """
    Runs the automated detect -> decide -> act -> verify chain right after
    the response is sent, instead of waiting for the next scheduled
    monitoring tick. It is the same chain the scheduler runs (same
    AUTO_RECOVERY_ENABLED switch, same lock, same retry limit).
    """
    if settings.AUTO_RECOVERY_ENABLED:
        background.add_task(run_pipeline_sync, ignore_cooldown=True)


@router.post("/cpu")
def simulate_cpu(payload: CpuSimulationRequest, background: BackgroundTasks) -> dict:
    simulation_state.set_cpu(payload.value)
    logger.warning("Simulation: CPU overload injected (%.1f%%)", payload.value)
    _kick_pipeline(background)
    return {"message": f"Simulated CPU usage set to {payload.value}%.", "active": simulation_state.status()}


@router.post("/memory")
def simulate_memory(payload: MemorySimulationRequest, background: BackgroundTasks) -> dict:
    simulation_state.set_memory(payload.value)
    logger.warning("Simulation: memory exhaustion injected (%.1f%%)", payload.value)
    _kick_pipeline(background)
    return {"message": f"Simulated memory usage set to {payload.value}%.", "active": simulation_state.status()}


@router.post("/disk")
def simulate_disk(payload: DiskSimulationRequest, background: BackgroundTasks) -> dict:
    simulation_state.set_disk(payload.value)
    fill_info = fill_scratch_dir(num_files=payload.junk_files, size_mb=payload.junk_file_size_mb)
    logger.warning("Simulation: disk exhaustion injected (%.1f%%)", payload.value)
    _kick_pipeline(background)
    return {
        "message": f"Simulated disk usage set to {payload.value}%, with real junk files created for cleanup to act on.",
        "junk_files": fill_info,
        "active": simulation_state.status(),
    }


@router.post("/network")
def simulate_network(payload: NetworkSimulationRequest, background: BackgroundTasks) -> dict:
    simulation_state.set_network(latency=payload.latency_ms, multiplier=payload.throughput_multiplier)
    logger.warning("Simulation: network degradation injected (latency=%.0fms)", payload.latency_ms)
    _kick_pipeline(background)
    return {"message": f"Simulated network latency set to {payload.latency_ms}ms.", "active": simulation_state.status()}


@router.post("/error-rate")
def simulate_error_rate(payload: ErrorRateSimulationRequest, background: BackgroundTasks) -> dict:
    simulation_state.set_error_rate(payload.value)
    logger.warning("Simulation: error-rate spike injected (%.2f)", payload.value)
    _kick_pipeline(background)
    return {"message": f"Simulated error rate set to {payload.value:.0%}.", "active": simulation_state.status()}


@router.post("/resource-saturation")
def simulate_resource_saturation(payload: SaturationSimulationRequest, background: BackgroundTasks) -> dict:
    simulation_state.set_resource_saturation(payload.cpu, payload.memory)
    logger.warning("Simulation: CPU+memory saturation injected (cpu=%.1f mem=%.1f)", payload.cpu, payload.memory)
    _kick_pipeline(background)
    return {"message": f"Simulated CPU {payload.cpu}% and memory {payload.memory}%.", "active": simulation_state.status()}


@router.post("/service-degraded")
def simulate_service_degraded(background: BackgroundTasks) -> dict:
    simulation_state.set_service_degraded()
    logger.warning("Simulation: service degradation injected")
    _kick_pipeline(background)
    return {"message": "Simulated service degradation (service up but unhealthy).", "active": simulation_state.status()}


@router.post("/service-failure")
def simulate_service_failure(background: BackgroundTasks) -> dict:
    """
    Stops the controlled primary-service container when Docker and the
    container are available (a real, safe action -- the monitor then reads
    the container's real state). Otherwise the outage is simulated, so the
    scenario always does something visible instead of silently doing nothing.
    """
    from app.recovery.docker_client import get_docker_client, is_controlled_container

    if not is_controlled_container(_PRIMARY_SERVICE_CONTAINER):
        return {"message": "Refused: target is not a controlled container.", "simulated": False}

    client = get_docker_client()
    if client is not None:
        import docker
        try:
            container = client.containers.get(_PRIMARY_SERVICE_CONTAINER)
            container.stop(timeout=3)
            simulation_state.mark_scenario("service_failure")
            logger.warning("Simulation: stopped controlled container '%s'", _PRIMARY_SERVICE_CONTAINER)
            _kick_pipeline(background)
            return {"message": f"Stopped controlled container '{_PRIMARY_SERVICE_CONTAINER}'.", "simulated": False}
        except docker.errors.NotFound:
            reason = f"container '{_PRIMARY_SERVICE_CONTAINER}' not found (run `docker compose up`)"
        except Exception as exc:
            logger.exception("Could not stop controlled container for simulation")
            reason = f"Docker error: {exc}"
    else:
        reason = "Docker not reachable"

    simulation_state.set_service_down("stopped")
    logger.warning("Simulation: service outage simulated (%s)", reason)
    _kick_pipeline(background)
    return {"message": f"Simulated service outage ({reason}).", "simulated": True}


@router.post("/reset")
def reset_simulation() -> dict:
    simulation_state.clear()
    from app.recovery.cleanup_disk import cleanup_disk
    cleanup_result = cleanup_disk()

    # Best-effort: bring the primary service back up if it was stopped for the demo.
    try:
        restart_container(_PRIMARY_SERVICE_CONTAINER)
    except Exception:
        logger.exception("Could not restart primary service container during simulation reset")

    return {"message": "All simulations cleared.", "disk_cleanup": cleanup_result}


@router.get("/status")
def simulation_status() -> dict:
    return simulation_state.status()
