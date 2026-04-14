"""AI/NLP module FastAPI application factory.

LESSON-006: All middleware and routers must be MOUNTED here, not just unit-tested.
Integration test through create_app() is the only reliable way to verify
they're on the live request path.
"""

from __future__ import annotations

from fastapi import FastAPI

from src.api.router import router
from src.middleware import SecurityHeadersMiddleware


def create_app() -> FastAPI:
    """Create and configure the AI/NLP FastAPI application."""
    app = FastAPI(
        title="InfinityRx AI/NLP Layer",
        version="1.0.0",
        description="AI/NLP service layer — document intelligence, RAG chatbot, content generation",
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "module": "ai-nlp"}

    return app
