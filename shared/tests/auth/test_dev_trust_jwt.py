"""Unit tests for shared.auth.dev_trust_jwt.

Covers the production refusal guard and the synthetic-loader behaviour
the directory backends depend on.
"""
from __future__ import annotations

import os
import uuid

import pytest

from shared.auth import dependencies as auth_dep
from shared.auth.dev_trust_jwt import configure_auth_trust_jwt


@pytest.fixture(autouse=True)
def _reset_auth_state(monkeypatch):
    """Reset module-level auth wiring before/after each test so tests cannot
    leak loader state into each other or into the rest of the suite."""
    monkeypatch.setattr(auth_dep, "_user_loader", None)
    monkeypatch.setattr(auth_dep, "_revoked_repo", None)
    yield
    auth_dep._user_loader = None
    auth_dep._revoked_repo = None


def test_refuses_in_production(monkeypatch):
    """Production env must hard-refuse — this code path is dev-only."""
    monkeypatch.setenv("INFINITYRX_ENV", "production")
    with pytest.raises(RuntimeError, match="must not run in production"):
        configure_auth_trust_jwt()


def test_refuses_in_production_case_insensitive(monkeypatch):
    """Trim + lowercase: "  Production  " is still production."""
    monkeypatch.setenv("INFINITYRX_ENV", "  Production  ")
    with pytest.raises(RuntimeError, match="must not run in production"):
        configure_auth_trust_jwt()


def test_configures_loader_in_dev(monkeypatch):
    monkeypatch.setenv("INFINITYRX_ENV", "development")
    configure_auth_trust_jwt()
    # After configuration, the module-level wiring should be populated.
    assert auth_dep._user_loader is not None
    assert auth_dep._revoked_repo is not None


def test_loader_returns_active_admin_user(monkeypatch):
    """The synthetic loader must build a CurrentUser get_current_user() can
    accept: status="active", platform_admin role, wildcard permission."""
    monkeypatch.setenv("INFINITYRX_ENV", "development")
    configure_auth_trust_jwt(default_email="qa@infinityrx.local")
    loader = auth_dep._user_loader
    assert loader is not None
    user_id = uuid.UUID("b0000000-0000-0000-0000-000000000001")
    user = loader(user_id)
    assert user.id == user_id
    assert user.status == "active"
    assert user.email == "qa@infinityrx.local"
    assert "platform_admin" in user.roles
    assert "*" in user.permissions


def test_default_env_is_development(monkeypatch):
    """If INFINITYRX_ENV is unset, default treated as development (not prod)."""
    monkeypatch.delenv("INFINITYRX_ENV", raising=False)
    # Should not raise — unset env defaults to development.
    configure_auth_trust_jwt()
    assert auth_dep._user_loader is not None


def test_loader_uses_request_tenant_id_contextvar(monkeypatch):
    """When _current_request_tenant_id contextvar is set, the dev loader must
    return CurrentUser.tenant_id from the contextvar, NOT from user_id.

    This is the fix for the 403 TENANT_MISMATCH bug: validate_tenant_id in
    billing compares x-tenant-id header against current_user.tenant_id.  The
    old loader set tenant_id=user_id (b0000000-...) which never matched the
    real tenant header (a0000000-...).
    """
    monkeypatch.setenv("INFINITYRX_ENV", "development")
    configure_auth_trust_jwt()
    loader = auth_dep._user_loader
    assert loader is not None

    user_id = uuid.UUID("b0000000-0000-0000-0000-000000000001")
    tenant_id = uuid.UUID("a0000000-0000-0000-0000-000000000001")

    # Simulate get_current_user() setting the contextvar before calling the loader.
    token = auth_dep._current_request_tenant_id.set(tenant_id)
    try:
        user = loader(user_id)
    finally:
        auth_dep._current_request_tenant_id.reset(token)

    assert user.id == user_id
    assert user.tenant_id == tenant_id, (
        f"Expected tenant_id={tenant_id}, got {user.tenant_id}. "
        "dev_trust_jwt loader must read _current_request_tenant_id contextvar."
    )


def test_loader_falls_back_to_user_id_when_contextvar_not_set(monkeypatch):
    """When no contextvar is set (test isolation), loader falls back gracefully.
    This preserves backward compat for any existing test that calls the loader
    directly without setting the contextvar.
    """
    monkeypatch.setenv("INFINITYRX_ENV", "development")
    configure_auth_trust_jwt()
    loader = auth_dep._user_loader
    assert loader is not None

    # Ensure contextvar is cleared
    auth_dep._current_request_tenant_id.set(None)

    user_id = uuid.UUID("b0000000-0000-0000-0000-000000000001")
    user = loader(user_id)
    # Fallback: tenant_id == user_id (old behavior, keeps existing tests green)
    assert user.id == user_id
    assert user.status == "active"


def test_dev_loader_includes_operator_and_approver_roles(monkeypatch):
    """The dev trust-JWT loader must grant operator + approver roles so that
    the platform_admin dev user can call write endpoints on billing/uploads
    without hitting the RBAC 403 (only operator/approver may upload).
    """
    monkeypatch.setenv("INFINITYRX_ENV", "development")
    configure_auth_trust_jwt()
    loader = auth_dep._user_loader
    assert loader is not None

    user_id = uuid.UUID("b0000000-0000-0000-0000-000000000001")
    user = loader(user_id)
    assert "operator" in user.roles, "dev loader must include 'operator' role for upload RBAC"
    assert "approver" in user.roles, "dev loader must include 'approver' role for upload RBAC"
