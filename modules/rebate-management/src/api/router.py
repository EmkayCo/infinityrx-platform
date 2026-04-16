"""Top-level API router for rebate-management module."""

from __future__ import annotations

from fastapi import APIRouter

from .routes.contracts import router as contracts_router
from .routes.calculations import router as calculations_router
from .routes.pass_through import router as pass_through_router
from .routes.gtn_waterfall import router as gtn_router
from .routes.spend_cap import router as spend_cap_router
from .routes.compliance import router as compliance_router

router = APIRouter(prefix="/api/v1/rebates")

router.include_router(contracts_router)
router.include_router(calculations_router)
router.include_router(pass_through_router)
router.include_router(gtn_router)
router.include_router(spend_cap_router)
router.include_router(compliance_router)
