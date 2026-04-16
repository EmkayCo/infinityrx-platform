"""Top-level API router aggregating all prior-authorization sub-routers."""
from __future__ import annotations

from fastapi import APIRouter

from .routes.pa_requests import router as pa_requests_router
from .routes.decisions import router as decisions_router

router = APIRouter(prefix="/api/v1/prior-auth")

router.include_router(pa_requests_router)
router.include_router(decisions_router)
