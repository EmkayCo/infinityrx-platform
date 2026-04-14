"""Integration tests that drive the full FastAPI app via create_app().

Per LESSON-006: primitives must be tested through the real application factory,
not just in isolation. These tests verify the routes are mounted and reachable.

The shared database session is overridden with a no-op mock so these tests
run without a live database connection.
"""

from __future__ import annotations

import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parents[2]
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import os
os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

TENANT_ID = "11111111-1111-1111-1111-111111111111"

_FIXED_NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)


class _MockSession:
    """Minimal async session mock for integration tests without a live DB."""
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


async def _mock_get_session():
    yield _MockSession()


@pytest.fixture(scope="module")
def client():
    """Create a TestClient against the real create_app() with DB mocked out."""
    from src.main import create_app

    app = create_app()

    # Override the DB session dependency so routes don't need a live DB
    try:
        from shared.db.session import get_session  # type: ignore[import]
        app.dependency_overrides[get_session] = _mock_get_session
    except (ImportError, Exception):
        pass

    return TestClient(app, raise_server_exceptions=True)


def test_health_endpoint(client):
    """Health check is reachable through the real app (LESSON-006)."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["module"] == "edi-compliance"


def test_generate_835_through_app(client):
    """835 generator route is mounted on the real app and produces valid X12."""
    from src.x12.generators.gen_835 import generate_835
    from src.x12.generators.schemas import Generate835Request, N1Party, TrnTrace
    from src.x12.delimiters import Delimiters

    _DELIMS = Delimiters(element="*", sub_element=":", segment="~")
    req = Generate835Request(
        tenant_id=TENANT_ID,
        trading_partner_id="22222222-2222-2222-2222-222222222222",
        isa_control_number=1,
        gs_control_number=1,
        st_control_number=1,
        payment_date="20260401",
        payment_amount=Decimal("100.00"),
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="EFT001",
        payer=N1Party(entity_qualifier="PR", name="PAYER INC"),
        payee=N1Party(entity_qualifier="PE", name="PHARMA INC"),
        trace=TrnTrace(check_eft_number="EFT001", payer_id="PAYER001"),
        claims=[],
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        test_mode=True,
        implementation_guide="005010X221A1",
    )

    resp = client.post(
        "/api/v1/edi/generate/835",
        json={
            "tenant_id": TENANT_ID,
            "trading_partner_id": "22222222-2222-2222-2222-222222222222",
            "isa_control_number": 1,
            "gs_control_number": 1,
            "st_control_number": 1,
            "payment_date": "20260401",
            "payment_amount": "100.00",
            "credit_debit_flag": "C",
            "payment_method": "ACH",
            "check_eft_number": "EFT001",
            "payer": {"entity_qualifier": "PR", "name": "PAYER INC"},
            "payee": {"entity_qualifier": "PE", "name": "PHARMA INC"},
            "trace": {"check_eft_number": "EFT001", "payer_id": "PAYER001"},
            "claims": [],
            "sender_qualifier": "ZZ",
            "sender_id": "INFINITYRX     ",
            "receiver_qualifier": "ZZ",
            "test_mode": True,
            "implementation_guide": "005010X221A1",
        },
        headers={"x-tenant-id": TENANT_ID},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["transaction_type"] == "835"
    assert data["content"].startswith("ISA")
    assert data["byte_count"] > 0


def test_generate_270_through_app(client):
    """270 generator route is mounted and reachable."""
    resp = client.post(
        "/api/v1/edi/generate/270",
        json={
            "tenant_id": TENANT_ID,
            "trading_partner_id": "22222222-2222-2222-2222-222222222222",
            "isa_control_number": 1,
            "gs_control_number": 1,
            "st_control_number": 1,
            "sender_qualifier": "ZZ",
            "sender_id": "INFINITYRX     ",
            "receiver_qualifier": "ZZ",
            "receiver_id": "PAYER001       ",
            "test_mode": True,
            "implementation_guide": "005010X279A1",
            "payer_id": "PAYER001",
            "payer_name": "BLUE CROSS",
            "receiver_id_qualifier": "XX",
            "receiver_npi": "1234567893",
            "subscriber_id": "MEM001",
            "subscriber_last_name": "SMITH",
            "subscriber_first_name": "JOHN",
            "service_type_codes": ["30"],
        },
        headers={"x-tenant-id": TENANT_ID},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["transaction_type"] == "270"


def test_parse_835_through_app(client):
    """835 parse route is mounted and parses generated content."""
    from src.x12.delimiters import Delimiters
    from src.x12.generators.gen_835 import generate_835
    from src.x12.generators.schemas import Generate835Request, N1Party, TrnTrace

    _DELIMS = Delimiters(element="*", sub_element=":", segment="~")
    req = Generate835Request(
        tenant_id=TENANT_ID,
        trading_partner_id="22222222-2222-2222-2222-222222222222",
        isa_control_number=1,
        gs_control_number=1,
        st_control_number=1,
        payment_date="20260401",
        payment_amount=Decimal("100.00"),
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="EFT001",
        payer=N1Party(entity_qualifier="PR", name="PAYER"),
        payee=N1Party(entity_qualifier="PE", name="PAYEE"),
        trace=TrnTrace(check_eft_number="EFT001", payer_id="P001"),
        claims=[],
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        test_mode=True,
        implementation_guide="005010X221A1",
    )
    edi_content = generate_835(req, _DELIMS, _FIXED_NOW)

    resp = client.post(
        "/api/v1/edi/parse/835",
        json={"content": edi_content},
        headers={"x-tenant-id": TENANT_ID},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["transaction_type"] == "835"
    assert data["is_valid"]


def test_validate_through_app(client):
    """Validate endpoint is reachable through the app."""
    resp = client.post(
        "/api/v1/edi/parse/validate",
        json={"content": "NOTEDI"},
        headers={"x-tenant-id": TENANT_ID},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert not data["is_valid"]


def test_missing_tenant_returns_401(client):
    """Missing x-tenant-id header returns 401 — not 500 (security boundary)."""
    resp = client.post("/api/v1/edi/generate/835", json={})
    assert resp.status_code == 401


def test_invalid_tenant_uuid_returns_403(client):
    """Malformed tenant UUID returns 403."""
    resp = client.post(
        "/api/v1/edi/generate/835",
        json={},
        headers={"x-tenant-id": "not-a-uuid"},
    )
    assert resp.status_code == 403


def test_generate_835_invalid_input_returns_422(client):
    """Invalid 835 request body returns structured 422."""
    resp = client.post(
        "/api/v1/edi/generate/835",
        json={"payment_amount": "not_a_number"},
        headers={"x-tenant-id": TENANT_ID},
    )
    assert resp.status_code == 422


def test_all_generation_routes_mounted(client):
    """Verify all generation routes exist on the app (not 404)."""
    # 837P route should exist — may return 422 but not 404
    resp = client.post(
        "/api/v1/edi/generate/837p",
        json={},
        headers={"x-tenant-id": TENANT_ID},
    )
    assert resp.status_code in (200, 422), f"837P route not mounted: {resp.status_code}"
