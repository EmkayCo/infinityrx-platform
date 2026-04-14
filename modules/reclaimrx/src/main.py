"""ReclaimRx FastAPI application entry point.

create_app() is the canonical application factory (LESSON-006):
all middleware, routers, and event-bus subscriptions must be mounted here
so integration tests through create_app() catch regressions.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.events.dlq import DLQService, build_dlq_router
from shared.middleware import RateLimitConfig, RateLimitMiddleware, SecurityHeadersMiddleware

from .api.router import router

logger = logging.getLogger("reclaimrx.main")


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


def create_app() -> FastAPI:
    """Application factory. Tests use this to build a fresh app per case."""
    from shared.config import get_settings  # noqa: PLC0415 — deferred to allow test override

    settings = get_settings()
    environment = getattr(settings, "ENVIRONMENT", "development")
    cors_origins = getattr(settings, "CORS_ALLOW_ORIGINS", [])

    app = FastAPI(
        title="InfinityRx ReclaimRx",
        version="1.0.0",
        description="FWA detection, ML scoring, graph analysis, and recovery estimation.",
        openapi_url="/openapi.json" if environment != "production" else None,
        docs_url="/docs" if environment != "production" else None,
        redoc_url="/redoc" if environment != "production" else None,
    )

    # LESSON-006: all middleware mounted here so integration tests catch regressions.
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
        return {"status": "ok", "module": "reclaimrx"}

    return app


app = create_app()

__all__ = ["app", "create_app"]
