"""Rebate Management module FastAPI application entry point.

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

logger = logging.getLogger("rebate_management.main")


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
    """Startup: wire event-bus consumers."""
    try:
        from shared.observability.slow_query import install_slow_query_logger  # noqa: PLC0415

        from .db.session import _get_engine  # noqa: PLC0415

        engine = _get_engine()
        if engine:
            install_slow_query_logger(engine, threshold_ms=1000)
    except Exception:
        logger.debug("Slow-query logger not installed (optional)")

    try:
        from shared.events.factory import get_event_bus  # noqa: PLC0415
        from .events.consumers import wire_consumers  # noqa: PLC0415

        bus = get_event_bus()
        wire_consumers(bus)
        logger.info("Rebate management event consumers wired")
    except Exception:
        logger.debug("Event bus not available — consumers not wired")

    yield


def create_app() -> FastAPI:
    """Application factory for the rebate-management module."""
    app = FastAPI(
        title="InfinityRx Rebate Management",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Security headers (MUST be mounted — LESSON-006 / security.md)
    app.add_middleware(SecurityHeadersMiddleware)

    # Rate limiting
    app.add_middleware(
        RateLimitMiddleware,
        config=RateLimitConfig(),
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # DLQ router (MUST be mounted — security.md)
    dlq_router = build_dlq_router(
        get_service=_get_dlq_service,
        get_permissions=_get_dlq_permissions,
    )
    app.include_router(dlq_router)

    # Module API routes
    app.include_router(router)

    return app


# Module-level app instance for uvicorn (src.main:app)
app = create_app()
