"""Drug Database FastAPI application factory.

LESSON-006: Every middleware mounted here must have an integration test
that exercises it through create_app(), not in isolation.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.events.dlq import DLQService, build_dlq_router

from src.api.router import router
from src.infrastructure.rate_limiter import RateLimitConfig, RateLimitMiddleware
from src.infrastructure.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)


class _EmptyDLQRepository:
    async def list(self, **_kwargs):  # type: ignore[no-untyped-def]  # pragma: no cover
        return []

    async def get(self, _entry_id):  # type: ignore[no-untyped-def]  # pragma: no cover
        return None

    async def save(self, _entry) -> None:  # pragma: no cover
        return None


async def _get_dlq_service() -> DLQService:
    return DLQService(repository=_EmptyDLQRepository())


async def _get_dlq_permissions() -> set[str]:
    return set()


def create_app() -> FastAPI:
    """Application factory. Tests use this to build a fresh app per case."""
    try:
        from shared.config import get_settings  # noqa: PLC0415
        settings = get_settings()
        environment = getattr(settings, "ENVIRONMENT", "development")
        cors_origins = getattr(settings, "CORS_ALLOW_ORIGINS", [])
    except Exception:  # pragma: no cover — settings unavailable in some test envs
        environment = "development"
        cors_origins = []

    app = FastAPI(
        title="InfinityRx Drug Database",
        version="1.0.0",
        description="Drug reference data — NDC lookup, pricing, interactions, equivalence.",
        openapi_url="/openapi.json" if environment != "production" else None,
        docs_url="/docs" if environment != "production" else None,
        redoc_url="/redoc" if environment != "production" else None,
    )

    # CORS must be added before other middleware (outermost layer for preflight).
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

    return app


app = create_app()

__all__ = ["app", "create_app"]
