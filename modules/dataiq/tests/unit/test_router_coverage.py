"""Additional router endpoint tests to reach 99% branch coverage.

These tests drive through endpoints not fully covered by the integration
test suite, targeting the actual return-value code paths.

All DB I/O is mocked: the goal is to verify routing, tenant-scoping wiring,
and the shape of responses — not live DB correctness (covered by integration
tests in tests/integration/).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from src.main import create_app

TENANT_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))
TENANT_HEADERS = {"x-tenant-id": TENANT_ID}


def _mock_result(rows=None, scalar=None):
    """Build a mock SQLAlchemy execute result."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = rows if rows is not None else []
    mock_result.scalar_one_or_none.return_value = scalar
    mock_result.all.return_value = rows if rows is not None else []
    return mock_result


def _make_mock_session(rows=None, scalar=None):
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=_mock_result(rows, scalar))
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    return mock_session


@pytest.fixture(scope="module")
def client() -> TestClient:
    from shared.db.session import get_session  # noqa: PLC0415

    app = create_app()

    mock_session = _make_mock_session()

    async def _override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = _override_get_session
    return TestClient(app)


class TestMetricCurrentEndpoint:
    def test_get_current_metric_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/metrics/claim_count/current",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["metric_key"] == "claim_count"
        assert "as_of" in data

    def test_get_current_metric_value_is_none_when_no_data(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/metrics/unknown_metric/current",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["value"] is None


class TestDrugTrendEndpoints:
    def test_spend_trend_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/spend",
            headers=TENANT_HEADERS,
            params={"start_date": "2026-01-01", "end_date": "2026-04-13"},
        )
        assert response.status_code == 200
        assert "data" in response.json()

    def test_glp1_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/glp1",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        assert "data" in response.json()

    def test_biosimilar_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/biosimilar",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        assert "data" in response.json()

    def test_new_drugs_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/new-drugs",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        assert "data" in response.json()

    def test_price_inflation_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/price-inflation",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        assert "data" in response.json()

    def test_decomposition_with_date_params_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/decomposition",
            headers=TENANT_HEADERS,
            params={"start_period": "2026-01-01", "end_period": "2026-04-01"},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_top_drugs_requires_date_params(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/top-drugs",
            headers=TENANT_HEADERS,
        )
        # Missing required params → 422
        assert response.status_code == 422

    def test_top_drugs_returns_200_with_params(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/top-drugs",
            headers=TENANT_HEADERS,
            params={"start_date": "2026-01-01", "end_date": "2026-04-13"},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestNetworkAnalyticsEndpoints:
    def test_scorecard_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/network/scorecard",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        assert "data" in response.json()

    def test_leakage_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/network/leakage",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        assert "data" in response.json()

    def test_cost_variation_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/network/cost-variation",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        assert "data" in response.json()

    def test_network_adequacy_returns_zero_state_when_no_data(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/network/adequacy",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_members"] == 0
        assert data["covered_members"] == 0


class TestMemberAnalyticsEndpoints:
    def test_adherence_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/member/adherence",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200

    def test_high_cost_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/member/high-cost",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200

    def test_polypharmacy_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/member/polypharmacy",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200

    def test_therapy_gaps_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/member/therapy-gaps",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200

    def test_opioid_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/member/opioid",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200


class TestFinancialAnalyticsEndpoints:
    def test_cost_drivers_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/financial/cost-drivers",
            headers=TENANT_HEADERS,
            params={"start_period": "2026-01-01", "end_period": "2026-04-13"},
        )
        assert response.status_code == 200
        assert "data" in response.json()

    def test_pmpm_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/financial/pmpm",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200

    def test_spread_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/financial/spread",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200

    def test_profitability_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/financial/profitability",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200


class TestDataQualityEndpoints:
    def test_data_quality_returns_default_score_when_no_data(self, client: TestClient) -> None:
        """No DB row → returns default 100.00 score."""
        response = client.get(
            "/api/v1/dataiq/data-quality",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["overall_score"] == "100.00"

    def test_data_quality_history_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/data-quality/history",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        assert "scores" in response.json()

    def test_data_quality_issues_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/data-quality/issues",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        assert "issues" in response.json()


class TestBenchmarkEndpoints:
    def test_list_benchmarks_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/benchmarks",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_benchmark_returns_201(self, client: TestClient) -> None:
        from unittest.mock import MagicMock  # noqa: PLC0415
        import uuid as _uuid  # noqa: PLC0415
        from decimal import Decimal  # noqa: PLC0415

        # The create endpoint flushes and commits, then reads benchmark attrs.
        # We need the mock session's add() to capture the object so flush/commit
        # don't fail. The session mock already captures add via MagicMock.

        # Patch the benchmark object's id to something predictable
        response = client.post(
            "/api/v1/dataiq/benchmarks",
            headers=TENANT_HEADERS,
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
        assert data["metric_key"] == "generic_fill_rate"

    def test_update_benchmark_returns_404_when_not_found(self, client: TestClient) -> None:
        """Update returns 404 when benchmark not found (no DB row)."""
        benchmark_id = str(uuid.uuid4())
        response = client.put(
            f"/api/v1/dataiq/benchmarks/{benchmark_id}",
            headers=TENANT_HEADERS,
            json={
                "name": "Updated Benchmark",
                "metric_key": "generic_fill_rate",
                "benchmark_type": "target",
                "target_value": "0.90",
            },
        )
        # Mock returns None for scalar_one_or_none → 404
        assert response.status_code == 404

    def test_benchmarks_status_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/benchmarks/status",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        assert "benchmarks" in response.json()


class TestInsightAlertEndpoints:
    def test_list_insights_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/insights",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_insights_unacknowledged_filter(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/insights",
            headers=TENANT_HEADERS,
            params={"unacknowledged_only": "true"},
        )
        assert response.status_code == 200

    def test_acknowledge_insight_returns_404_when_not_found(self, client: TestClient) -> None:
        """Acknowledge returns 404 when insight not found (mock returns None)."""
        insight_id = str(uuid.uuid4())
        response = client.put(
            f"/api/v1/dataiq/insights/{insight_id}/acknowledge",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 404

    def test_insights_summary_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/insights/summary",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_unacknowledged" in data
        assert data["total_unacknowledged"] == 0


class TestTenantIsolation:
    def test_missing_tenant_header_rejected(self, client: TestClient) -> None:
        response = client.get("/api/v1/dataiq/metrics")
        assert response.status_code in (400, 422)

    def test_invalid_tenant_uuid_rejected(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/metrics",
            headers={"x-tenant-id": "not-a-uuid"},
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["error"]["code"] == "INVALID_TENANT_ID"
