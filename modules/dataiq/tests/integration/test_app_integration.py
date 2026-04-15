"""Integration tests for DataIQ module through create_app().

LESSON-006: every middleware/router primitive must be exercised through
the top-level app factory, not just tested in isolation.

DB sessions are mocked so tests run without a live database. This verifies
routing, auth/tenant enforcement, and middleware wiring — not DB query
correctness (that is tested by unit tests with real mock sessions).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from src.main import create_app


def _mock_result(rows=None, scalar=None):
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = rows if rows is not None else []
    mock_result.scalar_one_or_none.return_value = scalar
    mock_result.all.return_value = rows if rows is not None else []
    return mock_result


@pytest.fixture()
def client() -> TestClient:
    from shared.db.session import get_session  # noqa: PLC0415

    app = create_app()

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=_mock_result())
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    async def _override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = _override_get_session
    return TestClient(app, raise_server_exceptions=True)


TENANT_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))


class TestHealthEndpoint:
    def test_health_check_is_reachable(self, client: TestClient) -> None:
        """Health endpoint must be mounted and return the contract schema."""
        response = client.get("/health")
        # 200 = healthy/degraded, 503 = unhealthy (DB/Redis down in test env).
        assert response.status_code in (200, 503)
        data = response.json()
        assert data["module"] == "dataiq"
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert "dependencies" in data

    def test_health_has_no_auth_requirement(self, client: TestClient) -> None:
        """Health must be reachable without an auth token."""
        response = client.get("/health")
        assert response.status_code in (200, 503)


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
        # 200 confirms the route is mounted and wired
        assert response.status_code == 200
        data = response.json()
        assert data["metric_key"] == "claim_count"
        assert data["snapshots"] == []
        assert data["mean"] is None

    def test_spc_anomalies_endpoint_exists(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/metrics/claim_count/anomalies",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestDrugTrendEndpoints:
    def test_decomposition_endpoint_mounted(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/decomposition",
            headers={"x-tenant-id": TENANT_ID},
            params={"start_period": "2026-01-01", "end_period": "2026-04-01"},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_top_drugs_endpoint_mounted(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/top-drugs",
            headers={"x-tenant-id": TENANT_ID},
            params={"start_date": "2026-01-01", "end_date": "2026-04-01"},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestDataQualityEndpoints:
    def test_data_quality_endpoint_mounted(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/data-quality",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        # No DB data → default 100.00
        assert data["overall_score"] == "100.00"

    def test_data_quality_history_endpoint_mounted(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/data-quality/history",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200
        assert "scores" in response.json()


class TestInsightAlertEndpoints:
    def test_insights_list_endpoint_mounted(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/insights",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_insights_summary_endpoint_mounted(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/insights/summary",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_unacknowledged" in data


class TestNetworkEndpoints:
    def test_network_adequacy_endpoint_mounted(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/network/adequacy",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_members" in data
        assert "pct_members_covered" in data

    def test_network_adequacy_uses_geo_analytics_for_zero_state(self, client: TestClient) -> None:
        """When no rollup data, geo_analytics.calculate_network_adequacy is used."""
        response = client.get(
            "/api/v1/dataiq/network/adequacy",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_members"] == 0
        assert data["covered_members"] == 0
        assert data["pct_members_covered"] == "0.00"


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

    def test_each_endpoint_requires_tenant_header(self, client: TestClient) -> None:
        """Spot-check several endpoints to confirm tenant header enforcement."""
        endpoints = [
            "/api/v1/dataiq/drug-trend/glp1",
            "/api/v1/dataiq/network/scorecard",
            "/api/v1/dataiq/member/adherence",
            "/api/v1/dataiq/financial/pmpm",
            "/api/v1/dataiq/benchmarks",
            "/api/v1/dataiq/insights",
        ]
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code in (400, 422), f"{ep} did not reject missing tenant header"


class TestFinancialEndpointsWired:
    def test_cost_drivers_returns_period_pair(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/financial/cost-drivers",
            headers={"x-tenant-id": TENANT_ID},
            params={"start_period": "2026-01-01", "end_period": "2026-04-01"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["period_pair"] == "2026-01-01/2026-04-01"
        assert "data" in data

    def test_pmpm_returns_data_key(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/financial/pmpm",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200
        assert "data" in response.json()

    def test_spread_returns_data_key(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/financial/spread",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200
        assert "data" in response.json()

    def test_profitability_returns_data_key(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/financial/profitability",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200
        assert "data" in response.json()


class TestBenchmarkEndpointsWired:
    def test_list_benchmarks_returns_list(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/benchmarks",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_benchmarks_status_returns_benchmarks_key(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/benchmarks/status",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200
        assert "benchmarks" in response.json()

    def test_create_benchmark_returns_201(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/dataiq/benchmarks",
            headers={"x-tenant-id": TENANT_ID},
            json={
                "name": "Generic Fill Rate Target",
                "metric_key": "generic_fill_rate",
                "benchmark_type": "target",
                "target_value": "0.85",
                "warning_threshold": "0.80",
                "critical_threshold": "0.75",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Generic Fill Rate Target"

    def test_update_benchmark_returns_404_when_not_found(self, client: TestClient) -> None:
        benchmark_id = str(uuid.uuid4())
        response = client.put(
            f"/api/v1/dataiq/benchmarks/{benchmark_id}",
            headers={"x-tenant-id": TENANT_ID},
            json={
                "name": "Updated",
                "metric_key": "generic_fill_rate",
                "benchmark_type": "target",
            },
        )
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["error"]["code"] == "BENCHMARK_NOT_FOUND"


class TestInsightAlertsWired:
    def test_insights_list_supports_unacknowledged_filter(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/insights",
            headers={"x-tenant-id": TENANT_ID},
            params={"unacknowledged_only": "true"},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_acknowledge_insight_returns_404_when_not_found(self, client: TestClient) -> None:
        insight_id = str(uuid.uuid4())
        response = client.put(
            f"/api/v1/dataiq/insights/{insight_id}/acknowledge",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["error"]["code"] == "INSIGHT_NOT_FOUND"

    def test_insights_summary_has_severity_counts(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/insights/summary",
            headers={"x-tenant-id": TENANT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert "critical_count" in data
        assert "warning_count" in data
        assert "info_count" in data
