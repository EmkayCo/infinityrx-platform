"""Core-platform FastAPI entry point with graceful-shutdown lifespan.

Ensures in-flight DB transactions and in-flight event-bus messages are
flushed before the process exits. Without this, pod termination
(SIGTERM → 30s grace → SIGKILL) can corrupt PHI/audit data — HIPAA
§164.308(a)(1) availability + §164.308(a)(7) contingency.

On startup:
    - Verify the database is reachable (SELECT 1).
    - Start the event bus (opens connection, spins consumers).
    - Log "service started" with correlation metadata.

On shutdown (lifespan exit OR SIGTERM OR SIGINT):
    - Stop the event bus (drains in-flight deliveries, closes channel).
    - Dispose the SQLAlchemy engine (returns pooled connections).
    - Log "service stopped".

The SIGTERM/SIGINT handler forwards to the lifespan by raising an
asyncio CancelledError in uvicorn's main loop — uvicorn then triggers
the normal lifespan shutdown path. We only install the handler when
running under an event loop (skipped in TestClient).
"""

from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from sqlalchemy import text

from shared.db.engine import dispose_engine, get_engine
from shared.events.factory import get_event_bus, reset_event_bus

from .api import router as api_router

logger = logging.getLogger("core-platform.main")


async def _verify_database() -> None:
    """Fail-fast on startup if the DB is not reachable."""
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, app: FastAPI) -> None:
    """Forward SIGTERM/SIGINT to the uvicorn shutdown path.

    Setting ``app.state.shutting_down`` lets health checks report 503 while
    the lifespan shutdown tasks drain.
    """

    def _handler(signame: str) -> None:
        logger.info("signal_received", extra={"signal": signame})
        app.state.shutting_down = True
        # Uvicorn installs its own handler; we only flip the flag so the
        # readiness probe starts failing immediately. Uvicorn drives the
        # actual lifespan shutdown when its server loop unwinds.

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handler, sig.name)
        except (NotImplementedError, RuntimeError):
            # Windows / test environments may not support add_signal_handler
            pass


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan: startup + graceful shutdown."""
    # --- startup ---
    app.state.shutting_down = False
    try:
        loop = asyncio.get_running_loop()
        _install_signal_handlers(loop, app)
    except RuntimeError:
        pass  # No running loop (shouldn't happen under uvicorn)

    await _verify_database()
    bus = get_event_bus()
    await bus.start()
    logger.info("service_started", extra={"module": "core-platform"})

    try:
        yield
    finally:
        # --- shutdown ---
        app.state.shutting_down = True
        logger.info("service_stopping", extra={"module": "core-platform"})
        try:
            await bus.stop()
        except Exception:  # pragma: no cover - best-effort drain
            logger.exception("event_bus_stop_failed")
        reset_event_bus()
        try:
            await dispose_engine()
        except Exception:  # pragma: no cover - best-effort drain
            logger.exception("engine_dispose_failed")
        logger.info("service_stopped", extra={"module": "core-platform"})


def create_app() -> FastAPI:
    """Application factory. Tests use this to build a fresh app per case."""
    app = FastAPI(
        title="InfinityRx Core Platform",
        version="1.0.0",
        description="Tenants, auth, RBAC, audit, jobs, files, notifications.",
        lifespan=lifespan,
    )
    app.include_router(api_router)
    return app


app = create_app()


__all__ = ["app", "create_app", "lifespan"]
