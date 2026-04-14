"""Additional integration route tests for coverage of compliance and trading partner APIs."""

from __future__ import annotations

import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parents[2]
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import os
os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

import pytest
from fastapi.testclient import TestClient

from tests.conftest import _FAKE_USER_FOR_TESTS  # noqa: E402

TENANT_ID = "11111111-1111-1111-1111-111111111111"


async def _mock_get_session():
    yield None


@pytest.fixture(scope="module")
def client():
    from src.main import create_app
    from shared.auth.dependencies import get_current_user
    app = create_app()
    try:
        from shared.db.session import get_session  # type: ignore[import]
        app.dependency_overrides[get_session] = _mock_get_session
    except (ImportError, Exception):
        pass
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER_FOR_TESTS
    return TestClient(app, raise_server_exceptions=False)


def test_compliance_dashboard_endpoint_exists(client):
    resp = client.get(
        "/api/v1/edi/compliance",
        headers={"x-tenant-id": TENANT_ID},
    )
    # Will fail with 500 (no real DB) but route must be mounted (not 404)
    assert resp.status_code in (200, 422, 500)


def test_trading_partners_list_endpoint_exists(client):
    resp = client.get(
        "/api/v1/edi/trading-partners",
        headers={"x-tenant-id": TENANT_ID},
    )
    assert resp.status_code in (200, 422, 500)


def test_generate_837p_through_app(client):
    resp = client.post(
        "/api/v1/edi/generate/837p",
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
            "implementation_guide": "005010X222A2",
            "billing_provider_npi": "1234567893",
            "billing_provider_name": "TEST PROVIDER",
            "subscriber_id": "MEM001",
            "subscriber_last_name": "DOE",
            "subscriber_first_name": "JANE",
            "subscriber_dob": "19800101",
            "subscriber_gender": "F",
            "payer_id": "PAYER001",
            "payer_name": "TEST PAYER",
            "claims": [
                {
                    "claim_id": "CLM001",
                    "charge_amount": "100.00",
                    "facility_code": "11",
                    "claim_frequency": "1",
                    "service_lines": [
                        {
                            "procedure_code": "99213",
                            "charge_amount": "100.00",
                            "units": "1",
                            "place_of_service": "11",
                            "date_of_service": "20260101",
                        }
                    ],
                }
            ],
        },
        headers={"x-tenant-id": TENANT_ID},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["transaction_type"] == "837P"
    assert data["content"].startswith("ISA")
