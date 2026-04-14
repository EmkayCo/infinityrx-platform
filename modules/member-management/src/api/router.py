"""Top-level API router for member management module."""
from __future__ import annotations

from fastapi import APIRouter

from .routes.members import router as members_router
from .routes.groups import router as groups_router
from .routes.enrollment import router as enrollment_router
from .routes.eligibility import router as eligibility_router
from .routes.coverage import router as coverage_router
from .routes.cob import router as cob_router

router = APIRouter(prefix="/api/v1")
router.include_router(members_router, prefix="/members")
router.include_router(groups_router)
router.include_router(enrollment_router, prefix="/members")
router.include_router(eligibility_router)
router.include_router(coverage_router)
router.include_router(cob_router)
