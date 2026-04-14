"""Drug Database FastAPI application factory.

LESSON-006: Every middleware mounted here must have an integration test
that exercises it through create_app(), not in isolation.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

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
    app = FastAPI(
        title="InfinityRx Drug Database",
        version="1.0.0",
        description="Drug reference data — NDC lookup, pricing, interactions, equivalence.",
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
