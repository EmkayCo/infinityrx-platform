"""Aggregator router for core-platform sub-routers.

Integration Coordinator composes the full app; this module composes every
HTTP-facing router (jobs/files/exclusions/health/government-programs,
bank-holidays, audit query, notifications) so create_app() has a single
include_router() call for the whole module.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ._shim.auth import current_user
from ._shim.db import get_session
from .audit.api import build_audit_router
from .bank_holidays.api import router as bank_holidays_router
from .exclusions.api import router as exclusions_router
from .exclusions import job_handler as _exclusion_job_handler  # noqa: F401 — registers handler
from .jobs import verify_audit_chain_job as _audit_chain_job_handler  # noqa: F401 — registers handler
from .files.api import router as files_router
from .government_programs.api import router as gov_programs_router
from .health.api import router as health_router
from .jobs.api import router as jobs_router
from .notifications.api import build_notifications_router
from .notifications.service import NotificationService


def _audit_require_permission(permission: str):
    """Permission gate for the audit router (CurrentUser role-based)."""

    def _dep(user: Any = None) -> Any:
        from fastapi import Depends  # noqa: PLC0415

        def _inner(current: Any = Depends(current_user)) -> Any:
            if "tenant_admin" not in getattr(current, "roles", []):
                raise HTTPException(status_code=403, detail={"error": "forbidden", "message": f"missing permission {permission}"})
            return current

        return _inner()

    from fastapi import Depends  # noqa: PLC0415

    def _dep_factory(current: Any = Depends(current_user)) -> Any:
        if "tenant_admin" not in getattr(current, "roles", []):
            raise HTTPException(status_code=403, detail={"error": "forbidden", "message": f"missing permission {permission}"})
        return current

    return _dep_factory


def _notifications_service_factory(session: Any) -> NotificationService:
    return NotificationService(session, event_bus=None)


router = APIRouter()
router.include_router(jobs_router)
router.include_router(files_router)
router.include_router(exclusions_router)
router.include_router(gov_programs_router)
router.include_router(health_router)
router.include_router(bank_holidays_router)
router.include_router(
    build_audit_router(
        get_session=get_session,
        require_permission=_audit_require_permission,
    )
)
router.include_router(
    build_notifications_router(
        get_session=get_session,
        current_user_dep=current_user,
        service_factory=_notifications_service_factory,
    )
)

__all__ = ["router"]
