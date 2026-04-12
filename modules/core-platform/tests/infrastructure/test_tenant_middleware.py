"""Tests for the tenant isolation ASGI middleware."""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from infrastructure.tenant_middleware import (
    AuthContext,
    TenantIsolationMiddleware,
    tenant_exempt_route,
)
from shared.db.tenant_context import current_tenant_id


TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()
USER_A = uuid.uuid4()


async def _who_am_i(request):  # type: ignore[no-untyped-def]
    return JSONResponse({"tenant": str(current_tenant_id.get())})


async def _crash(request):  # type: ignore[no-untyped-def]
    raise RuntimeError("boom")


@tenant_exempt_route
async def _admin_endpoint(request):  # type: ignore[no-untyped-def]
    return JSONResponse({"tenant": str(current_tenant_id.get())})


def _build_app(resolver) -> Starlette:
    app = Starlette(
        routes=[
            Route("/who", _who_am_i),
            Route("/crash", _crash),
            Route("/admin", _admin_endpoint),
        ]
    )
    app.add_middleware(TenantIsolationMiddleware, resolver=resolver)
    return app


def _resolver_for(ctx: AuthContext | None):
    def _resolve(request):  # noqa: ARG001
        return ctx

    return _resolve


def test_tenant_context_set_during_request() -> None:
    ctx = AuthContext(user_id=USER_A, tenant_id=TENANT_A, roles=frozenset())
    client = TestClient(_build_app(_resolver_for(ctx)))
    resp = client.get("/who")
    assert resp.status_code == 200
    assert resp.json()["tenant"] == str(TENANT_A)


def test_tenant_context_cleared_after_request() -> None:
    ctx = AuthContext(user_id=USER_A, tenant_id=TENANT_A, roles=frozenset())
    client = TestClient(_build_app(_resolver_for(ctx)))
    client.get("/who")
    assert current_tenant_id.get() is None


def test_tenant_context_cleared_on_exception() -> None:
    ctx = AuthContext(user_id=USER_A, tenant_id=TENANT_A, roles=frozenset())
    client = TestClient(_build_app(_resolver_for(ctx)))
    with pytest.raises(RuntimeError, match="boom"):
        client.get("/crash")
    assert current_tenant_id.get() is None


def test_unauthenticated_returns_401() -> None:
    client = TestClient(_build_app(_resolver_for(None)))
    resp = client.get("/who")
    assert resp.status_code == 401
    assert resp.json()["error"] == "unauthenticated"


def test_missing_tenant_id_without_exempt_returns_403() -> None:
    ctx = AuthContext(user_id=USER_A, tenant_id=None, roles=frozenset())
    client = TestClient(_build_app(_resolver_for(ctx)))
    resp = client.get("/who")
    assert resp.status_code == 403


def test_exempt_route_requires_platform_admin() -> None:
    ctx = AuthContext(user_id=USER_A, tenant_id=TENANT_A, roles=frozenset({"tenant_admin"}))
    client = TestClient(_build_app(_resolver_for(ctx)))
    resp = client.get("/admin")
    assert resp.status_code == 403
    assert "platform_admin" in resp.json()["detail"]


def test_exempt_route_allows_platform_admin_without_tenant() -> None:
    ctx = AuthContext(user_id=USER_A, tenant_id=None, roles=frozenset({"platform_admin"}))
    client = TestClient(_build_app(_resolver_for(ctx)))
    resp = client.get("/admin")
    assert resp.status_code == 200
    assert resp.json()["tenant"] == "None"


def test_exempt_route_with_platform_admin_and_tenant() -> None:
    ctx = AuthContext(
        user_id=USER_A, tenant_id=TENANT_A, roles=frozenset({"platform_admin"})
    )
    client = TestClient(_build_app(_resolver_for(ctx)))
    resp = client.get("/admin")
    assert resp.status_code == 200


def test_auth_context_is_platform_admin_flag() -> None:
    ctx = AuthContext(user_id=USER_A, tenant_id=TENANT_A, roles=frozenset({"platform_admin"}))
    assert ctx.is_platform_admin is True
    ctx2 = replace(ctx, roles=frozenset())
    assert ctx2.is_platform_admin is False


def test_route_is_exempt_handles_missing_app() -> None:
    from infrastructure.tenant_middleware import _route_is_exempt

    assert _route_is_exempt({}) is False


def test_route_is_exempt_handles_app_without_routes() -> None:
    from infrastructure.tenant_middleware import _route_is_exempt

    class FakeApp:
        router = None  # falsy; the function falls back to app itself

    class FakeScope(dict):
        pass

    scope = FakeScope(app=FakeApp())
    assert _route_is_exempt(scope) is False


def test_route_is_exempt_skips_routes_that_raise() -> None:
    from infrastructure.tenant_middleware import _route_is_exempt

    class Boom:
        def matches(self, scope):
            raise RuntimeError("nope")

    class Router:
        routes = [Boom()]

    class App:
        router = Router()

    assert _route_is_exempt({"app": App(), "type": "http", "path": "/x", "method": "GET"}) is False


def test_route_is_exempt_returns_false_when_no_route_matches() -> None:
    from starlette.routing import Match

    from infrastructure.tenant_middleware import _route_is_exempt

    class NoMatchRoute:
        def matches(self, scope):
            return (Match.NONE, {})

    class App:
        class router:
            routes = [NoMatchRoute()]

    assert _route_is_exempt({"app": App()}) is False


async def test_non_http_scope_passes_through() -> None:
    """Lifespan scope must pass through untouched."""
    called: list[str] = []

    async def inner(scope, receive, send):  # type: ignore[no-untyped-def]
        called.append(scope["type"])

    mw = TenantIsolationMiddleware(inner, lambda r: None)  # noqa: ARG005
    await mw({"type": "lifespan"}, None, None)  # type: ignore[arg-type]
    assert called == ["lifespan"]


def test_non_http_via_testclient() -> None:
    """Lifespan events (scope['type']='lifespan') must not trip the middleware."""
    # Starlette's TestClient startup/shutdown exercises lifespan; a successful
    # request on a TestClient proves lifespan passed through untouched.
    ctx = AuthContext(user_id=USER_A, tenant_id=TENANT_A, roles=frozenset())
    with TestClient(_build_app(_resolver_for(ctx))) as client:
        assert client.get("/who").status_code == 200
