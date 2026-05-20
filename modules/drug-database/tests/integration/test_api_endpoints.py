"""Integration tests for drug database API endpoints.

Tests exercise the full stack through create_app() with a SQLite DB.
Cross-tenant isolation is verified for tenant-scoped resources.

Seeded tables used: Drug (ndc_tables.py) + DrugNADACPricing (pricing_tables.py).
drug_products (tables.py) was never migrated; these tests target the live
seeded schema instead.
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
from src.models.ndc_tables import Drug, NDCBase
from src.models.pricing_tables import DrugNADACPricing, PricingBase
from src.models.tables import (
    DrugBase,
    DrugInteraction,
    DrugShortage,
    DrugPricingHistory,
    RemsProgram,
    TenantPricingOverride,
    TherapeuticEquivalence,
)

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"
_NOW = datetime.now(timezone.utc)

# Stable product_id values for test drugs
_METFORMIN_ID = "00093-3149"
_HUMALOG_ID = "00002-1436"


@pytest.fixture(scope="module")
def _engine():
    engine = create_engine(
        "sqlite:///file:drug_test_api?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )
    # SQLite does not support schemas — strip for all metadata objects
    for table in DrugBase.metadata.tables.values():
        table.schema = None
    for table in NDCBase.metadata.tables.values():
        table.schema = None
    for table in PricingBase.metadata.tables.values():
        table.schema = None

    DrugBase.metadata.create_all(engine)
    NDCBase.metadata.create_all(engine)
    PricingBase.metadata.create_all(engine)
    yield engine
    PricingBase.metadata.drop_all(engine)
    NDCBase.metadata.drop_all(engine)
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
    """Seed test data once for the module using seeded-schema models."""
    Factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    session = Factory()

    # Drug rows (seeded FDA NDC schema)
    d1 = Drug(
        product_id=_METFORMIN_ID,
        product_ndc="00093-3149",
        ndc_11="00093314900",  # product-level, package "00"
        non_proprietary_name="metformin hydrochloride",
        dosage_form_name="TABLET",
        route_name="ORAL",
        labeler_name="Teva Pharmaceuticals",
        marketing_category_name="ANDA",
        dea_schedule=None,
        ndc_exclude_flag=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    d2 = Drug(
        product_id=_HUMALOG_ID,
        product_ndc="00002-1436",
        ndc_11="00002143600",
        proprietary_name="Humalog",
        non_proprietary_name="insulin lispro",
        dosage_form_name="INJECTION",
        route_name="SUBCUTANEOUS",
        labeler_name="Eli Lilly",
        marketing_category_name="NDA",
        dea_schedule=None,
        ndc_exclude_flag=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add_all([d1, d2])

    # NADAC pricing for metformin
    nadac = DrugNADACPricing(
        ndc_11="00093314900",
        ndc_description="METFORMIN HCL 500 MG TABLET",
        nadac_per_unit=Decimal("0.045000"),
        effective_date=date(2026, 1, 1),
        pricing_unit="EA",
        as_of_date=date(2026, 1, 1),
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add(nadac)

    # Drug interaction
    i1 = DrugInteraction(
        drug_1_identifier="00093314900",
        drug_1_identifier_type="ndc",
        drug_1_name="Metformin",
        drug_2_identifier="00002143600",
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
        brand_ndc="00002143600",
        brand_name="Humalog",
        generic_ndc="00093314900",
        generic_name="insulin lispro",
        te_code="AB",
        is_therapeutically_equivalent=True,
        data_source="fda_orange_book",
        last_updated_at=_NOW,
    )
    # Non-AB rated (should not be returned as equivalent)
    te2 = TherapeuticEquivalence(
        brand_ndc="00002143600",
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
        ndc_11="00002143600",
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
        ndc_11="00093314900",
        shortage_status="active",
        start_date=date(2026, 1, 1),
        reason="Manufacturing delay",
        data_source="fda_shortage",
        last_updated_at=_NOW,
        created_at=_NOW,
    )
    session.add(shortage)

    # Pricing history row (tables.py DrugPricingHistory)
    ph = DrugPricingHistory(
        ndc_11="00093314900",
        price_type="NADAC",
        old_price=Decimal("0.040000"),
        new_price=Decimal("0.045000"),
        change_percentage=Decimal("12.5000"),
        effective_date=date(2026, 1, 1),
        data_source="cms_nadac",
        created_at=_NOW,
    )
    session.add(ph)

    # Tenant A MAC override
    override_a = TenantPricingOverride(
        tenant_id=uuid.UUID(TENANT_A),
        ndc_11="00093314900",
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
        resp = client.get("/api/v1/drugs/lookup/00093314900", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ndc_11"] == "00093314900"
        # proprietary_name is None for metformin; non_proprietary_name used as display
        assert "metformin" in data["drug_name_display"].lower()

    def test_lookup_id_is_string(self, client, seed_db) -> None:
        """id field is now product_id string, not UUID."""
        resp = client.get("/api/v1/drugs/lookup/00093314900", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        assert resp.json()["id"] == _METFORMIN_ID

    def test_lookup_not_found_returns_404(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/lookup/99999999999", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 404

    def test_lookup_invalid_ndc_returns_400(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/lookup/bad-ndc", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 400


class TestDrugSearch:
    def test_search_by_nonproprietary_name(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/search?q=metformin", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        ndcs = [r["ndc_11"] for r in data["results"]]
        assert "00093314900" in ndcs

    def test_search_by_proprietary_name(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/search?q=Humalog", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert data["results"][0]["proprietary_name"] == "Humalog"

    def test_search_no_results(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/search?q=ZZZZZ_NONEXISTENT_DRUG",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_search_nulled_out_fields(self, client, seed_db) -> None:
        """Fields without source columns in seeded schema must be null/False — not fabricated."""
        resp = client.get("/api/v1/drugs/search?q=metformin", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        r = resp.json()["results"][0]
        assert r["is_specialty"] is False
        assert r["is_biosimilar"] is False
        assert r["is_glp1"] is False
        assert r["gpi_code"] is None
        assert r["atc_code"] is None
        assert r["therapeutic_class_1"] is None
        assert r["marketing_status"] is None
        assert r["otc_rx"] is None


class TestDrugPricing:
    def test_pricing_returns_nadac(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/pricing/00093314900", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["price_type"] == "NADAC"
        # Decimal precision check
        assert Decimal(data[0]["price_per_unit"]) == Decimal("0.045000")

    def test_pricing_no_price_returns_empty(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/pricing/00002143600", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_pricing_history_returned(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/pricing/00093314900/history", headers={"X-Tenant-Id": TENANT_A}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["price_type"] == "NADAC"


class TestInteractions:
    def test_interaction_found(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/interactions?identifiers=00093314900&identifiers=00002143600",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["severity"] == "moderate"

    def test_single_drug_no_interactions(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/interactions?identifiers=00093314900",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestTherapeuticEquivalence:
    def test_ab_rated_equivalent_returned(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/equivalents/00002143600", headers={"X-Tenant-Id": TENANT_A}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for item in data:
            assert item["is_therapeutically_equivalent"] is True

    def test_non_ab_rated_not_returned(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/equivalents/00002143600", headers={"X-Tenant-Id": TENANT_A}
        )
        te_codes = [item["te_code"] for item in resp.json()]
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
        assert resp.json() == []

    def test_mac_upload_valid_csv(self, client, seed_db) -> None:
        csv_content = "ndc,price_per_unit,effective_date,unit_type\n00093314900,0.030000,2026-06-01,EA\n"
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
        resp = client.get("/api/v1/drugs/rems/00002143600", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["rems_program_name"] == "Humalog REMS"

    def test_rems_empty_for_non_rems_drug(self, client, seed_db) -> None:
        resp = client.get("/api/v1/drugs/rems/00093314900", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        assert resp.json() == []


class TestShortages:
    def test_shortage_listed(self, client, seed_db) -> None:
        resp = client.get(
            "/api/v1/drugs/shortages/00093314900", headers={"X-Tenant-Id": TENANT_A}
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
