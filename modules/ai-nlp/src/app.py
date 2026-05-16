"""AI/NLP module FastAPI application factory.

LESSON-006: All middleware and routers must be MOUNTED here, not just unit-tested.
Integration test through create_app() is the only reliable way to verify
they're on the live request path.
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

logger = logging.getLogger("ai-nlp.main")


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


async def _build_openai_client_or_fail():
    """Build an OpenAIClient from env vars, or raise RuntimeError if missing.

    CR-01 v2 BLOCK-3 fix: ai-nlp event consumers require a real OpenAI client.
    Proceeding with None marks FWA events as processed but skips NLP analysis —
    data loss. Fail fast at startup so the misconfiguration is immediately visible.
    """
    from shared.ai.openai_client import OpenAIClient, OpenAIConfig  # noqa: PLC0415
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    missing = [
        var for var, val in [
            ("AZURE_OPENAI_ENDPOINT", endpoint),
            ("AZURE_OPENAI_API_KEY", api_key),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(
            f"ai-nlp service requires Azure OpenAI configuration. "
            f"Missing env vars: {', '.join(missing)}. "
            f"Set them before starting the ai-nlp service."
        )
    config = OpenAIConfig(endpoint=endpoint, api_key=api_key)
    return OpenAIClient(config=config)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Wire event consumers with real OpenAI client at startup.

    CR-01 v2 BLOCK-3 fix: openai_client=None was silently no-opping FWA NLP
    analysis while marking events as processed (idempotency BLOCK). Now we
    fail fast at startup if Azure OpenAI credentials are missing.
    """
    openai_client = await _build_openai_client_or_fail()

    from shared.events.factory import get_event_bus, reset_event_bus  # noqa: PLC0415
    from src.events import wire_consumers  # noqa: PLC0415

    bus = get_event_bus()
    try:
        await bus.start()
        await wire_consumers(bus, openai_client=openai_client, db_factory=None)
        logger.info("ai-nlp service started", extra={"svc_name": "ai-nlp"})
        yield
    finally:
        await bus.stop()
        reset_event_bus()
        logger.info("ai-nlp service stopped", extra={"svc_name": "ai-nlp"})


def create_app() -> FastAPI:
    """Create and configure the AI/NLP FastAPI application."""
    from shared.config import get_settings  # noqa: PLC0415 — deferred to allow test override

    settings = get_settings()
    environment = getattr(settings, "ENVIRONMENT", "development")
    cors_origins = getattr(settings, "CORS_ALLOW_ORIGINS", [])

    app = FastAPI(
        lifespan=lifespan,
        title="InfinityRx AI/NLP Layer",
        version="1.0.0",
        description="AI/NLP service layer — document intelligence, RAG chatbot, content generation",
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

    app.include_router(router)
    app.include_router(
        build_dlq_router(
            get_service=_get_dlq_service,
            get_permissions=_get_dlq_permissions,
        )
    )

    @app.get("/health")
    async def health() -> dict:
        from sqlalchemy import text  # noqa: PLC0415
        from shared.db.session import get_sessionmaker  # noqa: PLC0415
        from fastapi.responses import JSONResponse  # noqa: PLC0415

        db_status: str
        db_critical_failed: bool
        try:
            maker = get_sessionmaker()
            async with maker() as session:
                await session.execute(text("SELECT 1"))
            db_status = "ok"
            db_critical_failed = False
        except Exception as exc:  # noqa: BLE001
            db_status = f"error: {type(exc).__name__}"
            db_critical_failed = True

        dependencies: dict[str, str] = {"database": db_status}

        if db_critical_failed:
            overall = "unhealthy"
        elif any(v != "ok" for v in dependencies.values()):
            overall = "degraded"
        else:
            overall = "healthy"

        status_code = 503 if db_critical_failed else 200
        return JSONResponse(
            status_code=status_code,
            content={"status": overall, "module": "ai-nlp", "dependencies": dependencies},
        )

    return app


app = create_app()

__all__ = ["app", "create_app"]
