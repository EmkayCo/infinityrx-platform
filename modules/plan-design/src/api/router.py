"""Top-level API router aggregating all plan-design sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from .routes.hierarchy import router as hierarchy_router
from .routes.formulary import router as formulary_router
from .routes.formulary import pt_router
from .routes.network import router as network_router
from .routes.market_access import router as market_access_router

router = APIRouter(prefix="/api/v1/plan-design")

router.include_router(hierarchy_router)
router.include_router(formulary_router)
router.include_router(pt_router)
router.include_router(network_router)
router.include_router(market_access_router)
