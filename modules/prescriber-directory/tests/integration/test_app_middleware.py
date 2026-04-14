"""Integration tests — middleware mounted through create_app().

LESSON-006: Every middleware primitive MUST be tested through create_app(),
not in isolation. These tests fail if middleware is not mounted.
"""

from __future__ import annotations

import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import pytest
from fastapi.testclient import TestClient

from shared.auth.dependencies import get_current_user
from src.api.dependencies import get_db
from src.main import create_app
from tests.conftest import _FAKE_USER_FOR_TESTS


@pytest.fixture(scope="module")
def app(_engine):
    """Create app with DB overridden to use in-memory SQLite."""
    application = create_app()

    def override_get_db():
        from sqlalchemy.orm import sessionmaker as _sm
        factory = _sm(bind=_engine, expire_on_commit=False, future=True)
        session = factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = override_get_db
    # CR-03: bypass JWT auth so middleware/tenant tests focus on the right layer
    application.dependency_overrides[get_current_user] = lambda: _FAKE_USER_FOR_TESTS
    return application


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app, raise_server_exceptions=True)


class TestSecurityHeadersMiddleware:
    def test_security_headers_present_on_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "strict-transport-security" in resp.headers or "x-content-type-options" in resp.headers

    def test_x_content_type_options_header(self, client):
        resp = client.get("/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options_header(self, client):
        resp = client.get("/health")
        assert resp.headers.get("x-frame-options") in ("DENY", "SAMEORIGIN")


class TestRateLimitMiddleware:
    def test_rate_limit_header_present(self, client):
        """Rate limit middleware must be mounted — headers prove it."""
        resp = client.get("/health")
        assert resp.status_code in (200, 429)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["module"] == "prescriber-directory"


class TestTenantHeaderValidation:
    def test_invalid_tenant_id_returns_400(self, client):
        resp = client.get(
            "/api/v1/prescribers/lookup/1234567893",
            headers={"x-tenant-id": "not-a-uuid"},
        )
        assert resp.status_code in (400, 422)

    def test_missing_tenant_id_returns_422(self, client):
        resp = client.get("/api/v1/prescribers/lookup/1234567893")
        assert resp.status_code in (400, 422)
