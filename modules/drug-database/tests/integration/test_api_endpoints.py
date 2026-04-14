"""Integration tests for drug database API endpoints.

Tests exercise the full stack through create_app() with a SQLite DB.
Cross-tenant isolation is verified for tenant-scoped resources.
"""
from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.dependencies import get_db
from src.main import create_app
from src.models.tables import (
    DrugBase,
    DrugInteraction,
    DrugPricing,
    DrugProduct,
    DrugShortage,
    RemsProgram,
    TenantPricingOverride,
    TherapeuticEquivalence,
)

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"
_NOW = datetime.now(timezone.utc)


@pytest.fixture(scope="module")
def _engine():
    # Use a named in-memory SQLite DB with shared cache so all connections
    # see the same tables and data.
    engine = create_engine(
        "sqlite:///file:drug_test_api?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )
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


@pytest.fixture(scope="module")
def seed_db(_engine):
    """Seed test data once for the module."""
    Factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    session = Factory()

    # Drug products
    d1 = DrugProduct(
        ndc_11="00093314905",
        ndc_formatted="00093-3149-05",
        labeler_code="00093",
        product_code="3149",
        package_code="05",
        drug_name_display="Metformin 500mg Tablets",
        nonproprietary_name="metformin hydrochloride",
        drug_type="generic",
        marketing_status="active",
        is_active=True,
        is_specialty=False,
        is_biosimilar=False,
        is_glp1=False,
        unit_dose=False,
        is_limited_distribution=False,
        data_source="fda_ndc",
        last_updated_at=_NOW,
        created_at=_NOW,
        updated_at=_NOW,
    )
    d2 = DrugProduct(
        ndc_11="00002143601",
        ndc_formatted="00002-1436-01",
        labeler_code="00002",
        product_code="1436",
        package_code="01",
        drug_name_display="Humalog 100 Units/mL",
        proprietary_name="Humalog",
        nonproprietary_name="insulin lispro",
        drug_type="brand",
        marketing_status="active",
        is_active=True,
        is_specialty=True,
        is_biosimilar=False,
        is_glp1=False,
        unit_dose=False,
        is_limited_distribution=False,
        data_source="fda_ndc",
        last_updated_at=_NOW,
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add_all([d1, d2])

    # Pricing
    p1 = DrugPricing(
        ndc_11="00093314905",
        price_type="NADAC",
        price_per_unit=Decimal("0.045000"),
        unit_type="EA",
        effective_date=date(2026, 1, 1),
        data_source="cms_nadac",
        created_at=_NOW,
    )
    session.add(p1)

    # Interaction
    i1 = DrugInteraction(
        drug_1_identifier="00093314905",
        drug_1_identifier_type="ndc",
        drug_1_name="Metformin",
        drug_2_identifier="00002143601",
        drug_2_identifier_type="ndc",
        drug_2_name="Insulin lispro",
        severity="moderate",
        interaction_description="Monitor blood glucose",
        management_recommendation="Monitor closely",
        data_source="fdb",
        last_updated_at=_NOW,
    )
    session.add(i1)

    # Therapeutic equivalence (AB-rated)
    te1 = TherapeuticEquivalence(
        brand_ndc="00002143601",
        brand_name="Humalog",
        generic_ndc="00093314905",
        generic_name="insulin lispro",
        te_code="AB",
        is_therapeutically_equivalent=True,
        data_source="fda_orange_book",
        last_updated_at=_NOW,
    )
    # Non-AB rated (should not be returned as equivalent)
    te2 = TherapeuticEquivalence(
        brand_ndc="00002143601",
        brand_name="Humalog",
        generic_ndc="99999999999",
        generic_name="some other drug",
        te_code="BC",
        is_therapeutically_equivalent=False,
        data_source="fda_orange_book",
        last_updated_at=_NOW,
    )
    session.add_all([te1, te2])

    # REMS
    rems = RemsProgram(
        ndc_11="00002143601",
        rems_program_name="Humalog REMS",
        rems_status="active",
        certified_pharmacy_required=True,
        certified_prescriber_required=False,
        patient_registry_required=False,
        lab_testing_required=False,
        restricted_distribution=False,
        patient_agreement_required=False,
        data_source="fda_rems",
        last_updated_at=_NOW,
        created_at=_NOW,
    )
    session.add(rems)

    # Drug shortage
    shortage = DrugShortage(
        ndc_11="00093314905",
        shortage_status="active",
        start_date=date(2026, 1, 1),
        reason="Manufacturing delay",
        data_source="fda_shortage",
        last_updated_at=_NOW,
        created_at=_NOW,
    )
    session.add(shortage)

    # Tenant A MAC override
    override_a = TenantPricingOverride(
        tenant_id=uuid.UUID(TENANT_A),
        ndc_11="00093314905",
        price_type="MAC",
        price_per_unit=Decimal("0.035000"),
        effective_date=date(2026, 1, 1),
        data_source="tenant_mac",
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add(override_a)

    session.commit()
    session.close()


class TestDrugLookup:
    def test_lookup_by_ndc11(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/lookup/00093314905", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ndc_11"] == "00093314905"
        assert data["drug_name_display"] == "Metformin 500mg Tablets"

    def test_lookup_5_4_2_format_normalized(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/lookup/00093-3149-05", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        assert resp.json()["ndc_11"] == "00093314905"

    def test_lookup_not_found_returns_404(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/lookup/99999999999", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 404

    def test_lookup_invalid_ndc_returns_400(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/lookup/bad-ndc", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 400


class TestDrugSearch:
    def test_search_by_name(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/search?q=Metformin", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        ndcs = [r["ndc_11"] for r in data["results"]]
        assert "00093314905" in ndcs

    def test_search_with_specialty_filter(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/search?q=Humalog&is_specialty=true",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for r in data["results"]:
            assert r["is_specialty"] is True

    def test_search_no_results(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/search?q=ZZZZZ_NONEXISTENT_DRUG",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestDrugPricing:
    def test_pricing_returns_current_price(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/pricing/00093314905", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["price_type"] == "NADAC"

    def test_pricing_no_price_returns_empty(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/pricing/00002143601", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_pricing_history_empty_for_new_drug(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/pricing/00093314905/history", headers={"X-Tenant-Id": TENANT_A}
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestInteractions:
    def test_interaction_found(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/interactions?identifiers=00093314905&identifiers=00002143601",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["severity"] == "moderate"

    def test_single_drug_no_interactions(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/interactions?identifiers=00093314905",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestTherapeuticEquivalence:
    def test_ab_rated_equivalent_returned(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/equivalents/00002143601", headers={"X-Tenant-Id": TENANT_A}
        )
        assert resp.status_code == 200
        data = resp.json()
        # Only AB-rated (is_therapeutically_equivalent=True) should be returned
        assert len(data) >= 1
        for item in data:
            assert item["is_therapeutically_equivalent"] is True

    def test_non_ab_rated_not_returned(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/equivalents/00002143601", headers={"X-Tenant-Id": TENANT_A}
        )
        te_codes = [item["te_code"] for item in resp.json()]
        # BC-rated entry should not appear
        assert "BC" not in te_codes


class TestTenantOverrides:
    def test_tenant_a_sees_own_overrides(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/overrides", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert all(r["tenant_id"] == TENANT_A for r in data)

    def test_tenant_b_sees_no_overrides(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/overrides", headers={"X-Tenant-Id": TENANT_B})
        assert resp.status_code == 200
        # Tenant B has no overrides — cross-tenant isolation
        assert resp.json() == []

    def test_mac_upload_valid_csv(self, client, seed_db) -> None:
        csv_content = "ndc,price_per_unit,effective_date,unit_type\n00093314905,0.030000,2026-06-01,EA\n"
        resp = client.post(
            "/api/v1/drugs/overrides/upload",
            files={"file": ("mac.csv", BytesIO(csv_content.encode()), "text/csv")},
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["records_applied"] >= 1

    def test_mac_upload_invalid_ndc_returns_422(self, client, seed_db) -> None:
        csv_content = "ndc,price_per_unit,effective_date\nbad-ndc,0.030000,2026-06-01\n"
        resp = client.post(
            "/api/v1/drugs/overrides/upload",
            files={"file": ("mac.csv", BytesIO(csv_content.encode()), "text/csv")},
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 422


class TestREMS:
    def test_rems_returned_for_ndc(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/rems/00002143601", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["rems_program_name"] == "Humalog REMS"

    def test_rems_empty_for_non_rems_drug(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/rems/00093314905", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        assert resp.json() == []


class TestShortages:
    def test_shortage_listed(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/shortages/00093314905", headers={"X-Tenant-Id": TENANT_A}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["shortage_status"] == "active"

    def test_active_shortages_list(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/shortages?status=active", headers={"X-Tenant-Id": TENANT_A}
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
