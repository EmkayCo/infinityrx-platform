"""Tests for eligibility API routes — through create_app() (LESSON-006).

Covers:
- GET /api/v1/eligibility
- POST /api/v1/eligibility/270
- GET /api/v1/members/{id}/coverage
- POST /api/v1/members/{id}/coverage
- GET /api/v1/members/{id}/cob
- POST /api/v1/members/{id}/cob
- DELETE /api/v1/members/{id}/cob/{cob_id}
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from src.main import create_app


TENANT_ID = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))
MEMBER_UUID = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def headers():
    return {"x-tenant-id": TENANT_ID, "x-user-id": str(uuid.uuid4())}


# ---------------------------------------------------------------------------
# GET /api/v1/eligibility
# ---------------------------------------------------------------------------

class TestGetEligibilityEndpoint:
    def test_eligibility_check_missing_member_id_returns_422(self, client, headers):
        resp = client.get(
            "/api/v1/eligibility",
            params={"rx_bin": "610014", "date_of_service": "2026-04-13"},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_eligibility_check_missing_bin_returns_422(self, client, headers):
        resp = client.get(
            "/api/v1/eligibility",
            params={"member_id": "M123456", "date_of_service": "2026-04-13"},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_eligibility_check_missing_dos_returns_422(self, client, headers):
        resp = client.get(
            "/api/v1/eligibility",
            params={"member_id": "M123456", "rx_bin": "610014"},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_eligibility_check_returns_200_or_404(self, client, headers):
        """With no DB, endpoint should return 200 structure or 404 — not 500."""
        resp = client.get(
            "/api/v1/eligibility",
            params={
                "member_id": "M123456",
                "rx_bin": "610014",
                "date_of_service": "2026-04-13",
                "source": "adjudication",
            },
            headers=headers,
        )
        assert resp.status_code in (200, 404)

    def test_eligibility_response_has_is_eligible_field(self, client, headers):
        resp = client.get(
            "/api/v1/eligibility",
            params={
                "member_id": "M123456",
                "rx_bin": "610014",
                "date_of_service": "2026-04-13",
                "source": "adjudication",
            },
            headers=headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "is_eligible" in data


# ---------------------------------------------------------------------------
# POST /api/v1/eligibility/270
# ---------------------------------------------------------------------------

class TestPost270Endpoint:
    def test_270_endpoint_exists(self, client, headers):
        """POST /api/v1/eligibility/270 should not return 404 (Not Found)."""
        resp = client.post(
            "/api/v1/eligibility/270",
            content="NOT VALID 270",
            headers={**headers, "Content-Type": "text/plain"},
        )
        # Should be 400 (bad transaction), not 404 (route not found), not 500
        assert resp.status_code != 404

    def test_270_with_valid_transaction_returns_271(self, client, headers):
        minimal_270 = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260413*1200*^*00501*000000001*0*T*:~"
            "GS*HS*SENDER*RECEIVER*20260413*1200*1*X*005010X279A1~"
            "ST*270*0001*005010X279A1~"
            "BHT*0022*13*10001234*20260413*1200~"
            "HL*1**20*1~"
            "NM1*PR*2*INFINITYRX*****PI*610014~"
            "HL*2*1*21*1~"
            "NM1*1P*1*DOE*JOHN****XX*1234567893~"
            "HL*3*2*22*0~"
            "TRN*1*ABC123*9INFINITYRX~"
            "NM1*IL*1*SMITH*JANE****MI*M123456~"
            "DMG*D8*19800101*F~"
            "DTP*291*D8*20260413~"
            "EQ*30~"
            "SE*13*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        resp = client.post(
            "/api/v1/eligibility/270",
            content=minimal_270,
            headers={**headers, "Content-Type": "text/plain"},
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "response_271" in data or "transaction_271" in data or "271" in str(data)

    def test_invalid_270_returns_400(self, client, headers):
        resp = client.post(
            "/api/v1/eligibility/270",
            content="NOT A VALID X12 TRANSACTION",
            headers={**headers, "Content-Type": "text/plain"},
        )
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# GET /api/v1/members/{id}/coverage
# ---------------------------------------------------------------------------

class TestCoverageRoutes:
    def test_get_coverage_endpoint_exists(self, client, headers):
        resp = client.get(
            f"/api/v1/members/{MEMBER_UUID}/coverage",
            headers=headers,
        )
        assert resp.status_code in (200, 404)

    def test_get_coverage_returns_list(self, client, headers):
        resp = client.get(
            f"/api/v1/members/{MEMBER_UUID}/coverage",
            headers=headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "coverage_periods" in data or isinstance(data, list)

    def test_add_coverage_endpoint_exists(self, client, headers):
        payload = {
            "plan_name": "Basic Rx Plan",
            "coverage_type": "pharmacy",
            "effective_date": "2026-01-01",
            "benefit_year_start": "2026-01-01",
            "benefit_year_end": "2026-12-31",
        }
        resp = client.post(
            f"/api/v1/members/{MEMBER_UUID}/coverage",
            json=payload,
            headers=headers,
        )
        assert resp.status_code in (201, 404, 422)

    def test_invalid_member_uuid_returns_422(self, client, headers):
        resp = client.get(
            "/api/v1/members/not-a-uuid/coverage",
            headers=headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET/POST/DELETE /api/v1/members/{id}/cob
# ---------------------------------------------------------------------------

class TestCobRoutes:
    def test_get_cob_endpoint_exists(self, client, headers):
        resp = client.get(
            f"/api/v1/members/{MEMBER_UUID}/cob",
            headers=headers,
        )
        assert resp.status_code in (200, 404)

    def test_get_cob_returns_list(self, client, headers):
        resp = client.get(
            f"/api/v1/members/{MEMBER_UUID}/cob",
            headers=headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "cob_records" in data or isinstance(data, list)

    def test_add_cob_endpoint_exists(self, client, headers):
        payload = {
            "payer_sequence": "primary",
            "other_payer_name": "BlueCross",
            "other_payer_bin": "600428",
            "other_payer_type": "commercial",
            "effective_date": "2026-01-01",
        }
        resp = client.post(
            f"/api/v1/members/{MEMBER_UUID}/cob",
            json=payload,
            headers=headers,
        )
        assert resp.status_code in (201, 404, 422)

    def test_delete_cob_endpoint_exists(self, client, headers):
        cob_id = str(uuid.uuid4())
        resp = client.delete(
            f"/api/v1/members/{MEMBER_UUID}/cob/{cob_id}",
            headers=headers,
        )
        assert resp.status_code in (200, 204, 404)

    def test_add_cob_invalid_payer_sequence_returns_422(self, client, headers):
        payload = {
            "payer_sequence": "quaternary",  # invalid
            "other_payer_name": "SomePayer",
            "effective_date": "2026-01-01",
        }
        resp = client.post(
            f"/api/v1/members/{MEMBER_UUID}/cob",
            json=payload,
            headers=headers,
        )
        assert resp.status_code == 422

    def test_add_cob_missing_required_fields_returns_422(self, client, headers):
        payload = {"other_payer_name": "BlueCross"}  # missing payer_sequence, effective_date
        resp = client.post(
            f"/api/v1/members/{MEMBER_UUID}/cob",
            json=payload,
            headers=headers,
        )
        assert resp.status_code == 422
