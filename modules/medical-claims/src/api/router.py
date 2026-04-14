"""Top-level API router aggregating all medical-claims sub-routers."""
from __future__ import annotations

from fastapi import APIRouter

from .routes.claims import router as claims_router
from .routes.crosswalk import router as crosswalk_router
from .routes.asp import router as asp_router
from .routes.unified_spend import router as unified_spend_router
from .routes.denials import router as denials_router
from .routes.claims_appeal import router as appeal_router
from .routes.analytics import router as analytics_router

router = APIRouter(prefix="/api/v1/medical-claims")

router.include_router(claims_router)
router.include_router(crosswalk_router)
router.include_router(asp_router)
router.include_router(unified_spend_router)
router.include_router(denials_router)
router.include_router(appeal_router)
router.include_router(analytics_router)
