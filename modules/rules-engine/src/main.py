"""Rules-engine module FastAPI application entry point.

create_app() is the canonical application factory (LESSON-006):
all middleware, routers, and event-bus subscriptions are mounted here
so integration tests through create_app() catch regressions.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.events.dlq import DLQService, build_dlq_router
from shared.middleware import RateLimitConfig, RateLimitMiddleware, SecurityHeadersMiddleware

from .api.router import router

logger = logging.getLogger("rules_engine.main")


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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: wire event-bus consumers."""
    try:
        from shared.events.factory import get_event_bus  # noqa: PLC0415
        from .events import wire_consumers  # noqa: PLC0415

        bus = get_event_bus()
        await bus.start()
        await wire_consumers(bus)
        app.state.event_bus = bus
    except Exception:  # pragma: no cover
        logger.exception("rules_engine.consumer_wiring_failed")

    yield

    bus = getattr(app.state, "event_bus", None)
    if bus is not None:
        try:
            await bus.stop()
        except Exception:  # pragma: no cover
            pass


def create_app() -> FastAPI:
    """Application factory. Tests use this to build a fresh app per case."""
    from shared.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    environment = getattr(settings, "ENVIRONMENT", "development")
    cors_origins = getattr(settings, "CORS_ALLOW_ORIGINS", [])

    app = FastAPI(
        lifespan=lifespan,
        title="InfinityRx Rules Engine",
        version="1.0.0",
        description="Rules engine — rule types, instances, pipelines, execution, MAC pricing, regulatory rules",
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
        return {"status": "healthy", "module": "rules-engine"}

    return app


app = create_app()

__all__ = ["app", "create_app"]
