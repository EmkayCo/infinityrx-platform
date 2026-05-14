"""Prescriber Directory FastAPI application entry point.

create_app() is used by tests (LESSON-006: every middleware must have an
integration test through create_app, not in isolation).
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

from src.api.router import router

logger = logging.getLogger("prescriber-directory.main")


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
    """Startup: install slow-query logger on prescriber-directory sync engine (M-04)
    and configure auth so Depends(get_current_user) can resolve incoming JWTs."""
    try:
        from src.db.session import _get_engine  # noqa: PLC0415
        from shared.observability.slow_query import install_slow_query_logger  # noqa: PLC0415
        threshold = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "1000"))
        install_slow_query_logger(_get_engine(), threshold_ms=threshold)
    except Exception:  # pragma: no cover — best-effort; missing DB is fine in tests
        pass
    # Directory backends own reference data, not identity — wire the dev
    # JWT-trusting loader so get_current_user() doesn't crash. Refuses to
    # run when INFINITYRX_ENV=production; prod deployments must supply a
    # real UserLoader.
    try:
        from shared.auth.dev_trust_jwt import configure_auth_trust_jwt  # noqa: PLC0415
        configure_auth_trust_jwt()
    except RuntimeError as exc:  # production guard fired
        logger.warning("auth_trust_jwt_skipped", extra={"svc_reason": str(exc)})
    yield


def create_app() -> FastAPI:
    from shared.config import get_settings  # noqa: PLC0415 — deferred to allow test override

    settings = get_settings()
    environment = getattr(settings, "ENVIRONMENT", "development")
    cors_origins = getattr(settings, "CORS_ALLOW_ORIGINS", [])

    app = FastAPI(
        lifespan=lifespan,
        title="InfinityRx Prescriber Directory",
        version="1.0.0",
        description="Prescriber and medical provider directory — NPI lookup, DEA validation, NPPES pipeline",
        openapi_url="/openapi.json" if environment != "production" else None,
        docs_url="/docs" if environment != "production" else None,
        redoc_url="/redoc" if environment != "production" else None,
    )

    # LESSON-006: mount middleware here so integration tests through create_app() catch regressions
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
        return {"status": "ok", "module": "prescriber-directory"}

    return app


app = create_app()

__all__ = ["app", "create_app"]
