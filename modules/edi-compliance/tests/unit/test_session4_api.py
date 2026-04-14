"""Session 4 — API endpoint tests for 278/999/TA1 generate and parse."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

_T = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))
_TP = str(uuid.UUID("00000000-0000-0000-0000-000000000002"))
_HEADERS = {"x-tenant-id": _T}
_FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def client():
    from src.main import create_app
    try:
        from shared.db.session import get_session  # type: ignore[import]
    except ImportError:
        get_session = None

    app = create_app()

    async def _mock_session():
        yield None

    if get_session is not None:
        from src.api.generate import get_session as gen_get_session  # type: ignore[import]
        app.dependency_overrides[gen_get_session] = _mock_session

    return TestClient(app)


def _base278_payload(**kwargs):
    defaults = {
        "tenant_id": _T,
        "trading_partner_id": _TP,
        "isa_control_number": 1,
        "gs_control_number": 1,
        "receiver_id": "PAYER          ",
        "payer_id": "P1",
        "payer_name": "PAYER",
        "provider_npi": "1234567893",
        "provider_name": "CLINIC",
        "subscriber_id": "S1",
        "subscriber_last_name": "A",
        "subscriber_first_name": "B",
        "service_reviews": [],
    }
    defaults.update(kwargs)
    return defaults


def _base999_payload(**kwargs):
    defaults = {
        "tenant_id": _T,
        "trading_partner_id": _TP,
        "isa_control_number": 1,
        "gs_control_number": 1,
        "receiver_id": "RECV           ",
        "original_isa_control": 1,
        "original_gs_control": 1,
        "original_transaction_type": "837",
        "ack_code": "A",
    }
    defaults.update(kwargs)
    return defaults


def _baseta1_payload(**kwargs):
    defaults = {
        "tenant_id": _T,
        "trading_partner_id": _TP,
        "isa_control_number": 1,
        "gs_control_number": 1,
        "receiver_id": "RECV           ",
        "ack_control_number": 1,
        "ack_date": "260101",
        "ack_time": "1200",
        "ack_code": "A",
        "error_code": "000",
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Generate 278
# ---------------------------------------------------------------------------

class TestGenerate278Api:
    def test_generate_278_success(self, client):
        resp = client.post("/api/v1/edi/generate/278", json=_base278_payload(), headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction_type"] == "278"
        assert "ST*278*" in data["content"]

    def test_generate_278_missing_tenant(self, client):
        resp = client.post("/api/v1/edi/generate/278", json=_base278_payload())
        assert resp.status_code == 401

    def test_generate_278_invalid_tenant(self, client):
        resp = client.post("/api/v1/edi/generate/278", json=_base278_payload(), headers={"x-tenant-id": "not-a-uuid"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Generate 999
# ---------------------------------------------------------------------------

class TestGenerate999Api:
    def test_generate_999_success(self, client):
        resp = client.post("/api/v1/edi/generate/999", json=_base999_payload(), headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction_type"] == "999"
        assert "AK9*" in data["content"]

    def test_generate_999_ack_code_r(self, client):
        payload = _base999_payload(ack_code="R")
        resp = client.post("/api/v1/edi/generate/999", json=payload, headers=_HEADERS)
        assert resp.status_code == 200
        assert "AK9*R" in resp.json()["content"]


# ---------------------------------------------------------------------------
# Generate TA1
# ---------------------------------------------------------------------------

class TestGenerateTA1Api:
    def test_generate_ta1_success(self, client):
        resp = client.post("/api/v1/edi/generate/ta1", json=_baseta1_payload(), headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction_type"] == "TA1"
        assert "TA1*" in data["content"]


# ---------------------------------------------------------------------------
# Parse 278
# ---------------------------------------------------------------------------

class TestParse278Api:
    def test_parse_278_success(self, client):
        from src.x12.generators.gen_278 import generate_278
        from src.x12.generators.schemas import Generate278Request
        req = Generate278Request(**_base278_payload())
        content = generate_278(req)
        resp = client.post("/api/v1/edi/parse/278", json={"content": content}, headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction_type"] == "278"
        assert data["data"]["payer_id"] == "P1"

    def test_parse_278_invalid_content(self, client):
        resp = client.post("/api/v1/edi/parse/278", json={"content": "NOTVALIDEDI"}, headers=_HEADERS)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Parse 834
# ---------------------------------------------------------------------------

class TestParse834Api:
    _SAMPLE_834 = (
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
        "*260101*1200*^*00501*000000001*0*T*:~"
        "GS*BE*SENDER*RECEIVER*20260101*1200*1*X*005010X220A1~"
        "ST*834*0001*005010X220A1~"
        "BGN*00*REF001*20260101*1200****2~"
        "NM1*P5*2*PAYER*****PI*P01~"
        "NM1*IL*1*SMITH*ALICE****MI*S001~"
        "INS*18*18*001**A~"
        "DMG*D8*19800101*F~"
        "SE*9*0001~"
        "GE*1*1~"
        "IEA*1*000000001~"
    )

    def test_parse_834_success(self, client):
        resp = client.post("/api/v1/edi/parse/834", json={"content": self._SAMPLE_834}, headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction_type"] == "834"
        assert data["data"]["member_count"] == 1

    def test_parse_834_invalid_content(self, client):
        resp = client.post("/api/v1/edi/parse/834", json={"content": "BADEDI"}, headers=_HEADERS)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Parse 999
# ---------------------------------------------------------------------------

class TestParse999Api:
    def test_parse_999_success(self, client):
        from src.x12.generators.gen_999 import generate_999
        from src.x12.generators.schemas import Generate999Request
        req = Generate999Request(**_base999_payload())
        content = generate_999(req)
        resp = client.post("/api/v1/edi/parse/999", json={"content": content}, headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction_type"] == "999"
        assert data["data"]["ack_code"] == "A"
        assert "original_gs_control" in data["data"]

    def test_parse_999_invalid(self, client):
        resp = client.post("/api/v1/edi/parse/999", json={"content": "NOTEDI"}, headers=_HEADERS)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Parse TA1
# ---------------------------------------------------------------------------

class TestParseTA1Api:
    def test_parse_ta1_success(self, client):
        from src.x12.generators.gen_999 import generate_ta1
        from src.x12.generators.schemas import GenerateTA1Request
        req = GenerateTA1Request(**_baseta1_payload())
        content = generate_ta1(req)
        resp = client.post("/api/v1/edi/parse/ta1", json={"content": content}, headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction_type"] == "TA1"
        assert data["data"]["ack_code"] == "A"

    def test_parse_ta1_invalid(self, client):
        resp = client.post("/api/v1/edi/parse/ta1", json={"content": "NOTEDI"}, headers=_HEADERS)
        assert resp.status_code == 422
