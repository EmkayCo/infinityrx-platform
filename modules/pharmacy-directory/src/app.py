"""Pharmacy-directory FastAPI application factory.

All middleware and routers mounted here per LESSON-006 — integration contract
requires every primitive to be tested through create_app().
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from shared.db.engine import dispose_engine, get_engine
from shared.events.dlq import DLQService, build_dlq_router
from shared.events.factory import get_event_bus, reset_event_bus
from sqlalchemy import text

from src.api.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from src.api.router import router as pharmacy_router
from src.events.consumers import (
    handle_fwa_credentialing_risk_elevated,
    handle_fwa_pharmacy_risk_elevated,
)

logger = logging.getLogger("pharmacy-directory.app")


async def _verify_database() -> None:
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.shutting_down = False
    await _verify_database()
    bus = get_event_bus()
    await bus.start()
    await bus.subscribe("fwa.credentialing_risk_elevated", handle_fwa_credentialing_risk_elevated)
    await bus.subscribe("fwa.pharmacy_risk_elevated", handle_fwa_pharmacy_risk_elevated)
    logger.info("service_started", extra={"service": "pharmacy-directory"})
    try:
        yield
    finally:
        app.state.shutting_down = True
        logger.info("service_stopping", extra={"service": "pharmacy-directory"})
        try:
            await bus.stop()
        except Exception:  # pragma: no cover
            logger.exception("event_bus_stop_failed")
        reset_event_bus()
        try:
            await dispose_engine()
        except Exception:  # pragma: no cover
            logger.exception("engine_dispose_failed")
        logger.info("service_stopped", extra={"service": "pharmacy-directory"})


class _EmptyDLQRepository:
    async def list(self, **_kwargs):  # type: ignore[no-untyped-def]
        return []

    async def get(self, _entry_id):  # type: ignore[no-untyped-def]
        return None

    async def save(self, _entry) -> None:  # pragma: no cover
        return None


async def _get_dlq_service() -> DLQService:
    return DLQService(repository=_EmptyDLQRepository())


async def _get_dlq_permissions() -> set[str]:
    return set()


def create_app() -> FastAPI:
    """Application factory. Tests drive middleware integration through this."""
    app = FastAPI(
        title="InfinityRx Pharmacy Directory",
        version="1.0.0",
        description="Pharmacy directory — lookup, networks, credentialing, performance.",
        lifespan=lifespan,
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(pharmacy_router)
    app.include_router(
        build_dlq_router(
            get_service=_get_dlq_service,
            get_permissions=_get_dlq_permissions,
        )
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "module": "pharmacy-directory"}

    return app


app = create_app()

__all__ = ["app", "create_app", "lifespan"]
