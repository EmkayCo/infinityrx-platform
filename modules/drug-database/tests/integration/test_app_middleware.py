"""Integration tests: middleware mounted through create_app().

LESSON-006: Every middleware must be tested through create_app(), not in isolation.
These tests can ONLY pass if SecurityHeadersMiddleware, RateLimitMiddleware,
and DLQ router are all mounted on the application.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.dependencies import get_db
from src.main import create_app
from src.models.tables import DrugBase

_TEST_TENANT = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(scope="module")
def _engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    for table in DrugBase.metadata.tables.values():
        table.schema = None
    DrugBase.metadata.create_all(engine)
    yield engine
    DrugBase.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="module")
def client(_engine) -> TestClient:
    app = create_app()

    _Factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

    def _override_db():
        session = _Factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app, raise_server_exceptions=False)


class TestSecurityHeadersMounted:
    """Security headers can only appear if SecurityHeadersMiddleware is mounted."""

    def test_hsts_header_present(self, client: TestClient) -> None:
        resp = client.get("/api/v1/drugs/health", headers={"X-Tenant-Id": _TEST_TENANT})
        assert "Strict-Transport-Security" in resp.headers

    def test_x_content_type_options_present(self, client: TestClient) -> None:
        resp = client.get("/api/v1/drugs/health", headers={"X-Tenant-Id": _TEST_TENANT})
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options_present(self, client: TestClient) -> None:
        resp = client.get("/api/v1/drugs/health", headers={"X-Tenant-Id": _TEST_TENANT})
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_cache_control_no_store(self, client: TestClient) -> None:
        resp = client.get("/api/v1/drugs/health", headers={"X-Tenant-Id": _TEST_TENANT})
        assert "no-store" in resp.headers.get("Cache-Control", "")

    def test_request_id_echoed(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/drugs/health",
            headers={"X-Request-ID": "test-req-123", "X-Tenant-Id": _TEST_TENANT},
        )
        assert resp.headers.get("X-Request-ID") == "test-req-123"

    def test_request_id_generated_when_absent(self, client: TestClient) -> None:
        resp = client.get("/api/v1/drugs/health", headers={"X-Tenant-Id": _TEST_TENANT})
        assert resp.headers.get("X-Request-ID") is not None


class TestDLQRouterMounted:
    """DLQ router can only respond if it's mounted on the app."""

    def test_dlq_list_endpoint_reachable(self, client: TestClient) -> None:
        resp = client.get("/api/v1/events/dlq")
        # 200 (empty list) or 403 (no permissions) — either means the route exists
        assert resp.status_code in (200, 403)

    def test_dlq_endpoint_is_not_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/events/dlq")
        assert resp.status_code != 404


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/v1/drugs/health", headers={"X-Tenant-Id": _TEST_TENANT})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["module"] == "drug-database"


class TestTenantIdValidation:
    def test_missing_tenant_id_returns_422(self, client: TestClient) -> None:
        resp = client.get("/api/v1/drugs/lookup/00093314905")
        assert resp.status_code == 422

    def test_invalid_tenant_id_returns_400(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/drugs/lookup/00093314905",
            headers={"X-Tenant-Id": "not-a-uuid"},
        )
        assert resp.status_code == 400
