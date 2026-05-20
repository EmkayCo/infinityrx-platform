"""Integration test: auth_api_router is mounted in create_app() and reachable.

LESSON-006 enforcement: these tests ONLY pass if auth_api_router is actually
included in the production app, the session dependency is wired through the
shim, the shared auth user loader is configured, and the tenant isolation
middleware has the anonymous-path allowlist for login. A unit test on any
single piece is insufficient â€” it cannot prove the router is on the live
request path behind the full middleware stack.

If any piece of that wiring regresses, one of these tests fails at the
boundary that broke, pointing directly at the LESSON-006 gap.
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from shared.auth.jwt_tokens import create_access_token
from shared.auth.passwords import hash_password
from src import main as main_module
from src._shim import db as db_shim
from src.auth._models import Base as AuthBase
from src.auth._models import Tenant, User
from src.auth.seed.system_roles import seed_system_roles
from src.auth.service import _assign_roles  # noqa: PLC2701  (intentional test access)


def _build_live_app():
    """Create the production app with lifespan startup stubbed.

    Returns ``(app, ExitStack)`` â€” the caller MUST call ``stack.close()``
    (or use the stack as a context manager) to undo the patches AFTER the
    TestClient exits.  The patches must remain active for the full duration
    of the TestClient context because the lifespan fires when the client
    starts up, not when ``create_app()`` is called.

    The autouse ``_fresh_db`` fixture in tests/conftest.py has already
    configured the shim engine to a per-test SQLite. We also have to
    create the auth tables on that same engine because they live on
    ``src.auth._models.Base`` â€” a different declarative base than the
    shim's own ``Base`` that ``_fresh_db`` runs ``create_all`` against.

    Returns ``(app, stack)`` â€” caller MUST call ``stack.close()`` when done.
    The patches must stay active through ``TestClient(app).__enter__()``
    because the lifespan resolves patched names at call time (not import time).
    """
    AuthBase.metadata.create_all(db_shim.get_engine())
    stack = ExitStack()
    stack.enter_context(patch.object(main_module, "_verify_database", AsyncMock()))
    stack.enter_context(patch.object(main_module, "get_event_bus", return_value=AsyncMock()))
    stack.enter_context(patch.object(main_module, "dispose_engine", AsyncMock()))
    stack.enter_context(patch.object(main_module, "reset_event_bus"))
    app = main_module.create_app()
    return app, stack


def _seed_admin_user() -> User:
    """Seed one tenant + one tenant_admin user through the shim session."""
    AuthBase.metadata.create_all(db_shim.get_engine())
    SessionLocal = db_shim.get_sessionmaker()
    with SessionLocal() as session:
        seed_system_roles(session)
        tenant = Tenant(name="TestTenant", slug="test-tenant", status="active")
        session.add(tenant)
        session.flush()
        user = User(
            tenant_id=tenant.id,
            email="admin@example.com",
            display_name="Test Admin",
            password_hash=hash_password("password-not-used-in-jwt-tests"),
            status="active",
        )
        session.add(user)
        session.flush()
        _assign_roles(session, user, ["tenant_admin"])
        session.commit()
        session.refresh(user)
        # Detach a plain DTO so the caller can use the ids after the
        # session closes without running into lazy-load errors.
        return user


def test_auth_router_mounted_users_list_returns_200() -> None:
    """GET /api/v1/users must return 200 through the real create_app() stack.

    Proves:
      1. ``auth_api_router`` is included in ``create_app()`` (path resolves;
         this would be 404 if the router wasn't mounted).
      2. The session dependency override in ``create_app()`` wires
         ``auth._db.get_session`` to the shim sessionmaker.
      3. ``configure_core_auth()`` installs the shared ``CurrentUser`` loader
         so ``tenant_admin_only`` can resolve the JWT's user_id to a real
         ORM user with roles.
      4. ``TenantIsolationMiddleware`` lets a valid bearer through to the
         route (not 401'd at the wall).
    """
    admin = _seed_admin_user()
    tenant_id = admin.tenant_id
    admin_id = admin.id

    app, stack = _build_live_app()
    token = create_access_token(admin_id, tenant_id, ["tenant_admin"])

    with stack, TestClient(app) as client:
        resp = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
        )


    assert resp.status_code == 200, (
        f"auth_api_router must be mounted in create_app() and the session "
        f"dependency must be overridden â€” LESSON-006. "
        f"Got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert isinstance(body, list), f"expected list, got {type(body).__name__}: {body}"
    emails = [u["email"] for u in body]
    assert "admin@example.com" in emails, f"seeded admin not in list: {emails}"


def test_auth_router_mounted_no_token_returns_401_not_404() -> None:
    """Unauthenticated GET /api/v1/users must be rejected by the tenant
    isolation middleware with 401 â€” not 404.

    A 404 would indicate the route isn't mounted at all. A 401 proves the
    request reached the middleware stack that guards the mounted route.
    """
    app, stack = _build_live_app()
    with stack, TestClient(app) as client:
        resp = client.get("/api/v1/users")


    assert resp.status_code == 401, (
        f"route must exist and middleware must 401 unauth callers (not 404). "
        f"Got {resp.status_code}: {resp.text}"
    )


def test_login_endpoint_reachable_without_auth_header() -> None:
    """POST /api/v1/auth/login must reach the handler without a bearer token.

    Without the unauthenticated-path allowlist on TenantIsolationMiddleware,
    every login attempt would 401 at the middleware wall â€” breaking the
    entire login flow in prod. This test proves the allowlist is wired by
    checking that the middleware does NOT intercept: invalid credentials
    return a 401 whose body is shaped like the handler's response
    (``{detail: {error: "invalid_credentials", ...}}``), not the middleware's
    (``{error: "unauthenticated", detail: "Missing or invalid credentials"}``).
    """
    _seed_admin_user()  # schema + a user to query against
    app, stack = _build_live_app()

    # Use an RFC-2606 test domain so Pydantic's EmailStr validator accepts
    # the value. `.local` is rejected as a reserved TLD by email-validator.
    with stack, TestClient(app) as client:
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrongpass"},
        )


    assert resp.status_code == 401, resp.text
    body = resp.json()
    # Plan E B7: core-platform now wraps every HTTPException in the canonical
    # envelope {"error": {"code", "message", "correlation_id"}}. Reaching the
    # handler returns the canonical envelope; the middleware bypass would
    # return a different shape with `error` as a STRING. We distinguish by
    # asserting body.error is a dict with the canonical "code" key.
    err = body.get("error")
    assert isinstance(err, dict) and err.get("code") == "UNAUTHORIZED", (
        f"login endpoint must be reached (not blocked by middleware). body: {body}"
    )


def test_auth_router_mounted_route_path_exists() -> None:
    """Structural check: /api/v1/users* paths are in the app's route table.

    A fast, no-HTTP sanity check that complements the end-to-end tests.
    Fails fast if someone drops ``app.include_router(auth_api_router)``.
    """
    app, stack = _build_live_app()
    stack.close()  # no lifespan needed â€” route table is set at create_app() time

    paths = {getattr(r, "path", "") for r in app.routes}
    assert any(p == "/api/v1/users" for p in paths), (
        f"/api/v1/users not in routes â€” auth_api_router not mounted. "
        f"paths: {sorted(paths)}"
    )
    assert any(p == "/api/v1/auth/login" for p in paths), (
        f"/api/v1/auth/login not in routes â€” auth_api_router not mounted. "
        f"paths: {sorted(paths)}"
    )


def test_tenant_resolver_rejects_revoked_token_via_middleware() -> None:
    """_TenantResolver must return None for revoked tokens.

    Defense-in-depth: tenant context must NOT be set when the token is in the
    revocation list, so the middleware 401s before any route logic executes.
    This verifies that _TenantResolver routes through get_current_user (which
    checks the revocation repo) rather than calling decode_token directly.
    """
    from datetime import datetime, timezone, timedelta
    from shared.auth.dependencies import configure_auth
    from shared.auth.jwt_tokens import decode_token
    from shared.auth.tokens_repo import InMemoryRevokedTokenRepo
    from src.auth.wiring import build_user_loader

    admin = _seed_admin_user()
    tenant_id = admin.tenant_id
    admin_id = admin.id

    # Build the live app first (its create_app() calls configure_core_auth
    # internally, installing a fresh InMemoryRevokedTokenRepo). We then
    # replace the repo with one that holds a revoked entry AFTER app creation.
    app, stack = _build_live_app()

    repo = InMemoryRevokedTokenRepo()
    SessionLocal = db_shim.get_sessionmaker()
    # Re-configure auth with our repo that has the revocation entry.
    configure_auth(build_user_loader(SessionLocal), repo)

    token = create_access_token(admin_id, tenant_id, ["tenant_admin"])
    # Decode to get jti, then immediately revoke it
    claims = decode_token(token)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    repo.revoke(claims.jti, tenant_id, expires_at)

    with stack, TestClient(app) as client:
        resp = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
        )

    # Middleware must 401 with its own response shape — distinguishes middleware-level
    # rejection from route-level get_current_user rejection.
    # Middleware shape: {"error": "unauthenticated", "detail": "Missing or invalid credentials"}
    # Route-level shape: {"detail": {"error": "unauthorized", "message": "..."}}
    assert resp.status_code == 401, (
        f"_TenantResolver must reject revoked tokens via get_current_user. "
        f"Got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body.get("error") == "unauthenticated", (
        "Response must be the middleware-level 401 (not a route-level auth rejection). "
        f"Expected error='unauthenticated' but got: {body}"
    )


def test_tenant_resolver_rejects_inactive_user() -> None:
    """_TenantResolver must return None for tokens belonging to inactive users.

    Defense-in-depth: tenant context must NOT be set when the user's status is
    not 'active', so the middleware 401s before any route logic executes.
    This verifies that _TenantResolver routes through get_current_user (which
    checks user.status) rather than only doing JWT signature verification.
    """
    from shared.auth.dependencies import configure_auth
    from shared.auth.tokens_repo import InMemoryRevokedTokenRepo
    from src.auth.wiring import build_user_loader

    # Seed a suspended user
    AuthBase.metadata.create_all(db_shim.get_engine())
    SessionLocal = db_shim.get_sessionmaker()
    with SessionLocal() as session:
        seed_system_roles(session)
        tenant = Tenant(name="InactiveTestTenant", slug="inactive-test-tenant", status="active")
        session.add(tenant)
        session.flush()
        user = User(
            tenant_id=tenant.id,
            email="suspended@example.com",
            display_name="Suspended User",
            password_hash=hash_password("irrelevant"),
            status="suspended",
        )
        session.add(user)
        session.flush()
        _assign_roles(session, user, ["tenant_admin"])
        session.commit()
        session.refresh(user)
        user_id = user.id
        tenant_id = user.tenant_id

    token = create_access_token(user_id, tenant_id, ["tenant_admin"])

    # Build live app first (its create_app() calls configure_core_auth with a
    # fresh repo), then re-configure auth so our loader is active for the request.
    app, stack = _build_live_app()
    repo = InMemoryRevokedTokenRepo()
    configure_auth(build_user_loader(SessionLocal), repo)

    with stack, TestClient(app) as client:
        resp = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
        )

    # Middleware must 401 with its own response shape — distinguishes middleware-level
    # rejection from route-level get_current_user rejection.
    assert resp.status_code == 401, (
        f"_TenantResolver must reject inactive users via get_current_user. "
        f"Got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body.get("error") == "unauthenticated", (
        "Response must be the middleware-level 401 (not a route-level auth rejection). "
        f"Expected error='unauthenticated' but got: {body}"
    )
