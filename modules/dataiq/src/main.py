"""DataIQ module FastAPI application factory.

LESSON-006: every router must be mounted through create_app() and verified
by integration tests — not just tested in isolation.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared.events.dlq import DLQService, build_dlq_router
from shared.middleware import RateLimitConfig, RateLimitMiddleware, SecurityHeadersMiddleware

from src.api.router import router

logger = logging.getLogger("dataiq.main")


class _EmptyDLQRepository:
    async def list(self, **_kwargs):
        return []

    async def get(self, _entry_id):
        return None

    async def save(self, _entry) -> None:  # pragma: no cover
        return None


async def _get_dlq_service() -> DLQService:
    return DLQService(repository=_EmptyDLQRepository())


async def _get_dlq_permissions() -> set[str]:
    return set()


async def _build_redis_or_fail():
    """Build an aioredis client from REDIS_URL, or raise RuntimeError if missing.

    CR-01 v2 BLOCK-1 fix: dataiq event consumers require a real Redis client
    for KPI counter updates. Proceeding with None silently drops all counters.
    Fail fast at startup so the problem is visible immediately.
    """
    import redis.asyncio as redis_async  # noqa: PLC0415
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        raise RuntimeError(
            "REDIS_URL environment variable is required for dataiq event consumers "
            "but is not set. Set it to a valid Redis connection URL (e.g., "
            "redis://localhost:6379/0)."
        )
    return redis_async.from_url(redis_url, decode_responses=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Wire event consumers with real Redis client at startup.

    CR-01 v2 BLOCK-1 fix: redis=None was silently no-opping all KPI counter
    updates. Now we fail fast at startup if REDIS_URL is missing.
    """
    redis_client = await _build_redis_or_fail()

    from shared.events.factory import get_event_bus, reset_event_bus  # noqa: PLC0415
    from src.events import wire_consumers  # noqa: PLC0415

    bus = get_event_bus()
    try:
        await bus.start()
        await wire_consumers(bus, redis=redis_client)
        logger.info("dataiq service started", extra={"svc_name": "dataiq"})
        yield
    finally:
        await bus.stop()
        reset_event_bus()
        await redis_client.aclose()
        logger.info("dataiq service stopped", extra={"svc_name": "dataiq"})


def create_app() -> FastAPI:
    """Create and configure the DataIQ FastAPI application."""
    from shared.config import get_settings  # noqa: PLC0415 — deferred to allow test override

    settings = get_settings()
    environment = getattr(settings, "ENVIRONMENT", "development")
    cors_origins = getattr(settings, "CORS_ALLOW_ORIGINS", [])

    app = FastAPI(
        lifespan=lifespan,
        title="InfinityRx DataIQ",
        version="1.0.0",
        description=(
            "DataIQ analytics and business intelligence module — "
            "real-time KPIs, SPC anomaly detection, drug trend decomposition, "
            "claims repricing, PostGIS geo analytics"
        ),
        openapi_url="/openapi.json" if environment != "production" else None,
        docs_url="/docs" if environment != "production" else None,
        redoc_url="/redoc" if environment != "production" else None,
    )

    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(RateLimitMiddleware, config=RateLimitConfig())
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(router)
    app.include_router(
        build_dlq_router(
            get_service=_get_dlq_service,
            get_permissions=_get_dlq_permissions,
        )
    )

    @app.get("/health")
    async def health() -> dict:
        from sqlalchemy import text  # noqa: PLC0415
        from shared.db.session import get_sessionmaker  # noqa: PLC0415
        from shared.config import get_settings  # noqa: PLC0415, F811
        import redis.asyncio as redis_async  # noqa: PLC0415
        from fastapi.responses import JSONResponse  # noqa: PLC0415

        db_status: str
        db_critical_failed: bool
        try:
            maker = get_sessionmaker()
            async with maker() as session:
                await session.execute(text("SELECT 1"))
            db_status = "ok"
            db_critical_failed = False
        except Exception as exc:  # noqa: BLE001
            db_status = f"error: {type(exc).__name__}"
            db_critical_failed = True

        redis_status: str
        try:
            _settings = get_settings()
            _redis = redis_async.from_url(_settings.REDIS_URL)
            try:
                await _redis.ping()
                redis_status = "ok"
            finally:
                await _redis.aclose()
        except Exception as exc:  # noqa: BLE001
            redis_status = f"error: {type(exc).__name__}"

        dependencies: dict[str, str] = {"database": db_status, "redis": redis_status}

        if db_critical_failed:
            overall = "unhealthy"
        elif any(v != "ok" for v in dependencies.values()):
            overall = "degraded"
        else:
            overall = "healthy"

        status_code = 503 if db_critical_failed else 200
        return JSONResponse(
            status_code=status_code,
            content={"status": overall, "module": "dataiq", "dependencies": dependencies},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = str(uuid.uuid4())
        logger.error(
            "unhandled_exception",
            extra={
                "svc_correlation_id": correlation_id,
                "svc_path": request.url.path,
            },
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "correlation_id": correlation_id,
                }
            },
        )

    return app


app = create_app()

__all__ = ["app", "create_app"]
