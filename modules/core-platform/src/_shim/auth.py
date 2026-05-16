"""Shim auth: current_user dependency — B12 S1 adapter (v2).

This module is a thin adapter over ``shared.auth.dependencies``. It
preserves the ``set_current_user`` test-injection interface used by all
existing core-platform tests so those tests need no changes, while
routing the JWT-decode production path through the full shared auth layer.

Key changes vs v1 (0ecc73a4):
- The JWT-decode production path now calls
  ``shared.auth.dependencies.get_current_user(token)`` directly (path a),
  which enforces revocation check, inactive-user rejection, and DB-backed
  role/permissions load — all of which v1 skipped by calling
  ``_resolve_claims`` only (HIGH-1 finding).
- ``_resolve_claims`` and ``_set_tenant_context`` are no longer called
  from this shim; ``get_current_user`` handles both internally.

The ``set_current_user`` mechanism remains so the 8 existing test
files that call ``auth_shim.set_current_user(u)`` work without
change.  When the override is active, the token is ignored and the
full auth path is skipped (this is the intended test-injection contract;
tests that need revocation/inactive coverage supply a real JWT and leave
the override unset — see tests/test_auth.py B12-S2 class).

Once ``shared.auth.dependencies.get_current_user`` is wired as the
sole dependency across the sub-routers (B12 slice 1 follow-on) this
file can be deleted.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from shared.auth.dependencies import (
    CurrentUser,
    get_current_user as _shared_get_current_user,
)

# Keep the oauth2 scheme aligned with the shared one so FastAPI OpenAPI docs
# show a single tokenUrl entry.
_bearer = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

_override: CurrentUser | None = None


def set_current_user(user: CurrentUser | None) -> None:
    """Install (or clear) a process-wide test override.

    When set, ``current_user`` returns this object without touching
    the JWT or the user loader — tests that call
    ``set_current_user(u)`` keep working unchanged.
    """
    global _override
    _override = user


def current_user(token: str | None = Depends(_bearer)) -> CurrentUser:
    """Resolve the caller's ``CurrentUser``.

    Resolution order:

    1. If a test override is installed (``set_current_user(u)``), return
       it immediately.  The token is ignored — tests don't mint JWTs.
    2. Route through ``shared.auth.dependencies.get_current_user(token)``
       which enforces: JWT decode, token-type check, revocation check,
       inactive-user rejection, DB-backed role/permissions load, and
       tenant context propagation.
    3. Reject missing/expired/invalid/revoked tokens with 401.

    HIGH-1 fix (B12-S1 v2): v1 called ``_resolve_claims`` only, bypassing
    revocation, inactive-user, and DB-permissions checks. This path now
    routes through ``get_current_user`` so all enforcement runs on every
    request regardless of which entry point is used.
    """
    if _override is not None:
        return _override

    if not isinstance(token, str) or not token:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "missing_token",
                "message": "Authorization bearer token required",
            },
        )

    # Route through the full shared auth stack:
    #   decode → type-check → revocation → user-load → inactive-check → tenant-ctx
    # get_current_user raises HTTPException(401) on any failure.
    #
    # Role-hierarchy note: ``get_current_user`` returns the user as loaded
    # from the DB via the user_loader (which populates roles/permissions from
    # ORM).  For the dev-bypass JWT path (platform_admin only, no DB user),
    # configure_core_auth must wire a user_loader that performs the
    # platform_admin → tenant_admin role expansion.  Tests that do NOT call
    # configure_core_auth must use the set_current_user override path.
    return _shared_get_current_user(token=token)


def require_role(*roles: str):
    """Build a FastAPI dependency that asserts the caller has one of ``roles``.

    Chains through the shim's ``current_user`` (not the shared
    ``get_current_user``) so the test-override path (``set_current_user``)
    is respected.  The shim's ``current_user`` handles JWT decode + tenant
    context propagation for production requests.
    """

    def _dep(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if not any(user.has_role(r) for r in roles):
            raise HTTPException(
                status_code=403,
                detail={"error": "forbidden", "required": list(roles)},
            )
        return user

    return _dep
