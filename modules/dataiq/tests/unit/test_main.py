"""Unit tests for DataIQ application factory.

LESSON-006: integration tests through create_app() to verify middleware
and routers are mounted.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from src.main import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


TENANT_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))


class TestCreateApp:
    def test_creates_fastapi_app(self) -> None:
        from fastapi import FastAPI

        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_has_dataiq_title(self) -> None:
        app = create_app()
        assert "DataIQ" in app.title

    def test_health_endpoint_mounted(self, client: TestClient) -> None:
        """Health endpoint must be mounted and return the contract schema."""
        response = client.get("/health")
        # 200 = healthy/degraded, 503 = unhealthy (DB/Redis down in test env).
        assert response.status_code in (200, 503)
        assert response.json()["module"] == "dataiq"

    def test_router_mounted_at_api_v1_dataiq(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/metrics",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200

    def test_generic_exception_handler_returns_500(self, client: TestClient) -> None:

        app = create_app()

        @app.get("/test-error")
        async def raise_error() -> None:
            raise RuntimeError("deliberate test error")

        test_client = TestClient(app, raise_server_exceptions=False)
        response = test_client.get("/test-error")
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert "correlation_id" in data["error"]
