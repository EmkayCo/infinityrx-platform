"""Billing module FastAPI application entry point.

create_app() is the canonical application factory (LESSON-006):
all middleware, routers, and event-bus subscriptions are mounted here
so integration tests through create_app() catch regressions.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.events.dlq import DLQService, build_dlq_router
from shared.middleware import RateLimitConfig, RateLimitMiddleware, SecurityHeadersMiddleware

from .api.router import router
from .api.uploads import router as uploads_router
from .api.inbox import router as inbox_router

logger = logging.getLogger("billing.main")


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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: install slow-query logger and wire event-bus consumers."""
    try:
        from src.db.session import _get_engine  # noqa: PLC0415
        from shared.observability.slow_query import install_slow_query_logger  # noqa: PLC0415
        threshold = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "1000"))
        install_slow_query_logger(_get_engine(), threshold_ms=threshold)
    except Exception:  # pragma: no cover - best-effort; missing DB is fine in tests
        pass

    # CR-01/CR-11: subscribe consumers to the event bus with idempotency wrappers.
    try:
        from shared.events.factory import get_event_bus  # noqa: PLC0415
        from .events import wire_consumers  # noqa: PLC0415
        bus = get_event_bus()
        await bus.start()
        await wire_consumers(bus)
        app.state.event_bus = bus
    except Exception:  # pragma: no cover - best-effort; missing broker is fine in tests
        logger.exception("billing.consumer_wiring_failed")

    yield

    bus = getattr(app.state, "event_bus", None)
    if bus is not None:
        try:
            await bus.stop()
        except Exception:  # pragma: no cover
            pass


def create_app() -> FastAPI:
    """Application factory. Tests use this to build a fresh app per case."""
    from shared.config import get_settings  # noqa: PLC0415 - deferred to allow test override

    settings = get_settings()
    environment = getattr(settings, "ENVIRONMENT", "development")
    cors_origins = getattr(settings, "CORS_ALLOW_ORIGINS", [])

    app = FastAPI(
        lifespan=lifespan,
        title="InfinityRx Billing",
        version="1.0.0",
        description="Billing module - claims, AP, AR, invoicing, journal, program monitoring",
        openapi_url="/openapi.json" if environment != "production" else None,
        docs_url="/docs" if environment != "production" else None,
        redoc_url="/redoc" if environment != "production" else None,
    )

    # LESSON-006: all middleware mounted here so integration tests catch regressions.
    # CORS must be added before other middleware.
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
    app.include_router(uploads_router)
    app.include_router(inbox_router)
    app.include_router(
        build_dlq_router(
            get_service=_get_dlq_service,
            get_permissions=_get_dlq_permissions,
        )
    )

    @app.get("/health")
    async def health() -> dict:
        from sqlalchemy import text  # noqa: PLC0415
        from src.db.session import _get_engine  # noqa: PLC0415
        from fastapi.responses import JSONResponse  # noqa: PLC0415

        db_status: str
        db_critical_failed: bool
        try:
            engine = _get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_status = "ok"
            db_critical_failed = False
        except Exception as exc:  # noqa: BLE001
            db_status = f"error: {type(exc).__name__}"
            db_critical_failed = True

        dependencies: dict[str, str] = {"database": db_status}

        if db_critical_failed:
            overall = "unhealthy"
        elif any(v != "ok" for v in dependencies.values()):
            overall = "degraded"
        else:
            overall = "healthy"

        status_code = 503 if db_critical_failed else 200
        return JSONResponse(
            status_code=status_code,
            content={"status": overall, "module": "billing", "dependencies": dependencies},
        )

    return app


app = create_app()

__all__ = ["app", "create_app"]

