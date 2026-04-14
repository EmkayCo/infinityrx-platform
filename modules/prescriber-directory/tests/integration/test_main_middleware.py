"""Integration test: full middleware stack is mounted in prescriber-directory create_app().

LESSON-006 enforcement: test only passes if SecurityHeadersMiddleware is mounted
via create_app(). Removing it from create_app() causes this test to fail.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[4]
for _p in (_MODULE_ROOT, _REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

from fastapi.testclient import TestClient

from src.main import create_app


def test_hsts_header_present_on_health_response() -> None:
    """HSTS must appear on /health — proves SecurityHeadersMiddleware is mounted."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.headers.get("Strict-Transport-Security") is not None, (
        "SecurityHeadersMiddleware not mounted in prescriber-directory create_app() — LESSON-006"
    )
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Cache-Control") == "no-store"
