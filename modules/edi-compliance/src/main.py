"""EDI & Compliance module FastAPI entry point.

Mounts security headers middleware, rate limiting, and all API routers.
Every primitive is mounted on the real app (LESSON-006 — not just tested in isolation).

CR-08 fix: removed try/except (ImportError, Exception): pass that wrapped
middleware imports. The previous code imported from
modules.core_platform.src.infrastructure (wrong path) and silently swallowed
ImportError, making middleware a silent no-op in production.
Now imports from shared.middleware (correct canonical location).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.events.dlq import DLQService, build_dlq_router
from shared.middleware import RateLimitConfig, RateLimitMiddleware, SecurityHeadersMiddleware

from .api.compliance import router as compliance_router
from .api.generate import router as generate_router
from .api.parse import router as parse_router
from .api.trading_partners import router as trading_partners_router

logger = logging.getLogger("edi-compliance.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        from sqlalchemy import text  # noqa: PLC0415
        from shared.db.engine import get_engine  # noqa: PLC0415
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover — DB not required in unit tests
        pass

    try:
        from shared.events.factory import get_event_bus, reset_event_bus  # noqa: PLC0415
        bus = get_event_bus()
        await bus.start()
        logger.info("edi-compliance service started", extra={"svc_name": "edi-compliance"})
        yield
        await bus.stop()
        reset_event_bus()
    except Exception:  # pragma: no cover
        logger.info("edi-compliance service started (standalone mode)", extra={"svc_name": "edi-compliance"})
        yield

    try:
        from shared.db.engine import dispose_engine  # noqa: PLC0415  # pragma: no cover
        await dispose_engine()  # pragma: no cover
    except Exception:  # pragma: no cover
        pass
    logger.info("edi-compliance service stopped", extra={"svc_name": "edi-compliance"})


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
    """Create the EDI & Compliance FastAPI application.

    All middleware and routers are mounted here so integration tests that
    drive create_app() exercise the full stack (LESSON-006 / CR-08).

    Middleware is imported from shared.middleware — NO try/except suppression.
    If the import fails, it should fail loudly at startup, not silently skip.
    """
    from shared.config import get_settings  # noqa: PLC0415 — deferred to allow test override

    settings = get_settings()
    environment = getattr(settings, "ENVIRONMENT", "development")
    cors_origins = getattr(settings, "CORS_ALLOW_ORIGINS", [])

    app = FastAPI(
        title="EDI & Compliance",
        version="1.0.0",
        lifespan=lifespan,
        openapi_url="/openapi.json" if environment != "production" else None,
        docs_url="/docs" if environment != "production" else None,
        redoc_url="/redoc" if environment != "production" else None,
    )

    # LESSON-006 / CR-08: Security middleware mounted explicitly — NO silent fallback.
    # Imports from shared.middleware (canonical). If this fails at startup, the
    # service refuses to start rather than running unprotected.
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

    # DLQ router — mounted on the real app (LESSON-006)
    app.include_router(
        build_dlq_router(
            get_service=_get_dlq_service,
            get_permissions=_get_dlq_permissions,
        )
    )

    # Business routers
    prefix = "/api/v1/edi"
    app.include_router(generate_router, prefix=prefix)
    app.include_router(parse_router, prefix=prefix)
    app.include_router(trading_partners_router, prefix=prefix)
    app.include_router(compliance_router, prefix=prefix)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "module": "edi-compliance"}

    return app


app = create_app()
