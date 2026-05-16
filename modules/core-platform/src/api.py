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
    """Permission gate for the audit router.

    Checks that the caller's ``CurrentUser.permissions`` contains the
    requested *permission* string (``module:action`` format).

    Backward-compat: ``tenant_admin`` and ``platform_admin`` roles implicitly
    possess all ``audit.*`` permissions because the RBAC layer (B12 slice 2+)
    will encode this declaratively.  Until then, this shim grants access if
    the permission is present OR the caller holds a privileged role.

    HIGH-2 fix (B12-S1 v2): v1 checked only ``tenant_admin`` role, ignoring
    the ``permission`` string entirely — any tenant_admin could access all
    audit endpoints regardless of permission grants.
    """
    from fastapi import Depends  # noqa: PLC0415

    _PRIVILEGED_ROLES = frozenset({"tenant_admin", "platform_admin"})

    def _dep_factory(current: Any = Depends(current_user)) -> Any:
        user_permissions: tuple = getattr(current, "permissions", ())
        user_roles: tuple = getattr(current, "roles", ())
        has_permission = permission in user_permissions
        # Backward-compat: privileged roles implicitly hold all audit.* perms
        # until the RBAC layer encodes this declaratively (B12 slice 2+).
        has_privileged_role = bool(set(user_roles) & _PRIVILEGED_ROLES)
        if not has_permission and not has_privileged_role:
            raise HTTPException(
                status_code=403,
                detail={"error": "forbidden", "message": f"missing permission {permission}"},
            )
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
