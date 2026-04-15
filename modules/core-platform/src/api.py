"""Aggregator router for core-platform Session 4 sub-routers.

Integration Coordinator composes the full app; this module only
exposes the jobs/files/exclusions/health/government-programs routers.
"""
from __future__ import annotations

from fastapi import APIRouter

from .exclusions.api import router as exclusions_router
from .exclusions import job_handler as _exclusion_job_handler  # noqa: F401 — registers handler
from .files.api import router as files_router
from .government_programs.api import router as gov_programs_router
from .health.api import router as health_router
from .jobs.api import router as jobs_router

router = APIRouter()
router.include_router(jobs_router)
router.include_router(files_router)
router.include_router(exclusions_router)
router.include_router(gov_programs_router)
router.include_router(health_router)

__all__ = ["router"]
