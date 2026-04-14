"""Extended API integration tests covering crosswalk, ASP, unified spend, denial, analytics."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.models.tables import MedicalClaimsBase, ClaimRecord, HcpcsNdcCrosswalk, AspPricing

TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")

_CLAIM = {
    "claim_number": "EXT-001",
    "claim_type": "professional",
    "patient_member_id": "MBR-EXT",
    "rendering_provider_npi": "1234567890",
    "date_of_service": "2026-02-01",
    "procedure_code": "J0135",
    "billed_amount": "300.00",
}


@pytest.fixture(scope="module")
def ext_app(_engine):
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    app = create_app()

    @app.middleware("http")
    async def inject_db(request, call_next):
        session = SessionLocal()
        request.state.db = session
        try:
            return await call_next(request)
        finally:
            session.close()

    return TestClient(app)


@pytest.fixture
def ext_client(ext_app):
    return ext_app


def _create_claim(client, tenant_id=TENANT_A, override=None):
    payload = {**_CLAIM, **(override or {})}
    return client.post(
        "/api/v1/medical-claims/claims",
        json=payload,
        headers={"x-tenant-id": str(tenant_id)},
    )


class TestCrosswalkEndpoints:
    def test_crosswalk_lookup_empty(self, ext_client):
        resp = ext_client.get(
            "/api/v1/medical-claims/crosswalk/J9998",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["confidence"] == "manual"
        assert data["requires_manual_review"] is True

    def test_unmapped_claims_list(self, ext_client):
        resp = ext_client.get(
            "/api/v1/medical-claims/crosswalk/unmapped",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_set_manual_mapping(self, ext_client):
        create_resp = _create_claim(ext_client, override={"claim_number": "XWLK-001"})
        claim_id = create_resp.json()["id"]

        resp = ext_client.post(
            f"/api/v1/medical-claims/crosswalk/claims/{claim_id}/drug-mapping",
            params={"ndc": "11111111111"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        assert resp.json()["mapping_confidence"] == "manual"

    def test_set_manual_mapping_invalid_ndc(self, ext_client):
        create_resp = _create_claim(ext_client, override={"claim_number": "XWLK-002"})
        claim_id = create_resp.json()["id"]

        resp = ext_client.post(
            f"/api/v1/medical-claims/crosswalk/claims/{claim_id}/drug-mapping",
            params={"ndc": "BAD"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 400


class TestAspEndpoints:
    def test_current_quarter_summary(self, ext_client):
        resp = ext_client.get(
            "/api/v1/medical-claims/asp/current-quarter",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "quarter" in data
        assert "record_count" in data

    def test_asp_lookup_not_found(self, ext_client):
        resp = ext_client.get(
            "/api/v1/medical-claims/asp/J9996",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 404

    def test_asp_refresh_valid_quarter(self, ext_client):
        resp = ext_client.post(
            "/api/v1/medical-claims/asp/refresh",
            params={"quarter": "2026-Q2"},
            json=[
                {"hcpcs_code": "J9000", "asp_per_unit": "50.000000", "effective_date": "2026-04-01"},
            ],
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["records_loaded"] == 1

    def test_asp_refresh_invalid_quarter(self, ext_client):
        resp = ext_client.post(
            "/api/v1/medical-claims/asp/refresh",
            params={"quarter": "2026-Q9"},
            json=[],
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 400

    def test_asp_lookup_found(self, ext_client):
        # First load an ASP record
        ext_client.post(
            "/api/v1/medical-claims/asp/refresh",
            params={"quarter": "2026-Q1"},
            json=[
                {"hcpcs_code": "J0135", "asp_per_unit": "12.500000", "effective_date": "2026-01-01"},
            ],
            headers={"x-tenant-id": str(TENANT_A)},
        )
        resp = ext_client.get(
            "/api/v1/medical-claims/asp/J0135",
            params={"as_of": "2026-02-15"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        assert resp.json()["asp_per_unit"] == "12.500000"


class TestUnifiedSpendEndpoints:
    def test_list_unified_spend_empty(self, ext_client):
        resp = ext_client.get(
            "/api/v1/medical-claims/unified-spend",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_member_drug_timeline(self, ext_client):
        member_id = str(uuid.uuid4())
        resp = ext_client.get(
            f"/api/v1/medical-claims/unified-spend/member/{member_id}",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200

    def test_duplications_endpoint(self, ext_client):
        resp = ext_client.get(
            "/api/v1/medical-claims/unified-spend/duplications",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestDenialEndpoints:
    def test_list_denials_empty(self, ext_client):
        resp = ext_client.get(
            "/api/v1/medical-claims/denials",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200

    def test_denial_analytics(self, ext_client):
        resp = ext_client.get(
            "/api/v1/medical-claims/denials/analytics",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "denial_rate" in data

    def test_appeal_denied_claim(self, ext_client):
        # Create → validate → deny → appeal
        create = _create_claim(ext_client, override={"claim_number": "APPEAL-001"})
        claim_id = create.json()["id"]

        ext_client.post(
            f"/api/v1/medical-claims/claims/{claim_id}/status",
            json={"status": "validated"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        ext_client.post(
            f"/api/v1/medical-claims/claims/{claim_id}/status",
            json={"status": "denied", "denial_reason_code": "50"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        resp = ext_client.post(
            f"/api/v1/medical-claims/claims/{claim_id}/appeal",
            json={"appeal_reason": "Medical necessity is documented in records"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "appealed"

    def test_appeal_non_denied_returns_422(self, ext_client):
        create = _create_claim(ext_client, override={"claim_number": "APPEAL-002"})
        claim_id = create.json()["id"]

        resp = ext_client.post(
            f"/api/v1/medical-claims/claims/{claim_id}/appeal",
            json={"appeal_reason": "Medical necessity is documented in records"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 422

    def test_appeal_unknown_claim_returns_404(self, ext_client):
        resp = ext_client.post(
            f"/api/v1/medical-claims/claims/{uuid.uuid4()}/appeal",
            json={"appeal_reason": "Medical necessity is documented in records"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 404


class TestAnalyticsEndpoints:
    def test_340b_claims_list(self, ext_client):
        resp = ext_client.get(
            "/api/v1/medical-claims/340b/claims",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200

    def test_340b_summary(self, ext_client):
        resp = ext_client.get(
            "/api/v1/medical-claims/340b/summary",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_340b_claims" in data

    def test_waste_report(self, ext_client):
        resp = ext_client.get(
            "/api/v1/medical-claims/waste/report",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_site_of_care_analysis(self, ext_client):
        resp = ext_client.get(
            "/api/v1/medical-claims/site-of-care/analysis",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200

    def test_site_of_care_opportunities(self, ext_client):
        resp = ext_client.get(
            "/api/v1/medical-claims/site-of-care/opportunities",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200

    def test_stats(self, ext_client):
        resp = ext_client.get(
            "/api/v1/medical-claims/stats",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "by_status" in data
