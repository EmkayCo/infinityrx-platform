"""FastAPI dependencies for authentication and authorization.

The shared layer does not know about SQLAlchemy models; instead it takes a
pluggable ``UserLoader`` callable that resolves a ``CurrentUser`` from a
decoded token's ``sub`` claim. The core-platform module provides the
production implementation bound to core.users rows; tests can supply an
in-memory fake.

Authorization primitives:
    * ``get_current_user(...)`` — resolves the JWT, loads the user, and
      asserts the account is active.
    * ``require_roles(*roles)`` — 403 if the user lacks ANY required role.
    * ``require_permissions(*perms)`` — 403 if the user lacks ANY required
      permission (``module:action``).
    * ``platform_admin_only`` / ``tenant_admin_only`` — shortcuts.

Tenant isolation: on every authenticated request the dependency sets the
``current_tenant_id`` contextvar from the token's ``tid`` claim (if T1's
``shared.db.tenant_context`` is importable), so any tenant-scoped query
executed further down the stack automatically scopes to the caller.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Callable, Protocol

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from shared.auth.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    WrongTokenTypeError,
)
from shared.auth.jwt_tokens import (
    TOKEN_TYPE_ACCESS,
    TokenClaims,
    decode_token,
    verify_token_type,
)
from shared.auth.tokens_repo import RevokedTokenRepo

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    status: str
    roles: tuple[str, ...] = field(default_factory=tuple)
    permissions: tuple[str, ...] = field(default_factory=tuple)

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_permission(self, perm: str) -> bool:
        return perm in self.permissions


class UserLoader(Protocol):
    def __call__(self, user_id: uuid.UUID) -> CurrentUser | None: ...


# Module-level wiring ---------------------------------------------------------
# The core-platform module sets these at startup via ``configure_auth``.

_user_loader: UserLoader | None = None
_revoked_repo: RevokedTokenRepo | None = None


def configure_auth(
    user_loader: UserLoader,
    revoked_repo: RevokedTokenRepo,
) -> None:
    """Bind the process-wide user loader and revoked-token repo.

    Must be called once at application startup (and again in tests that
    need to inject fakes). Kept as global module state for FastAPI
    dependency ergonomics — no hidden import cycles.
    """
    global _user_loader, _revoked_repo
    _user_loader = user_loader
    _revoked_repo = revoked_repo


def _get_user_loader() -> UserLoader:
    if _user_loader is None:
        raise RuntimeError("auth not configured: call configure_auth() at startup")
    return _user_loader


def _get_revoked_repo() -> RevokedTokenRepo:
    if _revoked_repo is None:
        raise RuntimeError("auth not configured: call configure_auth() at startup")
    return _revoked_repo


def _set_tenant_context(tenant_id: uuid.UUID) -> None:
    from shared.db.tenant_context import set_tenant_context

    set_tenant_context(tenant_id)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "unauthorized", "message": detail},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str, required: list[str]) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error": "forbidden", "message": detail, "required": required},
    )


def _resolve_claims(token: str | None) -> TokenClaims:
    if not token:
        raise _unauthorized("missing bearer token")
    try:
        claims = decode_token(token)
    except ExpiredTokenError as exc:
        raise _unauthorized("token expired") from exc
    except InvalidTokenError as exc:
        raise _unauthorized(f"invalid token: {exc}") from exc
    try:
        verify_token_type(claims, TOKEN_TYPE_ACCESS)
    except WrongTokenTypeError as exc:
        raise _unauthorized(str(exc)) from exc
    return claims


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
) -> CurrentUser:
    """Resolve the request's bearer token into a CurrentUser.

    Rejects missing/expired/invalid tokens (401), revoked tokens (401),
    unknown users (401), and non-active accounts (401).
    """
    claims = _resolve_claims(token)
    repo = _get_revoked_repo()
    if repo.is_revoked(claims.jti):
        raise _unauthorized("token revoked")

    loader = _get_user_loader()
    user = loader(claims.user_id)
    if user is None:
        raise _unauthorized("user not found")
    if user.status != "active":
        raise _unauthorized(f"user {user.status}")
    # Access tokens always carry a tenant claim (enforced by
    # create_access_token). If somehow it is missing the decoder will
    # have raised InvalidTokenError before we get here.
    assert claims.tenant_id is not None
    _set_tenant_context(claims.tenant_id)
    return user


def require_roles(*roles: str) -> Callable[[CurrentUser], CurrentUser]:
    """Dependency factory: caller must possess at least one of *roles*."""
    required = list(roles)

    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(user.has_role(r) for r in required):
            raise _forbidden("missing required role", required)
        return user

    return _dep


def require_permissions(*perms: str) -> Callable[[CurrentUser], CurrentUser]:
    """Dependency factory: caller must possess every required permission.

    Permissions use the ``module:action`` format and are matched exactly.
    """
    required = list(perms)

    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        missing = [p for p in required if not user.has_permission(p)]
        if missing:
            raise _forbidden("missing required permission", missing)
        return user

    return _dep


platform_admin_only = require_roles("platform_admin")
tenant_admin_only = require_roles("platform_admin", "tenant_admin")
