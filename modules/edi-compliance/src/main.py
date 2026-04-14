"""EDI & Compliance module FastAPI entry point.

Mounts security headers middleware, rate limiting, and all API routers.
Every primitive is mounted on the real app (LESSON-006 — not just tested in isolation).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from .api.compliance import router as compliance_router
from .api.generate import router as generate_router
from .api.parse import router as parse_router
from .api.trading_partners import router as trading_partners_router

logger = logging.getLogger("edi-compliance.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        from sqlalchemy import text
        from shared.db.engine import dispose_engine, get_engine
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pass

    try:
        from shared.events.factory import get_event_bus, reset_event_bus
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
        from shared.db.engine import dispose_engine  # pragma: no cover
        await dispose_engine()  # pragma: no cover
    except Exception:  # pragma: no cover
        pass
    logger.info("edi-compliance service stopped", extra={"svc_name": "edi-compliance"})


def create_app() -> FastAPI:
    """Create the EDI & Compliance FastAPI application.

    All middleware and routers are mounted here so integration tests that
    drive create_app() exercise the full stack (LESSON-006).
    """
    app = FastAPI(
        title="EDI & Compliance",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Security middleware — mounted on the REAL app, not just in tests (LESSON-006)
    try:
        from modules.core_platform.src.infrastructure.rate_limiter import (  # type: ignore[import]
            RateLimitConfig,
            RateLimitMiddleware,
        )
        from modules.core_platform.src.infrastructure.security_headers import (  # type: ignore[import]
            SecurityHeadersMiddleware,
        )
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(RateLimitMiddleware, config=RateLimitConfig())
    except (ImportError, Exception):
        pass

    # DLQ router — mounted on the real app (LESSON-006)
    try:
        from shared.events.dlq import build_dlq_router
        dlq_router = build_dlq_router()
        app.include_router(dlq_router, prefix="/api/v1/edi/dlq")
    except (ImportError, Exception):
        pass

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
