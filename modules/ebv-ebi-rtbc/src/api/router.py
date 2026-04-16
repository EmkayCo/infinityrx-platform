"""Top-level API router for EBV/EBI/RTBC module."""
from __future__ import annotations

from fastapi import APIRouter

from .routes.benefit import router as benefit_router
from .routes.eligibility import router as eligibility_router
from .routes.hub import router as hub_router
from .routes.member_tools import router as member_tools_router
from .routes.rtpb import router as rtpb_router

router = APIRouter(prefix="/api/v1")
router.include_router(eligibility_router)
router.include_router(benefit_router)
router.include_router(rtpb_router)
router.include_router(member_tools_router)
router.include_router(hub_router)
