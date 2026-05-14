"""Core Platform infrastructure glue (DB init hooks, middleware wiring)."""

# B11 w1: was `from infrastructure.tenant_middleware import ...` (absolute).
# Uvicorn launches with `--app-dir modules/core-platform`, so the package
# root is `src.*` and the absolute path resolves to nothing. Relative
# import works both under uvicorn AND under pytest with the existing
# conftest configuration.
from .tenant_middleware import (
    AuthContext,
    AuthResolver,
    TenantIsolationMiddleware,
    tenant_exempt_route,
)

__all__ = [
    "AuthContext",
    "AuthResolver",
    "TenantIsolationMiddleware",
    "tenant_exempt_route",
]
