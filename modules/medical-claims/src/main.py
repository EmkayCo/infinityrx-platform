"""Medical Claims FastAPI application.

All middleware mounted here per LESSON-006:
- SecurityHeadersMiddleware (HSTS, CSP, X-Request-ID)
- RateLimitMiddleware (per-tenant, per-user token bucket)
- DLQ router
"""
from __future__ import annotations

from fastapi import FastAPI

from shared.events.dlq import DLQService, build_dlq_router

from .api.router import router as api_router
from .infrastructure.rate_limiter import RateLimitConfig, RateLimitMiddleware
from .infrastructure.security_headers import SecurityHeadersMiddleware


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
    app = FastAPI(
        title="InfinityRx Medical Claims",
        version="1.0.0",
        description="Medical benefit drug claims — HCPCS J/Q/C codes, ASP pricing, 340B detection, unified spend.",
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
        return {"status": "ok", "module": "medical-claims"}

    return app


app = create_app()

__all__ = ["app", "create_app"]
