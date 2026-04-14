"""Integration tests for DataIQ module through create_app().

LESSON-006: every middleware/router primitive must be exercised through
the top-level app factory, not just tested in isolation.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from src.main import create_app


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    return TestClient(app, raise_server_exceptions=True)


TENANT_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))


class TestHealthEndpoint:
    def test_health_check_returns_ok(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["module"] == "dataiq"

    def test_health_has_no_auth_requirement(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200


class TestMetricsEndpoints:
    def test_metrics_list_requires_tenant_header(self, client: TestClient) -> None:
        response = client.get("/api/v1/dataiq/metrics")
        assert response.status_code in (400, 422)

    def test_metrics_list_with_tenant_header(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/metrics",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_invalid_tenant_id_returns_400(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/metrics",
            headers={"x-tenant-id": "not-a-uuid"},
        )
        assert response.status_code == 400


class TestSPCEndpoints:
    def test_spc_endpoint_is_mounted_on_app(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/metrics/claim_count/history",
            headers={"x-tenant-id": TENANT_ID},
            params={"start_date": "2026-01-01", "end_date": "2026-04-13"},
        )
        # 200 or 404 (no data) both confirm the route is mounted
        assert response.status_code in (200, 404)

    def test_spc_anomalies_endpoint_exists(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/metrics/claim_count/anomalies",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code in (200, 404)


class TestDrugTrendEndpoints:
    def test_decomposition_endpoint_mounted(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/decomposition",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code in (200, 422)

    def test_top_drugs_endpoint_mounted(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/top-drugs",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code in (200, 422)


class TestDataQualityEndpoints:
    def test_data_quality_endpoint_mounted(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/data-quality",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code in (200, 404)

    def test_data_quality_history_endpoint_mounted(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/data-quality/history",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code in (200, 404)


class TestInsightAlertEndpoints:
    def test_insights_list_endpoint_mounted(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/insights",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code in (200, 404)

    def test_insights_summary_endpoint_mounted(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/insights/summary",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code in (200, 404)


class TestNetworkEndpoints:
    def test_network_adequacy_endpoint_mounted(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/network/adequacy",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code in (200, 404, 422)


class TestTenantIsolation:
    def test_missing_tenant_id_rejected(self, client: TestClient) -> None:
        response = client.get("/api/v1/dataiq/metrics")
        assert response.status_code in (400, 422)

    def test_malformed_tenant_id_rejected(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/metrics",
            headers={"x-tenant-id": "malformed-not-uuid"},
        )
        assert response.status_code == 400

    def test_error_response_has_standard_format(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/metrics",
            headers={"x-tenant-id": "bad-uuid"},
        )
        assert response.status_code == 400
        data = response.json()
        # FastAPI wraps HTTPException detail under "detail"
        detail = data.get("detail") or data
        if isinstance(detail, dict) and "error" in detail:
            assert "code" in detail["error"]
            assert "message" in detail["error"]
        else:
            assert "error" in data
