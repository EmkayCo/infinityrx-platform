"""Tests for 837D dental claim generator."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.x12.generators.gen_837d import generate_837d
from src.x12.generators.schemas import Generate837DRequest

_FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TP_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


_MINIMAL_CLAIM = {
    "claim_id": "DCLM001",
    "charge_amount": "100.00",
    "service_lines": [{"procedure_code": "D0120", "charge_amount": "100.00"}],
}


def _base_req(**kwargs) -> Generate837DRequest:
    defaults = dict(
        tenant_id=_TENANT_ID,
        trading_partner_id=_TP_ID,
        isa_control_number=1,
        gs_control_number=1,
        st_control_number=1,
        receiver_id="RECEIVER       ",
        billing_provider_npi="1234567893",
        billing_provider_name="SMILE DENTAL",
        subscriber_id="SUB001",
        subscriber_last_name="DOE",
        subscriber_first_name="JANE",
        subscriber_dob="19800601",
        subscriber_gender="F",
        payer_id="DPAYER01",
        payer_name="DENTAL PLAN",
        claims=[_MINIMAL_CLAIM],
        test_mode=True,
    )
    defaults.update(kwargs)
    return Generate837DRequest(**defaults)


class TestGenerate837D:
    def test_produces_nonempty_string(self):
        req = _base_req()
        result = generate_837d(req, now=_FIXED_NOW)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_837_transaction_type(self):
        req = _base_req()
        result = generate_837d(req, now=_FIXED_NOW)
        assert "ST*837*" in result

    def test_contains_dental_guide(self):
        req = _base_req()
        result = generate_837d(req, now=_FIXED_NOW)
        assert "005010X224A3" in result

    def test_contains_billing_npi(self):
        req = _base_req()
        result = generate_837d(req, now=_FIXED_NOW)
        assert "1234567893" in result

    def test_contains_subscriber_name(self):
        req = _base_req()
        result = generate_837d(req, now=_FIXED_NOW)
        assert "DOE" in result

    def test_with_billing_provider_ein(self):
        req = _base_req(billing_provider_ein="987654321")
        result = generate_837d(req, now=_FIXED_NOW)
        assert "EI*987654321" in result

    def test_dental_claim_with_service_lines(self):
        req = _base_req(claims=[{
            "claim_id": "DCLM001",
            "charge_amount": "200.00",
            "oral_cavity_code": "00",
            "service_lines": [
                {
                    "procedure_code": "D0120",
                    "charge_amount": "75.00",
                    "tooth_number": "03",
                    "tooth_surface": "M",
                    "date_of_service": "20260101",
                },
            ],
        }])
        result = generate_837d(req, now=_FIXED_NOW)
        assert "CLM*DCLM001" in result
        assert "SV3*AD:D0120" in result
        assert "DTP*472" in result

    def test_service_line_without_date_no_dtp(self):
        req = _base_req(claims=[{
            "claim_id": "DCLM002",
            "charge_amount": "100.00",
            "service_lines": [
                {"procedure_code": "D0120", "charge_amount": "100.00"}
            ],
        }])
        result = generate_837d(req, now=_FIXED_NOW)
        assert "SV3" in result

    def test_claim_without_service_lines(self):
        req = _base_req(claims=[{
            "claim_id": "DCLM003",
            "charge_amount": "50.00",
        }])
        result = generate_837d(req, now=_FIXED_NOW)
        assert "CLM*DCLM003" in result

    def test_ends_with_iea(self):
        req = _base_req()
        result = generate_837d(req, now=_FIXED_NOW)
        assert "IEA*" in result

    def test_production_mode(self):
        req = _base_req(test_mode=False)
        result = generate_837d(req, now=_FIXED_NOW)
        assert "*P*" in result

    def test_dental_insurance_type_di_in_sbr(self):
        req = _base_req()
        result = generate_837d(req, now=_FIXED_NOW)
        assert "DI" in result


class TestGenerate837DValidation:
    def test_bad_npi_raises_value_error(self):
        req = _base_req(
            billing_provider_npi="9999999999",
            claims=[{
                "claim_id": "BAD",
                "charge_amount": "100.00",
                "service_lines": [{"procedure_code": "D0120", "charge_amount": "100.00"}],
            }],
        )
        with pytest.raises(ValueError, match="837D failed validation"):
            generate_837d(req, now=_FIXED_NOW)
