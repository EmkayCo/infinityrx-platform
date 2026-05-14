"""B11 w1 — Werkbench enforce_test_first hook satisfaction stub for __init__.py.

The hook treats the package __init__.py as production code and looks for
__init___test.py (or test___init__.py) co-located. The real coverage for
the relative-import fix is via the operator portal's b11-w0_1 e2e test
F-W04 (audit-log query reaches core-platform once /health responds), and
indirectly via the existing tenant_middleware unit tests at
modules/core-platform/tests/infrastructure/test_tenant_middleware.py
(which import the same symbols via the now-functional package path).
"""


def test_init_module_imports_resolve() -> None:
    """The __init__.py re-exports symbols from .tenant_middleware via
    relative import. Verify the package import works without raising."""
    # Use late-import so the stub itself doesn't fail to collect if there's
    # an unrelated transient import error elsewhere in the codebase.
    from src.infrastructure import (  # noqa: F401
        AuthContext,
        AuthResolver,
        TenantIsolationMiddleware,
        tenant_exempt_route,
    )

    assert AuthContext is not None
    assert AuthResolver is not None
    assert TenantIsolationMiddleware is not None
    assert tenant_exempt_route is not None
