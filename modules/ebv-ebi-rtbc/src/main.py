"""EBV/EBI/RTBC FastAPI application.

All middleware mounted here per LESSON-006:
- SecurityHeadersMiddleware
- RateLimitMiddleware
- DLQ router
- CORSMiddleware (when CORS_ALLOW_ORIGINS is set)
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .infrastructure.rate_limiter import RateLimitConfig, RateLimitMiddleware
from .infrastructure.security_headers import SecurityHeadersMiddleware
from shared.events.dlq import DLQService, build_dlq_router

from .api.router import router as api_router


class _EmptyDLQRepository:
    async def list(self, **_kwargs):  # type: ignore[no-untyped-def]
        return []

    async def get(self, _entry_id):  # type: ignore[no-untyped-def]
        return None

    async def save(self, _entry) -> None:
        return None


async def _get_dlq_service() -> DLQService:
    return DLQService(repository=_EmptyDLQRepository())


async def _get_dlq_permissions() -> set[str]:
    return set()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: install slow-query logger on the shared async engine."""
    try:
        from shared.db.engine import get_engine  # noqa: PLC0415
        from shared.observability.slow_query import install_slow_query_logger  # noqa: PLC0415
        threshold = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "1000"))
        install_slow_query_logger(get_engine().sync_engine, threshold_ms=threshold)
    except Exception:  # pragma: no cover
        pass
    yield


def create_app() -> FastAPI:
    """Application factory. Tests use this to build a fresh app per case."""
    try:
        from shared.config import get_settings  # noqa: PLC0415
        settings = get_settings()
        environment = getattr(settings, "ENVIRONMENT", "development")
        cors_origins = getattr(settings, "CORS_ALLOW_ORIGINS", [])
    except Exception:  # pragma: no cover
        environment = "development"
        cors_origins = []

    app = FastAPI(
        lifespan=lifespan,
        title="InfinityRx EBV/EBI/RTBC",
        version="1.0.0",
        description="Eligibility & Benefit Verification, Benefit Investigation, Real-Time Prescription Benefit.",
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

    app.include_router(api_router)
    app.include_router(
        build_dlq_router(
            get_service=_get_dlq_service,
            get_permissions=_get_dlq_permissions,
        )
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "module": "ebv-ebi-rtbc"}

    return app


app = create_app()

__all__ = ["app", "create_app"]
