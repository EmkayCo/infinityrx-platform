"""Extended API integration tests — DEA lookup, batch, alerts, monitoring."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_db
from src.main import create_app
from src.models.tables import CredentialAlert, Prescriber
from tests.conftest import make_prescriber, now_utc, TENANT_A


@pytest.fixture(scope="module")
def app(_engine):
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
    return application


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def extended_seed(_engine):
    from sqlalchemy.orm import sessionmaker as _sm
    factory = _sm(bind=_engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        # Prescriber with DEA for DEA lookup test
        p1 = Prescriber(**make_prescriber(
            npi="1000000038",
            last_name="WILLIAMS",
            first_name="CARL",
            display_name="DR. CARL WILLIAMS MD",
            dea_number="AW1234563",
            dea_status="active",
            dea_schedules=["2", "3", "4", "5"],
            practice_state="TX",
        ))
        # Organization for org search test
        p2 = Prescriber(**make_prescriber(
            npi="1000000046",
            entity_type="2",
            last_name="",
            first_name="",
            display_name="CHICAGO HEALTH NETWORK LLC",
            status="active",
            primary_specialty="group practice",
            practice_state="IL",
        ))
        p2.organization_name = "CHICAGO HEALTH NETWORK LLC"
        session.add_all([p1, p2])
        session.flush()

        # Credential alert
        alert = CredentialAlert(
            id=uuid.uuid4(),
            prescriber_id=p1.id,
            alert_type="dea_expiring",
            severity="warning",
            message="DEA expires in 30 days",
            created_at=now_utc(),
        )
        session.add(alert)
        session.commit()
    finally:
        session.close()


class TestDeaLookup:
    def test_lookup_by_valid_dea(self, client, extended_seed):
        resp = client.get(
            "/api/v1/prescribers/lookup/dea/AW1234563",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["npi"] == "1000000038"

    def test_lookup_by_nonexistent_dea_returns_404(self, client, extended_seed):
        resp = client.get(
            "/api/v1/prescribers/lookup/dea/ZZ9999999",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 404


class TestBatchLookup:
    def test_batch_lookup_found_and_not_found(self, client, extended_seed):
        # 1000000038 is seeded by extended_seed; 1000000004 is a valid NPI not seeded
        resp = client.get(
            "/api/v1/prescribers/batch",
            params={"npis": ["1000000038", "1000000004"]},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "1000000038" in data["results"]
        assert "1000000004" in data["not_found"]

    def test_batch_lookup_requires_tenant(self, client):
        resp = client.get(
            "/api/v1/prescribers/batch",
            params={"npis": ["1234567893"]},
        )
        assert resp.status_code in (400, 422)


class TestCredentialAlerts:
    def test_list_unacknowledged_alerts(self, client, extended_seed):
        resp = client.get(
            "/api/v1/prescribers/monitoring/alerts?acknowledged=false",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        alerts = resp.json()
        assert isinstance(alerts, list)
        assert len(alerts) >= 1

    def test_list_all_alerts(self, client, extended_seed):
        resp = client.get(
            "/api/v1/prescribers/monitoring/alerts",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200

    def test_acknowledge_nonexistent_alert_returns_404(self, client, extended_seed):
        fake_id = uuid.uuid4()
        resp = client.put(
            f"/api/v1/prescribers/monitoring/alerts/{fake_id}/acknowledge",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 404

    def test_acknowledge_existing_alert(self, client, extended_seed):
        # Get an alert first
        resp = client.get(
            "/api/v1/prescribers/monitoring/alerts?acknowledged=false",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        alerts = resp.json()
        if not alerts:
            pytest.skip("No unacknowledged alerts in DB")
        alert_id = alerts[0]["id"]
        ack_resp = client.put(
            f"/api/v1/prescribers/monitoring/alerts/{alert_id}/acknowledge",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert ack_resp.status_code == 200
        data = ack_resp.json()
        assert data["acknowledged"] is True


class TestSearchFilters:
    def test_search_by_entity_type(self, client, extended_seed):
        resp = client.get(
            "/api/v1/prescribers/search?entity_type=1",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        for r in data["results"]:
            assert r["entity_type"] == "1"

    def test_search_by_status(self, client, extended_seed):
        resp = client.get(
            "/api/v1/prescribers/search?status=active",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        for r in data["results"]:
            assert r["status"] == "active"

    def test_search_no_filters_returns_results(self, client, extended_seed):
        resp = client.get(
            "/api/v1/prescribers/search",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1


class TestOrganizationSearch:
    def test_list_organizations_with_name_filter(self, client, extended_seed):
        resp = client.get(
            "/api/v1/prescribers/organizations?name=CHICAGO+HEALTH",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_list_organizations_with_state_filter(self, client, extended_seed):
        resp = client.get(
            "/api/v1/prescribers/organizations?state=IL",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200

    def test_invalid_org_npi_returns_400(self, client):
        resp = client.get(
            "/api/v1/prescribers/organizations/BADNPI",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 400


class TestRelationshipEndpoints:
    def test_list_pharmacies_for_prescriber_empty(self, client, extended_seed):
        resp = client.get(
            "/api/v1/prescribers/relationships/1000000038/pharmacies",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_pharmacies_with_period_filter(self, client, extended_seed, _engine):
        from sqlalchemy.orm import sessionmaker as _sm
        from src.models.tables import PrescriberPharmacyRelationship
        factory = _sm(bind=_engine, expire_on_commit=False, future=True)
        session = factory()
        rel = PrescriberPharmacyRelationship(
            prescriber_npi="1000000038",
            pharmacy_npi="2000000010",
            period_month="2026-01",
            claim_count=10,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        session.add(rel)
        session.commit()
        session.close()

        resp = client.get(
            "/api/v1/prescribers/relationships/1000000038/pharmacies?period_month=2026-01",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["pharmacy_npi"] == "2000000010"

    def test_list_pharmacies_invalid_npi_returns_422(self, client):
        resp = client.get(
            "/api/v1/prescribers/relationships/BADNPI/pharmacies",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 422

    def test_relationship_stats_no_data(self, client, extended_seed):
        resp = client.get(
            "/api/v1/prescribers/relationships/1000000046/stats",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["prescriber_npi"] == "1000000046"
        assert data["unique_pharmacies"] == 0

    def test_relationship_stats_with_data(self, client, extended_seed):
        resp = client.get(
            "/api/v1/prescribers/relationships/1000000038/stats",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["prescriber_npi"] == "1000000038"

    def test_relationship_stats_invalid_npi(self, client):
        resp = client.get(
            "/api/v1/prescribers/relationships/BADNPI/stats",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 422


class TestNppesRefreshEndpoint:
    def test_refresh_queued_with_no_prior_log(self, client, extended_seed):
        resp = client.post(
            "/api/v1/prescribers/refresh?data_source=test-source&refresh_type=full",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] in ("queued", "completed")
        assert data["data_source"] == "test-source"

    def test_refresh_returns_last_completed_log(self, client, extended_seed, _engine):
        from sqlalchemy.orm import sessionmaker as _sm
        from datetime import datetime, timezone
        from src.models.tables import DataRefreshLog
        factory = _sm(bind=_engine, expire_on_commit=False, future=True)
        session = factory()
        log = DataRefreshLog(
            data_source="nppes-test",
            refresh_type="full",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            status="completed",
            records_processed=100,
            records_added=80,
            records_updated=20,
            created_at=datetime.now(timezone.utc),
        )
        session.add(log)
        session.commit()
        session.close()

        resp = client.post(
            "/api/v1/prescribers/refresh?data_source=nppes-test&refresh_type=full",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "completed"
        assert data["records_processed"] == 100
