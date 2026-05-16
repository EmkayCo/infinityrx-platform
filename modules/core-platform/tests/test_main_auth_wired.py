"""Integration test: auth_api_router is mounted in create_app() and reachable.

LESSON-006 enforcement: these tests ONLY pass if auth_api_router is actually
included in the production app, the session dependency is wired through the
shim, the shared auth user loader is configured, and the tenant isolation
middleware has the anonymous-path allowlist for login. A unit test on any
single piece is insufficient — it cannot prove the router is on the live
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

    Returns ``(app, ExitStack)`` — the caller MUST call ``stack.close()``
    (or use the stack as a context manager) to undo the patches AFTER the
    TestClient exits.  The patches must remain active for the full duration
    of the TestClient context because the lifespan fires when the client
    starts up, not when ``create_app()`` is called.

    The autouse ``_fresh_db`` fixture in tests/conftest.py has already
    configured the shim engine to a per-test SQLite. We also have to
    create the auth tables on that same engine because they live on
    ``src.auth._models.Base`` — a different declarative base than the
    shim's own ``Base`` that ``_fresh_db`` runs ``create_all`` against.
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
        f"dependency must be overridden — LESSON-006. "
        f"Got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert isinstance(body, list), f"expected list, got {type(body).__name__}: {body}"
    emails = [u["email"] for u in body]
    assert "admin@example.com" in emails, f"seeded admin not in list: {emails}"


def test_auth_router_mounted_no_token_returns_401_not_404() -> None:
    """Unauthenticated GET /api/v1/users must be rejected by the tenant
    isolation middleware with 401 — not 404.

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
    every login attempt would 401 at the middleware wall — breaking the
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
    detail = body.get("detail")
    assert isinstance(detail, dict) and detail.get("error") == "invalid_credentials", (
        f"login endpoint must be reached (not blocked by middleware). "
        f"body: {body}"
    )


def test_auth_router_mounted_route_path_exists() -> None:
    """Structural check: /api/v1/users* paths are in the app's route table.

    A fast, no-HTTP sanity check that complements the end-to-end tests.
    Fails fast if someone drops ``app.include_router(auth_api_router)``.
    """
    app, stack = _build_live_app()
    stack.close()  # no lifespan needed — route table is set at create_app() time
    paths = {getattr(r, "path", "") for r in app.routes}
    assert any(p == "/api/v1/users" for p in paths), (
        f"/api/v1/users not in routes — auth_api_router not mounted. "
        f"paths: {sorted(paths)}"
    )
    assert any(p == "/api/v1/auth/login" for p in paths), (
        f"/api/v1/auth/login not in routes — auth_api_router not mounted. "
        f"paths: {sorted(paths)}"
    )
