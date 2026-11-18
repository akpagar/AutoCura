"""
AutoCura - Background Task Scheduler

A minimal async periodic-task runner used to run monitoring collection
(and later prediction/decision cycles) without blocking the FastAPI
event loop and without introducing a heavyweight dependency (e.g. Celery).
"""

import asyncio
from collections.abc import Awaitable, Callable

from app.utils.logger import get_logger

logger = get_logger(__name__)


class PeriodicTask:
    """
    Runs `func` every `interval_seconds` in the background until stopped.
    `func` may be sync or async; sync functions are run in a thread so
    they never block the event loop.
    """

    def __init__(self, name: str, func: Callable[[], Awaitable[None] | None], interval_seconds: int):
        self.name = name
        self._func = func
        self._interval = interval_seconds
        self._task: asyncio.Task | None = None
        self._running = False

    async def _run_once(self) -> None:
        if asyncio.iscoroutinefunction(self._func):
            await self._func()
        else:
            # Run sync functions (e.g. blocking DB writes) in a worker
            # thread so they never block the event loop.
            await asyncio.to_thread(self._func)

    async def _loop(self) -> None:
        logger.info("Starting periodic task '%s' every %ss", self.name, self._interval)
        while self._running:
            try:
                await self._run_once()
            except Exception:
                logger.exception("Periodic task '%s' raised an exception", self.name)
            await asyncio.sleep(self._interval)

    def start(self) -> None:
        """
        Must be called from a running event loop (i.e. from an `async def`
        caller) -- asyncio.create_task() requires one. If a caller invokes
        this from a sync context (e.g. a sync FastAPI endpoint, which
        FastAPI runs in a worker thread with no event loop), raise a clear
        error instead of letting asyncio's cryptic "no running event loop"
        surface as an unexplained 500.
        """
        if self._running:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError as exc:
            raise RuntimeError(
                f"PeriodicTask '{self.name}'.start() must be called from an "
                "async context (no running event loop was found here)."
            ) from exc
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Stopped periodic task '%s'", self.name)

    @property
    def is_running(self) -> bool:
        return self._running
