"""DataIQ module FastAPI application factory.

LESSON-006: every router must be mounted through create_app() and verified
by integration tests — not just tested in isolation.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.router import router

logger = logging.getLogger("dataiq.main")


def create_app() -> FastAPI:
    """Create and configure the DataIQ FastAPI application."""
    app = FastAPI(
        title="InfinityRx DataIQ",
        version="1.0.0",
        description=(
            "DataIQ analytics and business intelligence module — "
            "real-time KPIs, SPC anomaly detection, drug trend decomposition, "
            "claims repricing, PostGIS geo analytics"
        ),
    )

    app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "module": "dataiq"}

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = str(uuid.uuid4())
        logger.error(
            "unhandled_exception",
            extra={
                "svc_correlation_id": correlation_id,
                "svc_path": request.url.path,
            },
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "correlation_id": correlation_id,
                }
            },
        )

    return app


app = create_app()
