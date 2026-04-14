"""Tests for generate API error paths and fallback import branch."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

_MODULE_ROOT = Path(__file__).resolve().parents[2]
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import os
os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

import pytest
from fastapi.testclient import TestClient

TENANT_ID = "11111111-1111-1111-1111-111111111111"


async def _mock_get_session():
    yield None


@pytest.fixture(scope="module")
def client():
    from src.main import create_app
    app = create_app()
    try:
        from shared.db.session import get_session  # type: ignore[import]
        app.dependency_overrides[get_session] = _mock_get_session
    except (ImportError, Exception):
        pass
    return TestClient(app, raise_server_exceptions=False)


def test_generate_835_raises_value_error(client):
    """When generator raises ValueError, API returns 422."""
    with patch("src.api.generate.generate_835", side_effect=ValueError("bad 835")):
        resp = client.post(
            "/api/v1/edi/generate/835",
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
                "implementation_guide": "005010X221A1",
                "payment_date": "20260101",
                "payment_amount": "100.00",
                "credit_debit_flag": "C",
                "payment_method": "ACH",
                "check_eft_number": "EFT001",
                "payer": {"entity_qualifier": "PR", "name": "PAYER"},
                "payee": {"entity_qualifier": "PE", "name": "PAYEE"},
                "trace": {"check_eft_number": "EFT001", "payer_id": "P001"},
                "claims": [],
            },
            headers={"x-tenant-id": TENANT_ID},
        )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"]["code"] == "GENERATION_FAILED"


def test_generate_837p_raises_value_error(client):
    """When 837P generator raises ValueError, API returns 422."""
    with patch("src.api.generate.generate_837p", side_effect=ValueError("bad 837p")):
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
                "claims": [],
            },
            headers={"x-tenant-id": TENANT_ID},
        )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"]["code"] == "GENERATION_FAILED"


def test_generate_api_import_fallback_coverage():
    """Cover the except ImportError branch in generate.py by simulating import failure."""
    # Remove sqlalchemy from sys.modules temporarily to exercise lines 13-17
    sqlalchemy_mod = sys.modules.get("sqlalchemy.ext.asyncio")
    try:
        # Patch the import inside generate module
        with patch.dict("sys.modules", {"sqlalchemy.ext.asyncio": None}):
            import importlib
            import src.api.generate as gen_module
            importlib.reload(gen_module)
            # After reload with failed import, AsyncSession should be None
            assert gen_module.AsyncSession is None
    finally:
        # Restore
        if sqlalchemy_mod is not None:
            sys.modules["sqlalchemy.ext.asyncio"] = sqlalchemy_mod
        import importlib
        import src.api.generate as gen_module
        importlib.reload(gen_module)
