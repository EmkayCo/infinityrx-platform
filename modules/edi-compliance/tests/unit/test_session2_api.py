"""Tests for new Session 2 API endpoints (271/277 parse, 271/276/277/837I/D generate)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.x12.generators.gen_271 import generate_271
from src.x12.generators.gen_277 import generate_277
from src.x12.generators.schemas import Generate271Request, Generate277Request

from tests.conftest import _FAKE_USER_FOR_TESTS  # noqa: E402

_TENANT_ID = str(uuid.uuid4())
_TENANT_HEADERS = {"x-tenant-id": _TENANT_ID}
_FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


async def _mock_get_session():
    yield None


@pytest.fixture()
def client():
    from shared.auth.dependencies import get_current_user
    app = create_app()
    try:
        from shared.db.session import get_session  # type: ignore[import]
        app.dependency_overrides[get_session] = _mock_get_session
    except (ImportError, Exception):
        pass
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER_FOR_TESTS
    with TestClient(app) as c:
        yield c


def _make_271_raw(benefit_info=None):
    t = uuid.UUID("00000000-0000-0000-0000-000000000001")
    tp = uuid.UUID("00000000-0000-0000-0000-000000000002")
    req = Generate271Request(
        tenant_id=t, trading_partner_id=tp,
        isa_control_number=1, gs_control_number=1,
        receiver_id="RECEIVER       ",
        payer_id="PAYER01", payer_name="AETNA",
        subscriber_id="SUB001", subscriber_last_name="HILL", subscriber_first_name="MARY",
        benefit_info=benefit_info or [],
    )
    return generate_271(req, now=_FIXED_NOW)


def _make_277_raw(claim_statuses=None):
    t = uuid.UUID("00000000-0000-0000-0000-000000000001")
    tp = uuid.UUID("00000000-0000-0000-0000-000000000002")
    req = Generate277Request(
        tenant_id=t, trading_partner_id=tp,
        isa_control_number=1, gs_control_number=1,
        receiver_id="SUBMITTER      ",
        payer_id="PAYER01", payer_name="UHC",
        claim_statuses=claim_statuses or [],
    )
    return generate_277(req, now=_FIXED_NOW)


class TestParse271Api:
    def test_parse_271_returns_200(self, client):
        raw = _make_271_raw()
        resp = client.post("/api/v1/edi/parse/271", json={"content": raw}, headers=_TENANT_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction_type"] == "271"
        assert data["is_valid"] is True
        assert data["data"]["payer_id"] == "PAYER01"

    def test_parse_271_invalid_edi_returns_422(self, client):
        resp = client.post("/api/v1/edi/parse/271", json={"content": "NOT EDI"}, headers=_TENANT_HEADERS)
        assert resp.status_code == 422

    def test_parse_271_missing_tenant_returns_401(self, client):
        resp = client.post("/api/v1/edi/parse/271", json={"content": "x"})
        assert resp.status_code == 401

    def test_parse_271_data_fields(self, client):
        raw = _make_271_raw()
        resp = client.post("/api/v1/edi/parse/271", json={"content": raw}, headers=_TENANT_HEADERS)
        d = resp.json()["data"]
        assert "subscriber_id" in d
        assert "eligibility_status" in d
        assert "benefit_count" in d


class TestParse277Api:
    def test_parse_277_returns_200(self, client):
        raw = _make_277_raw()
        resp = client.post("/api/v1/edi/parse/277", json={"content": raw}, headers=_TENANT_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction_type"] == "277"
        assert data["data"]["payer_id"] == "PAYER01"

    def test_parse_277_invalid_edi_returns_422(self, client):
        resp = client.post("/api/v1/edi/parse/277", json={"content": "NOT EDI"}, headers=_TENANT_HEADERS)
        assert resp.status_code == 422

    def test_parse_277_missing_tenant_returns_401(self, client):
        resp = client.post("/api/v1/edi/parse/277", json={"content": "x"})
        assert resp.status_code == 401

    def test_parse_277_data_fields(self, client):
        raw = _make_277_raw(claim_statuses=[{"status_category_code": "F1"}])
        resp = client.post("/api/v1/edi/parse/277", json={"content": raw}, headers=_TENANT_HEADERS)
        d = resp.json()["data"]
        assert d["claim_count"] == 1


class TestGenerate271Api:
    def test_generate_271_returns_200(self, client):
        payload = {
            "tenant_id": str(uuid.uuid4()),
            "trading_partner_id": str(uuid.uuid4()),
            "isa_control_number": 1,
            "gs_control_number": 1,
            "receiver_id": "PAYER          ",
            "payer_id": "PAYER01",
            "payer_name": "ANTHEM",
            "subscriber_id": "SUB001",
            "subscriber_last_name": "DOE",
            "subscriber_first_name": "JANE",
        }
        resp = client.post("/api/v1/edi/generate/271", json=payload, headers=_TENANT_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["transaction_type"] == "271"

    def test_generate_271_missing_tenant(self, client):
        resp = client.post("/api/v1/edi/generate/271", json={})
        assert resp.status_code == 401


class TestGenerate276Api:
    def test_generate_276_returns_200(self, client):
        payload = {
            "tenant_id": str(uuid.uuid4()),
            "trading_partner_id": str(uuid.uuid4()),
            "isa_control_number": 1,
            "gs_control_number": 1,
            "receiver_id": "PAYER          ",
            "payer_id": "PAYER01",
            "payer_name": "CIGNA",
            "provider_npi": "1234567893",
            "provider_name": "CLINIC",
        }
        resp = client.post("/api/v1/edi/generate/276", json=payload, headers=_TENANT_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["transaction_type"] == "276"

    def test_generate_276_missing_tenant(self, client):
        resp = client.post("/api/v1/edi/generate/276", json={})
        assert resp.status_code == 401


class TestGenerate277Api:
    def test_generate_277_returns_200(self, client):
        payload = {
            "tenant_id": str(uuid.uuid4()),
            "trading_partner_id": str(uuid.uuid4()),
            "isa_control_number": 1,
            "gs_control_number": 1,
            "receiver_id": "SUBMITTER      ",
            "payer_id": "PAYER01",
            "payer_name": "HUMANA",
        }
        resp = client.post("/api/v1/edi/generate/277", json=payload, headers=_TENANT_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["transaction_type"] == "277"

    def test_generate_277_missing_tenant(self, client):
        resp = client.post("/api/v1/edi/generate/277", json={})
        assert resp.status_code == 401


class TestGenerate837IApi:
    def _req_payload(self, **kwargs):
        defaults = {
            "tenant_id": str(uuid.uuid4()),
            "trading_partner_id": str(uuid.uuid4()),
            "isa_control_number": 1,
            "gs_control_number": 1,
            "receiver_id": "RECEIVER       ",
            "billing_provider_npi": "1234567893",
            "billing_provider_name": "HOSPITAL",
            "subscriber_id": "SUB001",
            "subscriber_last_name": "SMITH",
            "subscriber_first_name": "JOE",
            "subscriber_dob": "19700101",
            "subscriber_gender": "M",
            "payer_id": "PAYER01",
            "payer_name": "MEDICARE",
            "claims": [{
                "claim_id": "CLM001",
                "charge_amount": "500.00",
                "revenue_lines": [{"revenue_code": "0120", "procedure_code": "99213", "charge_amount": "500.00"}],
            }],
        }
        defaults.update(kwargs)
        return defaults

    def test_generate_837i_returns_200(self, client):
        resp = client.post("/api/v1/edi/generate/837i", json=self._req_payload(), headers=_TENANT_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["transaction_type"] == "837I"

    def test_generate_837i_bad_npi_returns_422(self, client):
        payload = self._req_payload(billing_provider_npi="9999999999")
        resp = client.post("/api/v1/edi/generate/837i", json=payload, headers=_TENANT_HEADERS)
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "GENERATION_FAILED"

    def test_generate_837i_missing_tenant(self, client):
        resp = client.post("/api/v1/edi/generate/837i", json={})
        assert resp.status_code == 401


class TestGenerate837DApi:
    def _req_payload(self, **kwargs):
        defaults = {
            "tenant_id": str(uuid.uuid4()),
            "trading_partner_id": str(uuid.uuid4()),
            "isa_control_number": 1,
            "gs_control_number": 1,
            "receiver_id": "RECEIVER       ",
            "billing_provider_npi": "1234567893",
            "billing_provider_name": "DENTAL CLINIC",
            "subscriber_id": "SUB001",
            "subscriber_last_name": "DOE",
            "subscriber_first_name": "JANE",
            "subscriber_dob": "19800101",
            "subscriber_gender": "F",
            "payer_id": "DPAYER",
            "payer_name": "DENTAL PLAN",
            "claims": [{
                "claim_id": "DC001",
                "charge_amount": "150.00",
                "service_lines": [{"procedure_code": "D0120", "charge_amount": "150.00"}],
            }],
        }
        defaults.update(kwargs)
        return defaults

    def test_generate_837d_returns_200(self, client):
        resp = client.post("/api/v1/edi/generate/837d", json=self._req_payload(), headers=_TENANT_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["transaction_type"] == "837D"

    def test_generate_837d_bad_npi_returns_422(self, client):
        payload = self._req_payload(billing_provider_npi="9999999999")
        resp = client.post("/api/v1/edi/generate/837d", json=payload, headers=_TENANT_HEADERS)
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "GENERATION_FAILED"

    def test_generate_837d_missing_tenant(self, client):
        resp = client.post("/api/v1/edi/generate/837d", json={})
        assert resp.status_code == 401
