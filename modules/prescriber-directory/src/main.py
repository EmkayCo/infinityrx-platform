"""Prescriber Directory FastAPI application entry point.

create_app() is used by tests (LESSON-006: every middleware must have an
integration test through create_app, not in isolation).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from src.api.router import router
from src.middleware.rate_limiter import RateLimitMiddleware
from src.middleware.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger("prescriber-directory.main")


def create_app() -> FastAPI:
    app = FastAPI(
        title="InfinityRx Prescriber Directory",
        version="1.0.0",
        description="Prescriber and medical provider directory — NPI lookup, DEA validation, NPPES pipeline",
    )

    # LESSON-006: mount middleware here so integration tests through create_app() catch regressions
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "module": "prescriber-directory"}

    return app


app = create_app()
