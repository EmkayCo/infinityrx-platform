"""Integration test: AuditMiddleware and TenantIsolationMiddleware are mounted
in create_app() and are reachable through real HTTP requests.

LESSON-006 enforcement: this test ONLY passes if the middleware is actually
mounted on the app from create_app(). Unit tests on AuditMiddleware in
isolation are insufficient — they cannot prove the middleware is on the live
request path. Removing either middleware from create_app() causes this file
to fail.
"""

from __future__ import annotations

from src import main as main_module
from src.audit.middleware import AuditMiddleware
from src.infrastructure.tenant_middleware import TenantIsolationMiddleware


def _middleware_classes(app) -> set[type]:
    return {m.cls for m in app.user_middleware}


def test_audit_middleware_is_mounted() -> None:
    """AuditMiddleware must be in the production app's middleware stack."""
    app = main_module.create_app()
    assert AuditMiddleware in _middleware_classes(app), (
        "AuditMiddleware must be added to create_app() — LESSON-006: "
        "primitives must be mounted, not just unit-tested."
    )


def test_tenant_isolation_middleware_is_mounted() -> None:
    """TenantIsolationMiddleware must be in the production app's middleware stack."""
    app = main_module.create_app()
    # TenantIsolationMiddleware is pure ASGI — it appears in user_middleware
    assert TenantIsolationMiddleware in _middleware_classes(app), (
        "TenantIsolationMiddleware must be added to create_app() — LESSON-006."
    )
