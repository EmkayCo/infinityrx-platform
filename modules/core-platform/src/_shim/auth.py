"""Shim auth: current_user dependency.

Two paths (B11 ship-day hotfix):

- TEST path: ``set_current_user(u)`` installs a module-level override;
  ``current_user`` returns it directly. Used by every existing
  core-platform test fixture.
- PRODUCTION path: when no override is set, decode the bearer token
  via ``shared.auth.jwt_tokens`` and synthesize a ``CurrentUser`` from
  the claims (``sub``, ``tid``, ``roles``). Roles are JWT-trusted —
  the dev bypass mints HS256 against ``JWT_SECRET`` so the claims have
  already been cryptographically validated by the time we read them.

The proper refactor (eliminate this shim across all 7 core-platform
sub-routers in favor of ``shared.auth.dependencies.get_current_user``)
is deferred to B12 slice 1. This file is the minimum-blast-radius B11
ship-day fix that turns the F-W04 audit gate green.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from shared.auth.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    WrongTokenTypeError,
)
from shared.auth.jwt_tokens import (
    TOKEN_TYPE_ACCESS,
    decode_token,
    verify_token_type,
)


@dataclass
class CurrentUser:
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str = "dev@example.com"
    roles: List[str] = field(default_factory=lambda: ["tenant_admin"])

    def has_role(self, role: str) -> bool:
        return role in self.roles


_override: CurrentUser | None = None
# auto_error=False so the Depends doesn't immediately 401 on missing
# header; ``current_user`` itself raises with structured error context
# (so callers see ``{"error": "missing_token", ...}`` instead of FastAPI's
# default ``{"detail": "Not authenticated"}`` shape).
_bearer = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def set_current_user(user: CurrentUser | None) -> None:
    global _override
    _override = user


def current_user(token: str | None = Depends(_bearer)) -> CurrentUser:
    """Resolve the caller's ``CurrentUser``.

    Resolution order:

    1. If a test override is set (``set_current_user(u)``), return it.
       The token is ignored — tests don't bother minting JWTs.
    2. Else decode the bearer token via ``shared.auth.jwt_tokens`` and
       synthesize a ``CurrentUser`` from claims. ``roles`` come from
       the JWT claim, so the audit router's ``tenant_admin in user.roles``
       gate works when the dev bypass mints a JWT with that role.
    3. Else (no override, no token, or invalid token) raise 401 with a
       structured detail body.
    """
    if _override is not None:
        return _override
    # When called directly (not via FastAPI's dep resolver — e.g., from
    # ``require_role``'s inner factory before this revision), ``token``
    # may arrive as the ``Depends`` marker rather than a string. Treat
    # any non-string as absent.
    if not isinstance(token, str) or not token:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "missing_token",
                "message": "Authorization bearer token required",
            },
        )
    try:
        claims = decode_token(token)
        verify_token_type(claims, TOKEN_TYPE_ACCESS)
    except ExpiredTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": "expired_token", "message": str(exc)},
        ) from exc
    except (InvalidTokenError, WrongTokenTypeError) as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "message": str(exc)},
        ) from exc
    # Role-hierarchy expansion: ``platform_admin`` is the system-wide
    # superuser and necessarily inherits every tenant-scoped role.
    # Without this expansion, the dev-bypass JWT (which mints only
    # ``platform_admin``) would 403 on routes gated by
    # ``require_role("tenant_admin", ...)`` — e.g., the audit query
    # endpoint. The proper RBAC layer (B12 slice 2+) will encode this
    # implication declaratively; for B11 ship-day, expand inline.
    roles = list(claims.roles or ())
    if "platform_admin" in roles and "tenant_admin" not in roles:
        roles.append("tenant_admin")
    return CurrentUser(
        id=claims.user_id,
        # tenant_id falls back to user_id when the token has no tid claim
        # (defensive — the access token shape always includes tid, but
        # this avoids a None-attribute crash in the synthesized struct).
        tenant_id=claims.tenant_id or claims.user_id,
        email="dev@infinityrx.local",
        roles=roles,
    )


def require_role(*roles: str):
    """Build a FastAPI dependency that asserts the caller has one of ``roles``.

    Chains through ``current_user`` via ``Depends`` so the JWT-decode path
    is exercised on the same request. Direct (non-FastAPI) callsites need
    to supply a ``CurrentUser`` themselves.
    """

    def _dep(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if not any(user.has_role(r) for r in roles):
            raise HTTPException(
                status_code=403,
                detail={"error": "forbidden", "required": list(roles)},
            )
        return user

    return _dep
