"""Integration test: SecurityHeadersMiddleware is mounted in edi-compliance create_app().

CR-08 / LESSON-006 enforcement: the previous code imported middleware from
modules.core_platform.src.infrastructure wrapped in try/except: pass, making
it a silent no-op. This test only passes if SecurityHeadersMiddleware is
actually mounted on the production app via create_app().
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parents[2]
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

from fastapi.testclient import TestClient

from src.main import create_app
from shared.middleware.security_headers import SecurityHeadersMiddleware
from shared.middleware.rate_limiter import RateLimitMiddleware


def _middleware_classes(app) -> set[type]:
    return {m.cls for m in app.user_middleware}


def test_security_headers_middleware_is_mounted() -> None:
    """SecurityHeadersMiddleware must be in the production app's middleware stack."""
    app = create_app()
    assert SecurityHeadersMiddleware in _middleware_classes(app), (
        "SecurityHeadersMiddleware not mounted in edi-compliance create_app() — CR-08/LESSON-006. "
        "Check that the import is NOT wrapped in try/except and uses shared.middleware."
    )


def test_rate_limit_middleware_is_mounted() -> None:
    """RateLimitMiddleware must be in the production app's middleware stack."""
    app = create_app()
    assert RateLimitMiddleware in _middleware_classes(app), (
        "RateLimitMiddleware not mounted in edi-compliance create_app() — CR-08/LESSON-006."
    )


def test_hsts_header_present_on_health_response() -> None:
    """HSTS must appear on /health — proves SecurityHeadersMiddleware is actually running."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.headers.get("Strict-Transport-Security") is not None, (
        "HSTS header missing — SecurityHeadersMiddleware is not on the live request path."
    )
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Cache-Control") == "no-store"
