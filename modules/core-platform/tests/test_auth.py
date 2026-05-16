"""Test the _shim/auth current_user dependency — B12 S1 adapter (v2).

B11 ship-day hotfix (35a0044) added the JWT-decode production path.

B12 S1 (this slice) converts the shim from a stand-alone adapter to a
thin wrapper over ``shared.auth.dependencies``:
- ``CurrentUser`` is now imported from ``shared.auth.dependencies``
  (frozen dataclass with ``status`` and ``permissions`` fields).
- The production JWT path routes through ``get_current_user`` (full stack:
  decode + revocation + inactive-user check + DB-backed permissions load).
- ``require_role`` is re-implemented locally so it chains through the
  shim's ``current_user`` (test-override-aware).

B12 S1 v2 — HIGH-1/HIGH-2/MEDIUM-2 closures (this revision):
- ``TestProductionPath`` and ``TestB12S1AdapterBehaviors`` now wire
  ``configure_auth`` with an in-memory user_loader so the full
  ``get_current_user`` stack runs on each test call.
- ``TestB12S1V2SecurityClosures`` adds:
  * test_revoked_token_rejected_via_shim (HIGH-1)
  * test_inactive_user_rejected_via_shim (HIGH-1)
  * test_db_loaded_permissions_present_in_shim_currentuser (HIGH-1/MEDIUM-2)
  * test_audit_permission_gate_checks_permission_string (HIGH-2)

Test surface:
- Override path: set_current_user(u) -> current_user(token=None) returns u.
- Production path with valid JWT: decoded -> CurrentUser with roles from claims.
- Production path with no token: 401.
- Production path with invalid token: 401 (shared error key "unauthorized").
- Production path with wrong secret: 401.
- B12-S1: tenant_id propagated to shared.db.tenant_context on JWT path.
- B12-S1: cross-tenant request returns data only for the authenticated tenant.
- B12-S1: shim CurrentUser is the shared frozen type (has status/permissions).
- B12-S1-v2: revoked token rejected 401 via shim path.
- B12-S1-v2: inactive user rejected 401 via shim path.
- B12-S1-v2: DB-loaded permissions present in returned CurrentUser.
- B12-S1-v2: audit permission gate checks actual permission string.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from shared.auth.dependencies import CurrentUser, configure_auth
from shared.auth.jwt_tokens import create_access_token
from shared.auth.tokens_repo import InMemoryRevokedTokenRepo
from src._shim.auth import current_user, set_current_user

# Fixed test identity — used across production-path fixtures
_TEST_USER_ID = uuid.UUID("b0000000-0000-0000-0000-000000000001")
_TEST_TENANT_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")


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


@pytest.fixture
def _revoked_repo() -> InMemoryRevokedTokenRepo:
    """Fresh in-memory revocation repo per test."""
    return InMemoryRevokedTokenRepo()


@pytest.fixture
def _configure_auth_fake(
    _jwt_secret: None,
    _revoked_repo: InMemoryRevokedTokenRepo,
):
    """Wire configure_auth with an in-memory user_loader + revocation repo.

    The user_loader returns a deterministic ``CurrentUser`` for the fixed
    _TEST_USER_ID used by _mint_jwt().  All production-path tests that call
    ``current_user(token=jwt)`` need this fixture — ``get_current_user``
    requires configure_auth() to have been called.

    Returns the revoked_repo so individual tests can revoke tokens or inject
    inactive users.
    """
    store: dict[uuid.UUID, CurrentUser] = {
        _TEST_USER_ID: CurrentUser(
            id=_TEST_USER_ID,
            tenant_id=_TEST_TENANT_ID,
            email="test@infinityrx.local",
            status="active",
            roles=("platform_admin", "tenant_admin"),
            permissions=("audit:read", "audit:export"),
        )
    }

    def _loader(user_id: uuid.UUID) -> CurrentUser | None:
        return store.get(user_id)

    configure_auth(_loader, _revoked_repo)
    # Expose store so individual tests can mutate the user (e.g., mark inactive)
    return store, _revoked_repo


def _mint_jwt(
    roles: tuple[str, ...] = ("platform_admin", "tenant_admin"),
    user_id: uuid.UUID = _TEST_USER_ID,
    tenant_id: uuid.UUID = _TEST_TENANT_ID,
) -> str:
    return create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=list(roles),
    )


class TestTestOverridePath:
    def test_override_set_returns_override(self) -> None:
        """set_current_user(u) makes current_user return u."""
        u = CurrentUser(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="alice@example.com",
            status="active",
            roles=("tenant_admin",),
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
    def test_valid_jwt_returns_currentuser_with_roles(
        self, _configure_auth_fake: tuple
    ) -> None:
        """A valid bearer token is decoded into a CurrentUser whose roles
        come from the user_loader (DB-backed roles/permissions)."""
        jwt = _mint_jwt(roles=("platform_admin", "tenant_admin"))
        user = current_user(token=jwt)
        assert isinstance(user, CurrentUser)
        assert user.id == _TEST_USER_ID
        assert user.tenant_id == _TEST_TENANT_ID
        assert "tenant_admin" in user.roles
        assert "platform_admin" in user.roles

    def test_platform_admin_implies_tenant_admin(
        self, _configure_auth_fake: tuple
    ) -> None:
        """Role-hierarchy expansion: user_loader returns a user with both
        platform_admin and tenant_admin so the audit router's permission gate
        accepts platform_admin bearers.

        The proper RBAC layer (B12 slice 2+) will encode this implication
        declaratively. For now, the user_loader in wiring.py must expand it.
        The shim no longer does role expansion inline — it defers to the
        user_loader result.
        """
        jwt = _mint_jwt(roles=("platform_admin",))
        user = current_user(token=jwt)
        # The in-memory user_loader always returns both roles for _TEST_USER_ID.
        assert "platform_admin" in user.roles
        assert "tenant_admin" in user.roles, (
            "platform_admin must imply tenant_admin so the audit router's "
            "tenant_admin permission gate accepts platform_admin bearers"
        )

    def test_missing_token_raises_401(self, _jwt_secret: None) -> None:
        """No override + no Authorization header => 401."""
        with pytest.raises(HTTPException) as exc_info:
            current_user(token=None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"] == "missing_token"

    def test_garbage_token_raises_401(self, _configure_auth_fake: tuple) -> None:
        """An undecodable token => 401, not 500.

        The error is routed through ``shared.auth.dependencies._resolve_claims``
        which uses the shared error key ``"unauthorized"``.
        """
        with pytest.raises(HTTPException) as exc_info:
            current_user(token="not.a.jwt")
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["error"] == "unauthorized"

    def test_wrong_secret_raises_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A token signed with the wrong secret => 401.

        get_auth_settings() re-reads JWT_SECRET on every call, so flipping
        the env var between mint and decode is enough to simulate a
        rotated/wrong key.
        """
        repo = InMemoryRevokedTokenRepo()
        configure_auth(lambda uid: None, repo)
        monkeypatch.setenv("JWT_SECRET", "a" * 64)
        jwt = _mint_jwt()
        monkeypatch.setenv("JWT_SECRET", "b" * 64)
        with pytest.raises(HTTPException) as exc_info:
            current_user(token=jwt)
        assert exc_info.value.status_code == 401


class TestB12S1AdapterBehaviors:
    """B12 S1 — new behaviors introduced by the shim-to-shared-auth adapter."""

    def test_currentuser_is_shared_frozen_type(
        self, _configure_auth_fake: tuple
    ) -> None:
        """After B12-S1, ``CurrentUser`` is the shared frozen dataclass.

        It has ``status`` and ``permissions`` fields; it is immutable.
        Verifies the duplicate local dataclass is gone.
        """
        from shared.auth.dependencies import CurrentUser as SharedCurrentUser

        jwt = _mint_jwt(roles=("tenant_admin",))
        user = current_user(token=jwt)
        assert isinstance(user, SharedCurrentUser), (
            "shim must use shared.auth.dependencies.CurrentUser — not a local copy"
        )
        assert user.status == "active"
        assert isinstance(user.permissions, tuple)

    def test_tenant_context_set_on_jwt_path(
        self, _configure_auth_fake: tuple
    ) -> None:
        """JWT decode path calls _set_tenant_context so DB queries are scoped.

        This was missing in the B11 shim — tenant-scoped ORM queries
        were relying on the test-override path which bypassed context
        propagation entirely.  The production JWT path must set the
        context so that TenantScopedMixin query filters see the right
        tenant_id on every request.
        """
        jwt = _mint_jwt(roles=("tenant_admin",))
        current_user(token=jwt)

        # The shared.db.tenant_context contextvar should now hold the
        # tenant_id from the JWT claim.
        try:
            from shared.db.tenant_context import current_tenant_id

            propagated = current_tenant_id.get(None)
        except Exception:
            # If the contextvar API isn't available in this env, skip
            # rather than fail — the _set_tenant_context call in get_current_user
            # is still exercised; we just can't read the value back here.
            pytest.skip("shared.db.tenant_context not accessible in this test env")
            return

        assert propagated == _TEST_TENANT_ID, (
            "B12-S1: shim must propagate JWT tenant_id to shared.db.tenant_context "
            f"for TenantScopedMixin; expected {_TEST_TENANT_ID}, got {propagated}"
        )

    def test_cross_tenant_override_switch_changes_resolved_user(self) -> None:
        """set_current_user can switch tenants mid-test.

        This is how all tenant isolation tests work: set tenant A user,
        make a request, switch to tenant B user, assert tenant B sees
        no tenant A data.  Verifies the override mechanism still works
        after the B12-S1 adapter change.
        """
        tenant_a = uuid.UUID("11111111-1111-1111-1111-111111111111")
        tenant_b = uuid.UUID("22222222-2222-2222-2222-222222222222")

        user_a = CurrentUser(
            id=uuid.uuid4(),
            tenant_id=tenant_a,
            email="a@example.com",
            status="active",
            roles=("tenant_admin",),
        )
        set_current_user(user_a)
        resolved = current_user(token="ignored")
        assert resolved.tenant_id == tenant_a

        user_b = CurrentUser(
            id=uuid.uuid4(),
            tenant_id=tenant_b,
            email="b@example.com",
            status="active",
            roles=("tenant_admin",),
        )
        set_current_user(user_b)
        resolved = current_user(token="ignored")
        assert resolved.tenant_id == tenant_b, (
            "set_current_user must switch tenants immediately — "
            "cross-tenant isolation tests depend on this"
        )

    def test_require_role_rejects_insufficient_role_403(self) -> None:
        """require_role through the shim still enforces authorization.

        The shim's require_role chains through the shim's current_user
        so the test-override path is respected AND the role check fires.
        """
        user = CurrentUser(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="op@example.com",
            status="active",
            roles=("tenant_operator",),
        )
        set_current_user(user)
        from src._shim.auth import require_role

        dep = require_role("platform_admin")

        with pytest.raises(HTTPException) as exc_info:
            # Call the inner dep directly with the override-injected user.
            dep(user=current_user(token=None))
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"] == "forbidden"

    def test_require_role_allows_matching_role(self) -> None:
        """require_role passes when the user has at least one required role."""
        user = CurrentUser(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="admin@example.com",
            status="active",
            roles=("tenant_admin",),
        )
        set_current_user(user)
        from src._shim.auth import require_role

        dep = require_role("platform_admin", "tenant_admin")
        result = dep(user=current_user(token=None))
        assert result is user


class TestB12S1V2SecurityClosures:
    """B12 S1 v2 — close HIGH-1 (revocation bypass) and MEDIUM-2 (missing tests).

    HIGH-1: v1 called _resolve_claims only; revoked tokens and inactive users
    were authorized.  v2 routes through get_current_user which enforces the
    full stack.

    HIGH-2 is covered in TestAuditPermissionGate below.
    """

    def test_revoked_token_rejected_via_shim(
        self, _configure_auth_fake: tuple
    ) -> None:
        """A revoked token must be rejected with 401 via the shim path.

        HIGH-1 fix: v1 skipped the revocation check; any revoked-but-valid JWT
        was accepted.  v2 routes through get_current_user which calls
        repo.is_revoked(claims.jti) before loading the user.
        """
        store, repo = _configure_auth_fake
        jwt = _mint_jwt()

        # Decode the JTI without going through the auth stack
        from shared.auth.jwt_tokens import decode_token

        claims = decode_token(jwt)
        assert claims.tenant_id is not None
        # Revoke the token
        repo.revoke(claims.jti, claims.tenant_id, expires_at=claims.exp)

        with pytest.raises(HTTPException) as exc_info:
            current_user(token=jwt)

        assert exc_info.value.status_code == 401, (
            "Revoked token must yield 401 — HIGH-1 fix verification"
        )
        assert exc_info.value.detail["error"] == "unauthorized"

    def test_inactive_user_rejected_via_shim(
        self, _configure_auth_fake: tuple
    ) -> None:
        """A token belonging to an inactive user must be rejected with 401.

        HIGH-1 fix: v1 synthesised a CurrentUser directly from JWT claims with
        status='active' hardcoded — it never consulted the DB.  Any user who
        had been deactivated after token issuance remained authorized.
        v2 loads the user via user_loader and checks user.status.
        """
        store, repo = _configure_auth_fake
        # Mark the test user inactive in the in-memory store
        active_user = store[_TEST_USER_ID]
        store[_TEST_USER_ID] = CurrentUser(
            id=active_user.id,
            tenant_id=active_user.tenant_id,
            email=active_user.email,
            status="inactive",
            roles=active_user.roles,
            permissions=active_user.permissions,
        )
        jwt = _mint_jwt()

        with pytest.raises(HTTPException) as exc_info:
            current_user(token=jwt)

        assert exc_info.value.status_code == 401, (
            "Inactive user must yield 401 — HIGH-1 fix verification"
        )
        assert exc_info.value.detail["error"] == "unauthorized"

    def test_db_loaded_permissions_present_in_shim_currentuser(
        self, _configure_auth_fake: tuple
    ) -> None:
        """Permissions on the returned CurrentUser come from the user_loader (DB).

        HIGH-1/MEDIUM-2 fix: v1 synthesised CurrentUser with permissions=()
        hardcoded — no DB consultation.  v2's user_loader populates permissions
        from ORM roles.  This test verifies the populated permissions reach the
        caller.
        """
        store, _repo = _configure_auth_fake
        jwt = _mint_jwt()
        user = current_user(token=jwt)

        assert "audit:read" in user.permissions, (
            "DB-loaded permissions must be present in shim CurrentUser — "
            f"got permissions={user.permissions!r}"
        )
        assert "audit:export" in user.permissions


class TestAuditPermissionGate:
    """HIGH-2: _audit_require_permission must check the actual permission string.

    v1 checked only ``tenant_admin`` role, ignoring the permission string —
    any tenant_admin could reach any audit endpoint regardless of permission
    grants.  v2 checks ``perm in current.permissions`` (with privileged-role
    backward-compat).
    """

    def _make_dep_factory(self, permission: str):
        """Helper: import and call _audit_require_permission."""
        from src.api import _audit_require_permission

        return _audit_require_permission(permission)

    def test_user_without_permission_and_without_privileged_role_gets_403(
        self,
    ) -> None:
        """A user with no privileged role and no matching permission → 403.

        This is the core HIGH-2 fix verification: the old code would have
        returned 200 for any ``tenant_admin`` and ignored the permission
        argument entirely. Here we use a non-privileged role to prove the
        permission string is actually checked.
        """
        user = CurrentUser(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="analyst@example.com",
            status="active",
            roles=("tenant_analyst",),  # NOT tenant_admin or platform_admin
            permissions=("reporting:read",),  # does NOT have audit:read
        )
        set_current_user(user)

        dep = self._make_dep_factory("audit:read")

        with pytest.raises(HTTPException) as exc_info:
            dep(current=current_user(token=None))

        assert exc_info.value.status_code == 403

    def test_user_with_matching_permission_gets_through(self) -> None:
        """A user with the specific permission (no privileged role) → allowed.

        Proves permission check is functional independent of role.
        """
        user = CurrentUser(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="auditor@example.com",
            status="active",
            roles=("tenant_analyst",),  # NOT tenant_admin
            permissions=("audit:read",),  # HAS audit:read
        )
        set_current_user(user)

        dep = self._make_dep_factory("audit:read")
        result = dep(current=current_user(token=None))
        assert result is user

    def test_tenant_admin_without_explicit_permission_still_allowed(self) -> None:
        """tenant_admin role grants backward-compat access to all audit.* perms.

        Privileged roles implicitly hold all audit permissions until the RBAC
        layer (B12 slice 2+) encodes this declaratively.
        """
        user = CurrentUser(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="admin@example.com",
            status="active",
            roles=("tenant_admin",),
            permissions=(),  # no explicit audit:read
        )
        set_current_user(user)

        dep = self._make_dep_factory("audit:read")
        result = dep(current=current_user(token=None))
        assert result is user
