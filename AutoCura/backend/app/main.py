"""
AutoCura - FastAPI Application Entrypoint

Phase 1: project structure, database foundation, authentication, and a
health-check endpoint.
Phase 2: real-time monitoring (psutil-backed collectors + background
scheduler), alerts, and logs.
Phase 3: ML failure prediction (anomaly detection + trained classifier).
Phase 4: rule-based decision engine.
Phase 5: controlled Docker recovery actions + failure simulation.
Later phases register additional routers (dashboard) without changing
this file's structure.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alerts, auth, dashboard, decision, logs, monitoring, prediction, recovery, simulation
from app.config import settings
from app.database import init_db
from app.middleware.exception_handler import register_exception_handlers
from app.services.monitoring_service import monitoring_scheduler
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s (%s environment)", settings.APP_NAME, settings.APP_ENV)
    init_db()
    logger.info("Database tables verified/created")

    monitoring_scheduler.start()
    logger.info("Background monitoring scheduler started")

    yield

    await monitoring_scheduler.stop()
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title="AutoCura",
    description="An Autonomous Recovery Engine for Cloud Infrastructure",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(monitoring.router)
app.include_router(alerts.router)
app.include_router(logs.router)
app.include_router(prediction.router)
app.include_router(decision.router)
app.include_router(recovery.router)
app.include_router(simulation.router)
app.include_router(dashboard.router)


@app.get("/api/health", tags=["System"])
def health_check() -> dict:
    """Top-level system health check used to verify the API is running."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": "0.1.0",
    }
