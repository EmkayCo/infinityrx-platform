"""Test the _shim/auth current_user dependency.

B11 ship-day hotfix scope: the shim previously raised RuntimeError when no
test override was set, which 500'd every authenticated request in
production runtime. The fix adds a JWT-decode path that fires when no
override is present — preserving the test override path (set_current_user)
while making the shim runtime-capable for production.

Proper refactor (eliminate _shim/auth across the 7 core-platform sub-routers
in favor of shared.auth.dependencies.get_current_user) is deferred to B12
slice 1.

Test surface:
- Override path: set_current_user(u) -> current_user(token=None) returns u.
- Production path with valid JWT: decoded -> CurrentUser with roles from claims.
- Production path with no token: 401.
- Production path with invalid token: 401.
- Production path with expired token: 401.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from shared.auth.jwt_tokens import create_access_token
from src._shim.auth import CurrentUser, current_user, set_current_user


@pytest.fixture(autouse=True)
def _clear_override():
    """Reset the module-level override so tests don't bleed."""
    set_current_user(None)
    yield
    set_current_user(None)


@pytest.fixture
def _jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a JWT secret long enough to satisfy the security rule.

    get_auth_settings() re-reads on every call (see shared/auth/_settings.py
    docstring), so a plain monkeypatch.setenv is enough — no cache to clear.
    """
    monkeypatch.setenv("JWT_SECRET", "x" * 64)
    monkeypatch.setenv("INFINITYRX_ENV", "development")


def _mint_jwt(roles: tuple[str, ...] = ("platform_admin", "tenant_admin")) -> str:
    return create_access_token(
        user_id=uuid.UUID("b0000000-0000-0000-0000-000000000001"),
        tenant_id=uuid.UUID("a0000000-0000-0000-0000-000000000001"),
        roles=list(roles),
    )


class TestTestOverridePath:
    def test_override_set_returns_override(self) -> None:
        """set_current_user(u) makes current_user return u."""
        u = CurrentUser(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="alice@example.com",
            roles=["tenant_admin"],
        )
        set_current_user(u)
        # Token is ignored when override is set — verified by passing junk.
        assert current_user(token="ignored-because-override-is-set") is u

    def test_override_set_to_none_falls_through(self, _jwt_secret: None) -> None:
        """Explicit None override falls through to production path (or raises 401)."""
        set_current_user(None)
        with pytest.raises(HTTPException) as exc_info:
            current_user(token=None)
        assert exc_info.value.status_code == 401


class TestProductionPath:
    def test_valid_jwt_returns_currentuser_with_jwt_roles(self, _jwt_secret: None) -> None:
        """A valid bearer token is decoded into a CurrentUser whose roles
        come from the JWT 'roles' claim."""
        jwt = _mint_jwt(roles=("platform_admin", "tenant_admin"))
        user = current_user(token=jwt)
        assert isinstance(user, CurrentUser)
        assert user.id == uuid.UUID("b0000000-0000-0000-0000-000000000001")
        assert user.tenant_id == uuid.UUID("a0000000-0000-0000-0000-000000000001")
        assert "tenant_admin" in user.roles
        assert "platform_admin" in user.roles

    def test_platform_admin_implies_tenant_admin(self, _jwt_secret: None) -> None:
        """Role-hierarchy expansion: a JWT carrying only ``platform_admin``
        synthesizes a CurrentUser whose roles include BOTH ``platform_admin``
        and ``tenant_admin``. This is what unblocks the F-W04 audit gate —
        the dev-bypass JWT mints only ``platform_admin`` but the audit
        router's permission factory checks ``tenant_admin in user.roles``.
        The proper RBAC layer (B12 slice 2+) will encode this implication
        declaratively; for B11 ship-day, the shim expands it inline."""
        jwt = _mint_jwt(roles=("platform_admin",))
        user = current_user(token=jwt)
        assert "platform_admin" in user.roles
        assert "tenant_admin" in user.roles, (
            "platform_admin must imply tenant_admin so the audit router's "
            "tenant_admin permission gate accepts platform_admin bearers"
        )

    def test_tenant_admin_only_does_not_get_platform_admin(self, _jwt_secret: None) -> None:
        """Inverse direction: ``tenant_admin`` does NOT get ``platform_admin``
        added. The hierarchy is one-way (platform > tenant), not symmetric."""
        jwt = _mint_jwt(roles=("tenant_admin",))
        user = current_user(token=jwt)
        assert "tenant_admin" in user.roles
        assert "platform_admin" not in user.roles

    def test_missing_token_raises_401(self, _jwt_secret: None) -> None:
        """No override + no Authorization header => 401."""
        with pytest.raises(HTTPException) as exc_info:
            current_user(token=None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"] == "missing_token"

    def test_garbage_token_raises_401(self, _jwt_secret: None) -> None:
        """An undecodable token => 401, not 500."""
        with pytest.raises(HTTPException) as exc_info:
            current_user(token="not.a.jwt")
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"] == "invalid_token"

    def test_wrong_secret_raises_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A token signed with the wrong secret => 401.

        get_auth_settings() re-reads JWT_SECRET on every call, so flipping
        the env var between mint and decode is enough to simulate a
        rotated/wrong key.
        """
        monkeypatch.setenv("JWT_SECRET", "a" * 64)
        jwt = _mint_jwt()
        monkeypatch.setenv("JWT_SECRET", "b" * 64)
        with pytest.raises(HTTPException) as exc_info:
            current_user(token=jwt)
        assert exc_info.value.status_code == 401
