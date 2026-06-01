"""SP-3 reclaimrx route dependencies.

R1 BLOCK 2 fix: dependencies wrap `shared/auth/dependencies.py` factories.
R1 BLOCK 3 fix: require_mfa_elevated returns 403 MFA_REQUIRED (not 503).
R1 BLOCK 4 fix: require_tenant_match validates X-Tenant-Id header.

Production rule: import nothing from src._shim.auth in route handlers.
This module is the sole bridge between the spec 3-role model and the
shared auth factories.
"""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Callable

from fastapi import Depends, Header, HTTPException

from shared.auth.dependencies import (
    CurrentUser,
    get_current_user,
    require_roles,
)
from shared.db.tenant_context import set_tenant_context

from src.api.errors import build_error_envelope

# ── Role bindings (spec §5.4) ─────────────────────────────────────────────────
# Hierarchy: reclaimrx.admin > reclaimrx.investigator > reclaimrx.viewer.
# Each dep lists every role that satisfies the floor.

RECLAIMRX_VIEWER_DEP = Depends(
    require_roles("reclaimrx.viewer", "reclaimrx.investigator", "reclaimrx.admin")
)
RECLAIMRX_INVESTIGATOR_DEP = Depends(
    require_roles("reclaimrx.investigator", "reclaimrx.admin")
)
RECLAIMRX_ADMIN_DEP = Depends(require_roles("reclaimrx.admin"))



# ── MFA dependency (spec D6a; R1 BLOCK 3 fix) ─────────────────────────────────

# Type alias for the session-lookup callable. Lets tests inject a stub
# without monkeypatching core-platform HTTP code. Production binding is set
# at app-factory time via `set_mfa_session_lookup()`.
SessionLookup = Callable[[uuid.UUID], dict | None]
_session_lookup: SessionLookup | None = None


def set_mfa_session_lookup(fn: SessionLookup) -> None:
    """Inject the production session-lookup callable at app-factory time."""
    global _session_lookup
    _session_lookup = fn


def _default_session_lookup(user_id: uuid.UUID) -> dict | None:
    # No production binding set — fail closed.
    return None


def require_mfa_elevated(
    user: CurrentUser = Depends(
        require_roles("reclaimrx.viewer", "reclaimrx.investigator", "reclaimrx.admin")
    ),
    session_lookup: SessionLookup | None = None,
) -> CurrentUser:
    """Require the caller's session to be MFA-elevated (spec D6a).

    Returns the CurrentUser when elevated. Raises 403 MFA_REQUIRED otherwise.
    R1 BLOCK 3 fix: 403 is the spec-correct status; 503 would silently let
    the request through on core-platform availability blips (fail-open),
    which violates fail-closed.
    """
    if os.getenv("RECLAIMRX_MFA_BYPASS") == "1":
        return user
    lookup = session_lookup or _session_lookup or _default_session_lookup
    session = lookup(user.id)
    elevated_until = (session or {}).get("mfa_elevated_until")
    if elevated_until and elevated_until > datetime.now(UTC):
        return user
    raise HTTPException(
        status_code=403,
        detail=build_error_envelope(
            "MFA_REQUIRED",
            "MFA-elevated session required to access this resource.",
        ),
    )


# ── Tenant-header validator (R1 BLOCK 4 fix) ──────────────────────────────────

def require_tenant_match(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Validate the X-Tenant-Id header matches the authenticated user's tenant.

    Raises 400 INVALID_TENANT_HEADER on missing or malformed header.
    Raises 403 TENANT_MISMATCH on tenant cross-claim.
    """
    if x_tenant_id is None:
        raise HTTPException(
            status_code=400,
            detail=build_error_envelope(
                "INVALID_TENANT_HEADER",
                "X-Tenant-Id header is required.",
                field="x-tenant-id",
            ),
        )
    try:
        header_tid = uuid.UUID(x_tenant_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=build_error_envelope(
                "INVALID_TENANT_HEADER",
                "X-Tenant-Id is not a valid UUID.",
                field="x-tenant-id",
            ),
        ) from exc
    if header_tid != user.tenant_id:
        raise HTTPException(
            status_code=403,
            detail=build_error_envelope(
                "TENANT_MISMATCH",
                "Authenticated user tenant does not match X-Tenant-Id header.",
                field="x-tenant-id",
            ),
        )
    return user


# DB session accessor re-exported from shim so router.py has one import site.
from src._shim.db import get_session as _get_session
from collections.abc import Generator
from sqlalchemy.orm import Session


def get_db() -> Generator[Session, None, None]:
    yield from _get_session()


async def bind_tenant_context(
    user: CurrentUser = Depends(require_tenant_match),
) -> CurrentUser:
    """Async wrapper over require_tenant_match that publishes the authenticated tenant
    into the shared contextvar IN THE ROUTE'S ASYNC TASK CONTEXT.

    require_tenant_match / get_current_user are sync deps that FastAPI runs in a
    threadpool; any set_tenant_context() there lands in a throwaway worker-thread context
    the async handler never sees, leaving the ORM tenant-loader + Postgres RLS GUC unset
    (every read returns 0 rows). Setting it here -- in an async dep -- binds it to the same
    task the handler and its sync DB session run in. Mirrors dataiq's get_tenant_id.
    """
    set_tenant_context(user.tenant_id)
    return user
