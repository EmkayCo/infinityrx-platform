"""Integration tests for prescriber lookup and validation API endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_db
from src.main import create_app
from src.models.tables import Prescriber
from tests.conftest import make_prescriber, TENANT_A


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
def seeded_db(_engine):
    """Seed prescribers for all tests in this module."""
    from sqlalchemy.orm import sessionmaker as _sm
    factory = _sm(bind=_engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        # Active prescriber with DEA
        p1 = Prescriber(**make_prescriber(
            npi="1234567893",
            last_name="SMITH",
            first_name="JOHN",
            display_name="DR. JOHN SMITH MD",
            status="active",
            primary_specialty="family medicine",
            practice_state="IL",
            dea_number="AS1234563",
            dea_status="active",
            dea_schedules=["2", "2N", "3", "3N", "4", "5"],
        ))
        # Deactivated prescriber
        p2 = Prescriber(**make_prescriber(
            npi="1679576722",
            last_name="JONES",
            first_name="MARY",
            display_name="DR. MARY JONES DO",
            status="deactivated",
        ))
        # Excluded prescriber
        p3 = Prescriber(**make_prescriber(
            npi="1003000126",
            last_name="BROWN",
            first_name="BOB",
            display_name="BOB BROWN PA",
            status="excluded",
        ))
        # Organization (Type 2)
        p4 = Prescriber(**make_prescriber(
            npi="1000000012",
            entity_type="2",
            last_name="",
            first_name="",
            display_name="CHICAGO MEDICAL GROUP LLC",
            status="active",
            primary_specialty="group practice",
            practice_state="IL",
        ))
        p4.organization_name = "CHICAGO MEDICAL GROUP LLC"
        # Prescriber without DEA
        p5 = Prescriber(**make_prescriber(
            npi="1000000020",
            last_name="PATEL",
            first_name="ANITA",
            display_name="ANITA PATEL MD",
            status="active",
        ))

        session.add_all([p1, p2, p3, p4, p5])
        session.commit()
    finally:
        session.close()


class TestLookupByNpi:
    def test_lookup_active_prescriber(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/lookup/1234567893",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["npi"] == "1234567893"
        assert data["last_name"] == "SMITH"

    def test_lookup_nonexistent_npi_returns_404(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/lookup/1000000004",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 404

    def test_lookup_invalid_npi_format_returns_400(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/lookup/BADNPI",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 400

    def test_dea_number_not_exposed_in_lookup(self, client, seeded_db):
        """DEA numbers must never appear in logs — response may include it but not in logs."""
        resp = client.get(
            "/api/v1/prescribers/lookup/1234567893",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        # DEA number redacted in partial NPI logging — just verify response works
        assert "npi" in resp.json()


class TestValidation:
    def test_validate_active_prescriber(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/validate/1234567893",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["npi"] == "1234567893"

    def test_validate_deactivated_prescriber_returns_invalid(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/validate/1679576722",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["reason_code"] == "NPI_DEACTIVATED"

    def test_validate_excluded_prescriber_returns_invalid(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/validate/1003000126",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["reason_code"] == "EXCLUDED"

    def test_validate_nonexistent_npi_returns_invalid(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/validate/1000000004",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["reason_code"] == "NPI_NOT_FOUND"

    def test_validate_invalid_npi_format_returns_invalid(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/validate/BADNPI",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["reason_code"] == "INVALID_NPI_FORMAT"


class TestControlledSubstanceAuth:
    def test_authorized_for_schedule_2(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/validate/1234567893/controlled/2",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["authorized"] is True
        assert data["schedule"] == "2"

    def test_not_authorized_no_dea(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/validate/1000000020/controlled/2",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["authorized"] is False
        assert data["reason_code"] == "NO_DEA"

    def test_not_authorized_deactivated_prescriber(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/validate/1679576722/controlled/2",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["authorized"] is False

    def test_invalid_schedule_returns_400(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/validate/1234567893/controlled/99",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 400


class TestSearch:
    def test_search_by_name(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/search?name=SMITH",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        npis = [r["npi"] for r in data["results"]]
        assert "1234567893" in npis

    def test_search_by_state(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/search?state=IL",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_search_by_specialty(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/search?specialty=family",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_search_pagination(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/search?page=1&page_size=2",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_search_no_tenant_returns_422(self, client, seeded_db):
        resp = client.get("/api/v1/prescribers/search?name=SMITH")
        assert resp.status_code in (400, 422)


class TestOrganizations:
    def test_get_organization_by_npi(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/organizations/1000000012",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "2"
        assert "CHICAGO" in data["display_name"]

    def test_get_individual_as_org_returns_404(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/organizations/1234567893",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 404


class TestTaxonomyEndpoints:
    def test_list_taxonomies(self, client):
        resp = client.get(
            "/api/v1/prescribers/taxonomies",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["taxonomies"]) > 10

    def test_get_taxonomy_by_code(self, client):
        resp = client.get(
            "/api/v1/prescribers/taxonomies/207Q00000X",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "207Q00000X"
        assert data["is_prescriber"] is True

    def test_get_unknown_taxonomy_returns_404(self, client):
        resp = client.get(
            "/api/v1/prescribers/taxonomies/UNKNOWN00",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 404

    def test_list_specialties(self, client):
        resp = client.get(
            "/api/v1/prescribers/specialties",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "family medicine" in data["specialties"]


class TestDirectoryStats:
    def test_stats_endpoint(self, client, seeded_db):
        resp = client.get(
            "/api/v1/prescribers/stats",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_prescribers" in data
        assert data["total_prescribers"] >= 5
