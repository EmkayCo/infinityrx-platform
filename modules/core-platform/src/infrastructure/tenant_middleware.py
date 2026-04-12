"""Tenant isolation middleware for FastAPI/Starlette.

Responsibility
--------------
For each incoming request:

1. Invoke the injected :class:`AuthResolver` to extract
   ``(user_id, tenant_id, roles)`` from the request (typically JWT claims).
   The middleware deliberately does NOT implement JWT parsing itself —
   Teammate 2 will provide the real resolver that understands Azure AD B2C /
   local JWT. The middleware only depends on the :class:`AuthResolver`
   Protocol, so unit tests inject fakes trivially.

2. Validate the resulting :class:`AuthContext` against the route's
   ``tenant_exempt`` marker:

   * Route is tenant-scoped (default): a tenant id is required.
   * Route is ``tenant_exempt``: caller MUST hold the ``platform_admin``
     role, otherwise the middleware returns 403. Without this guard any
     route decorated ``tenant_exempt`` would be a cross-tenant data-leak.

3. Set the :data:`shared.db.tenant_context.current_tenant_id` contextvar
   for the duration of the request, then *always* clear it — including on
   exceptions — so that a later request on the same worker never inherits
   stale context.

Public API for other teammates
------------------------------
* :class:`AuthResolver` — protocol they must implement.
* :func:`tenant_exempt_route` — decorator marking a route as cross-tenant;
  the middleware will only permit it if the caller is ``platform_admin``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from shared.db.tenant_context import (
    clear_tenant_context,
    set_tenant_context,
)

#: Route attribute / ``scope['route']`` attribute name used to opt a route
#: out of tenant scoping. The decorator :func:`tenant_exempt_route` sets it.
TENANT_EXEMPT_ROUTE_ATTR = "__infinityrx_tenant_exempt__"

#: Role name that may traverse tenants.
PLATFORM_ADMIN_ROLE = "platform_admin"


@dataclass(frozen=True)
class AuthContext:
    """Resolved auth info for a single request."""

    user_id: UUID
    tenant_id: UUID | None
    roles: frozenset[str]

    @property
    def is_platform_admin(self) -> bool:
        return PLATFORM_ADMIN_ROLE in self.roles


@runtime_checkable
class AuthResolver(Protocol):
    """Callable that extracts :class:`AuthContext` from a request.

    Return ``None`` to signal the request is unauthenticated — the middleware
    will then decide whether that's allowed (it never is for tenant-scoped
    routes).
    """

    def __call__(self, request: Request) -> AuthContext | None: ...


def tenant_exempt_route(func):  # type: ignore[no-untyped-def]
    """Mark a FastAPI route handler as exempt from tenant scoping.

    The middleware will only allow the request to proceed if the resolved
    caller holds the ``platform_admin`` role.
    """
    setattr(func, TENANT_EXEMPT_ROUTE_ATTR, True)
    return func


def _route_is_exempt(scope: Scope) -> bool:
    """Resolve the matching route for *scope* and inspect its exempt flag.

    The middleware runs before Starlette's router populates
    ``scope['route']``, so we manually ask each registered route whether it
    would match this scope. This keeps the decorator ergonomics simple
    (a plain function attribute) without coupling the middleware to any
    particular framework beyond Starlette's own :class:`Route` matching
    protocol.
    """
    app = scope.get("app")
    if app is None:
        return False
    router = getattr(app, "router", None) or app
    routes = getattr(router, "routes", None)
    if not routes:
        return False
    for route in routes:
        try:
            match, _ = route.matches(scope)
        except Exception:  # noqa: BLE001
            continue
        # Match.FULL == 2 per starlette.routing.Match
        if getattr(match, "value", match) == 2:
            endpoint = getattr(route, "endpoint", None)
            if endpoint is not None and getattr(endpoint, TENANT_EXEMPT_ROUTE_ATTR, False):
                return True
            return bool(getattr(route, TENANT_EXEMPT_ROUTE_ATTR, False))
    return False


class TenantIsolationMiddleware:
    """Pure ASGI middleware — no framework coupling beyond Starlette types."""

    def __init__(self, app: ASGIApp, resolver: AuthResolver) -> None:
        self.app = app
        self.resolver = resolver

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        auth = self.resolver(request)
        exempt = _route_is_exempt(scope)

        if auth is None:
            response: Response = JSONResponse(
                {"error": "unauthenticated", "detail": "Missing or invalid credentials"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        if exempt:
            if not auth.is_platform_admin:
                response = JSONResponse(
                    {
                        "error": "forbidden",
                        "detail": "tenant_exempt routes require platform_admin",
                    },
                    status_code=403,
                )
                await response(scope, receive, send)
                return
            # Exempt + platform_admin: run with no tenant context.
            token = set_tenant_context(None)  # type: ignore[arg-type]
        else:
            if auth.tenant_id is None:
                response = JSONResponse(
                    {
                        "error": "forbidden",
                        "detail": "Request has no tenant context",
                    },
                    status_code=403,
                )
                await response(scope, receive, send)
                return
            token = set_tenant_context(auth.tenant_id)

        try:
            await self.app(scope, receive, send)
        finally:
            clear_tenant_context(token)
