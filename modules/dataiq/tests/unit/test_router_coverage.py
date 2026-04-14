"""Additional router endpoint tests to reach 99% branch coverage.

These tests drive through endpoints not fully covered by the integration
test suite, targeting the actual return-value code paths.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from src.main import create_app

TENANT_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))
TENANT_HEADERS = {"x-tenant-id": TENANT_ID}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


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


class TestDrugTrendEndpoints:
    def test_spend_trend_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/spend",
            headers=TENANT_HEADERS,
            params={"start_date": "2026-01-01", "end_date": "2026-04-13"},
        )
        assert response.status_code == 200

    def test_glp1_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/glp1",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200

    def test_biosimilar_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/biosimilar",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200

    def test_new_drugs_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/new-drugs",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200

    def test_price_inflation_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/drug-trend/price-inflation",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200


class TestNetworkAnalyticsEndpoints:
    def test_scorecard_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/network/scorecard",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200

    def test_leakage_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/network/leakage",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200

    def test_cost_variation_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/network/cost-variation",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200


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
    def test_data_quality_history_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/data-quality/history",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200

    def test_data_quality_issues_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/data-quality/issues",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200


class TestBenchmarkEndpoints:
    def test_list_benchmarks_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/benchmarks",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_benchmark_returns_201(self, client: TestClient) -> None:
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

    def test_update_benchmark_returns_200(self, client: TestClient) -> None:
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
        assert response.status_code == 200

    def test_benchmarks_status_returns_200(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/dataiq/benchmarks/status",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200


class TestInsightAlertEndpoints:
    def test_acknowledge_insight_returns_200(self, client: TestClient) -> None:
        insight_id = str(uuid.uuid4())
        response = client.put(
            f"/api/v1/dataiq/insights/{insight_id}/acknowledge",
            headers=TENANT_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["acknowledged"] is True
