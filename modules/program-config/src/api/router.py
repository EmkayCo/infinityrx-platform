"""Top-level API router aggregating all program-config sub-routers."""
from __future__ import annotations

from fastapi import APIRouter

from .routes.brd import router as brd_router
from .routes.contracts import router as contracts_router
from .routes.manufacturer import router as manufacturer_router
from .routes.onboarding import router as onboarding_router
from .routes.programs import router as programs_router

router = APIRouter(prefix="/api/v1/program-config")

router.include_router(programs_router)
router.include_router(brd_router)
router.include_router(contracts_router)
router.include_router(onboarding_router)
router.include_router(manufacturer_router)
