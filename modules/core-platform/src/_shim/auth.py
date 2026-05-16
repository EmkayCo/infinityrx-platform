"""Shim auth: current_user dependency — B12 S1 adapter.

This module is a thin adapter over ``shared.auth.dependencies``. It
preserves the ``set_current_user`` test-injection interface used by all
existing core-platform tests so those tests need no changes, while
routing the JWT-decode production path through the shared auth layer.

Key changes vs the B11 ship-day version (35a0044):
- ``CurrentUser`` is now *imported* from ``shared.auth.dependencies``
  (the duplicate local dataclass is removed).  The shared type adds
  ``status`` and ``permissions`` fields and is frozen.
- The JWT-decode production path now calls
  ``shared.auth.dependencies._resolve_claims`` and also calls
  ``_set_tenant_context`` to propagate the tenant to the DB query
  context (previously missing — tenant isolation was not wired from
  this shim).
- ``require_role`` is re-implemented locally so it chains through the
  shim's ``current_user`` (and therefore through the test override)
  rather than through ``shared.auth.dependencies.get_current_user``
  (which requires ``configure_auth`` to have been called).

The ``set_current_user`` mechanism remains so the 8 existing test
files that call ``auth_shim.set_current_user(u)`` work without
change.  Once ``shared.auth.dependencies.get_current_user`` is wired
as the sole dependency across the sub-routers (B12 slice 1 follow-on)
this file can be deleted.
"""
from __future__ import annotations

from typing import List

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from shared.auth.dependencies import (
    CurrentUser,
    _resolve_claims,
    _set_tenant_context,
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
    2. Decode the bearer token via ``shared.auth.dependencies._resolve_claims``,
       set the tenant context so downstream DB queries are scoped correctly,
       and synthesise a ``CurrentUser`` from the JWT claims.
    3. Reject missing/expired/invalid tokens with 401.

    Unlike the pre-B12-S1 version, this path now calls
    ``_set_tenant_context`` so the ``TenantScopedMixin`` query filter
    on every ORM query sees the correct ``tenant_id`` for the request.
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

    # _resolve_claims raises HTTPException(401) on expired/invalid tokens.
    claims = _resolve_claims(token)

    # Propagate tenant to the request-scoped DB context so tenant-scoped
    # ORM queries are automatically filtered.  The assert below mirrors
    # what shared.auth.dependencies.get_current_user does — access tokens
    # always carry a tid claim; if somehow it is absent the decoder would
    # have raised InvalidTokenError before we get here.
    assert claims.tenant_id is not None, "access token must carry tenant_id"
    _set_tenant_context(claims.tenant_id)

    # Role-hierarchy expansion: ``platform_admin`` is the system-wide
    # superuser and necessarily inherits every tenant-scoped role.
    # Without this, the dev-bypass JWT (which mints only ``platform_admin``)
    # would 403 on routes gated by ``require_role("tenant_admin", ...)``.
    # The proper RBAC layer (B12 slice 2+) will encode this declaratively.
    roles: List[str] = list(claims.roles or ())
    if "platform_admin" in roles and "tenant_admin" not in roles:
        roles.append("tenant_admin")

    return CurrentUser(
        id=claims.user_id,
        tenant_id=claims.tenant_id,
        email="dev@infinityrx.local",
        status="active",
        roles=tuple(roles),
        permissions=(),
    )


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
