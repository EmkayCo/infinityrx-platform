"""Unit tests for SP-3 role + MFA + tenant-header dependencies (R1 BLOCK 2/3/4 fix)."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from shared.auth import dependencies as shared_auth
from shared.auth.dependencies import CurrentUser

from src.api.dependencies import (
    RECLAIMRX_VIEWER_DEP,
    RECLAIMRX_INVESTIGATOR_DEP,
    RECLAIMRX_ADMIN_DEP,
    require_mfa_elevated,
    require_tenant_match,
)


def _user(roles: list[str], tenant_id: uuid.UUID | None = None) -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        email="t@example.com",
        status="active",
        roles=tuple(roles),
        permissions=tuple(),
    )


# ── Role dependencies (R1 BLOCK 2) ─────────────────────────────────────────────

def test_viewer_dep_is_depends_object():
    """RECLAIMRX_VIEWER_DEP must be a FastAPI Depends wrapper."""
    from fastapi.params import Depends as _Depends
    assert isinstance(RECLAIMRX_VIEWER_DEP, _Depends)


def test_investigator_dep_is_depends_object():
    from fastapi.params import Depends as _Depends
    assert isinstance(RECLAIMRX_INVESTIGATOR_DEP, _Depends)


def test_admin_dep_is_depends_object():
    from fastapi.params import Depends as _Depends
    assert isinstance(RECLAIMRX_ADMIN_DEP, _Depends)


def test_investigator_satisfies_viewer():
    """Investigator role implies viewer access (spec §5.4)."""
    u = _user(["reclaimrx.investigator"])
    dep = shared_auth.require_roles("reclaimrx.viewer", "reclaimrx.investigator", "reclaimrx.admin")
    assert dep(user=u) is u


def test_admin_satisfies_viewer():
    u = _user(["reclaimrx.admin"])
    dep = shared_auth.require_roles("reclaimrx.viewer", "reclaimrx.investigator", "reclaimrx.admin")
    assert dep(user=u) is u


def test_viewer_blocked_on_investigator_dep():
    u = _user(["reclaimrx.viewer"])
    dep = shared_auth.require_roles("reclaimrx.investigator", "reclaimrx.admin")
    with pytest.raises(HTTPException) as exc:
        dep(user=u)
    assert exc.value.status_code == 403


def test_admin_only_blocks_investigator():
    u = _user(["reclaimrx.investigator"])
    dep = shared_auth.require_roles("reclaimrx.admin")
    with pytest.raises(HTTPException) as exc:
        dep(user=u)
    assert exc.value.status_code == 403


def test_legacy_role_strings_rejected():
    """'investigator' (no prefix) must not satisfy reclaimrx.viewer."""
    u = _user(["investigator", "tenant_admin"])
    dep = shared_auth.require_roles("reclaimrx.viewer", "reclaimrx.investigator", "reclaimrx.admin")
    with pytest.raises(HTTPException):
        dep(user=u)


# ── MFA dependency (R1 BLOCK 3) ────────────────────────────────────────────────

def test_mfa_required_returns_403_not_503(monkeypatch):
    """MFA-not-elevated MUST return 403 MFA_REQUIRED, not 503."""
    monkeypatch.delenv("RECLAIMRX_MFA_BYPASS", raising=False)
    u = _user(["reclaimrx.viewer"])
    with pytest.raises(HTTPException) as exc:
        require_mfa_elevated(user=u, session_lookup=_unelevated_session_lookup_stub)
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "MFA_REQUIRED"


def test_mfa_passes_when_session_elevated(monkeypatch):
    monkeypatch.delenv("RECLAIMRX_MFA_BYPASS", raising=False)
    u = _user(["reclaimrx.viewer"])
    result = require_mfa_elevated(user=u, session_lookup=_elevated_session_lookup_stub)
    assert result is u


def test_mfa_bypass_env_var_skips_check(monkeypatch):
    """RECLAIMRX_MFA_BYPASS=1 passes through without checking session."""
    monkeypatch.setenv("RECLAIMRX_MFA_BYPASS", "1")
    u = _user(["reclaimrx.viewer"])
    result = require_mfa_elevated(user=u, session_lookup=_unelevated_session_lookup_stub)
    assert result is u


def test_mfa_none_session_fails_closed(monkeypatch):
    """None from session_lookup must fail closed with 403."""
    monkeypatch.delenv("RECLAIMRX_MFA_BYPASS", raising=False)
    u = _user(["reclaimrx.viewer"])
    with pytest.raises(HTTPException) as exc:
        require_mfa_elevated(user=u, session_lookup=lambda uid: None)
    assert exc.value.status_code == 403


def _elevated_session_lookup_stub(user_id):
    from datetime import UTC, datetime, timedelta
    return {"mfa_elevated_until": datetime.now(UTC) + timedelta(minutes=10)}


def _unelevated_session_lookup_stub(user_id):
    return {"mfa_elevated_until": None}


# ── Tenant header dependency (R1 BLOCK 4) ──────────────────────────────────────

def test_tenant_header_match_passes():
    tid = uuid.uuid4()
    u = _user(["reclaimrx.viewer"], tenant_id=tid)
    assert require_tenant_match(x_tenant_id=str(tid), user=u) is u


def test_tenant_header_mismatch_returns_403_tenant_mismatch():
    u = _user(["reclaimrx.viewer"])  # random tenant
    with pytest.raises(HTTPException) as exc:
        require_tenant_match(x_tenant_id=str(uuid.uuid4()), user=u)
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "TENANT_MISMATCH"


def test_tenant_header_invalid_uuid_returns_400():
    u = _user(["reclaimrx.viewer"])
    with pytest.raises(HTTPException) as exc:
        require_tenant_match(x_tenant_id="not-a-uuid", user=u)
    assert exc.value.status_code == 400
    assert exc.value.detail["error"]["code"] == "INVALID_TENANT_HEADER"


def test_tenant_header_missing_returns_400():
    u = _user(["reclaimrx.viewer"])
    with pytest.raises(HTTPException) as exc:
        require_tenant_match(x_tenant_id=None, user=u)
    assert exc.value.status_code == 400
    assert exc.value.detail["error"]["code"] == "INVALID_TENANT_HEADER"
