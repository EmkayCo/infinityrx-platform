"""Member Management FastAPI application.

All middleware mounted here per LESSON-006:
- SecurityHeadersMiddleware
- RateLimitMiddleware
- DLQ router
- CORSMiddleware (when CORS_ALLOW_ORIGINS is set)
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .infrastructure.rate_limiter import (
    RateLimitConfig,
    RateLimitMiddleware,
)
from .infrastructure.security_headers import SecurityHeadersMiddleware
from shared.events.dlq import DLQService, build_dlq_router

from .api.router import router as api_router


class _EmptyDLQRepository:
    async def list(self, **_kwargs):
        return []

    async def get(self, _entry_id):
        return None

    async def save(self, _entry) -> None:
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
        title="InfinityRx Member Management",
        version="1.0.0",
        description="Member enrollment, eligibility, accumulators, and benefit tracking.",
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

    app.include_router(api_router)
    app.include_router(
        build_dlq_router(
            get_service=_get_dlq_service,
            get_permissions=_get_dlq_permissions,
        )
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "module": "member-management"}

    return app


app = create_app()

__all__ = ["app", "create_app"]
