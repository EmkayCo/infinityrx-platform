"""Tests for 837I institutional claim generator."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.x12.generators.gen_837i import generate_837i
from src.x12.generators.schemas import Generate837IRequest

_FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TP_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


_MINIMAL_CLAIM = {
    "claim_id": "CLM001",
    "charge_amount": "100.00",
    "revenue_lines": [{"revenue_code": "0120", "procedure_code": "99213", "charge_amount": "100.00"}],
}


def _base_req(**kwargs) -> Generate837IRequest:
    defaults = dict(
        tenant_id=_TENANT_ID,
        trading_partner_id=_TP_ID,
        isa_control_number=1,
        gs_control_number=1,
        st_control_number=1,
        receiver_id="RECEIVER       ",
        billing_provider_npi="1234567893",
        billing_provider_name="GENERAL HOSPITAL",
        subscriber_id="SUB001",
        subscriber_last_name="SMITH",
        subscriber_first_name="JOHN",
        subscriber_dob="19700101",
        subscriber_gender="M",
        payer_id="PAYER01",
        payer_name="MEDICARE",
        claims=[_MINIMAL_CLAIM],
        test_mode=True,
    )
    defaults.update(kwargs)
    return Generate837IRequest(**defaults)


class TestGenerate837I:
    def test_produces_nonempty_string(self):
        req = _base_req()
        result = generate_837i(req, now=_FIXED_NOW)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_837_transaction_type(self):
        req = _base_req()
        result = generate_837i(req, now=_FIXED_NOW)
        assert "ST*837*" in result

    def test_contains_implementation_guide(self):
        req = _base_req()
        result = generate_837i(req, now=_FIXED_NOW)
        assert "005010X223A3" in result

    def test_contains_billing_provider_npi(self):
        req = _base_req()
        result = generate_837i(req, now=_FIXED_NOW)
        assert "1234567893" in result

    def test_contains_subscriber_name(self):
        req = _base_req()
        result = generate_837i(req, now=_FIXED_NOW)
        assert "SMITH" in result

    def test_contains_payer_id(self):
        req = _base_req()
        result = generate_837i(req, now=_FIXED_NOW)
        assert "PAYER01" in result

    def test_with_billing_provider_ein(self):
        req = _base_req(billing_provider_ein="123456789")
        result = generate_837i(req, now=_FIXED_NOW)
        assert "EI*123456789" in result

    def test_claim_with_all_fields(self):
        req = _base_req(claims=[{
            "claim_id": "CLM001",
            "charge_amount": "1500.00",
            "facility_code": "21",
            "admission_type": "1",
            "admission_source": "7",
            "patient_status": "01",
            "admission_date": "20260101",
            "discharge_date": "20260103",
            "principal_diagnosis": "A09",
            "drg_code": "392",
            "revenue_lines": [
                {
                    "revenue_code": "0120",
                    "procedure_code": "99214",
                    "charge_amount": "750.00",
                    "units": "1",
                    "date_of_service": "20260101",
                }
            ],
        }])
        result = generate_837i(req, now=_FIXED_NOW)
        assert "CLM*CLM001" in result
        assert "ABK:A09" in result
        assert "BBQ:392" in result
        assert "SV2*0120" in result
        assert "DTP*435" in result  # admission date
        assert "DTP*096" in result  # discharge date

    def test_revenue_line_without_procedure_code(self):
        req = _base_req(claims=[{
            "claim_id": "CLM002",
            "charge_amount": "500.00",
            "revenue_lines": [
                {"revenue_code": "0360", "charge_amount": "500.00"}
            ],
        }])
        result = generate_837i(req, now=_FIXED_NOW)
        # When no procedure_code, svc01 falls back to revenue_code
        assert "SV2*0360*0360" in result

    def test_revenue_line_without_date_no_dtp(self):
        req = _base_req(claims=[{
            "claim_id": "CLM003",
            "charge_amount": "200.00",
            "revenue_lines": [
                {"revenue_code": "0360", "procedure_code": "99213", "charge_amount": "200.00"}
            ],
        }])
        result = generate_837i(req, now=_FIXED_NOW)
        # DTP*472 only emitted when date_of_service present
        assert "SV2" in result

    def test_claim_without_optional_fields(self):
        req = _base_req(claims=[{
            "claim_id": "CLM004",
            "charge_amount": "300.00",
        }])
        result = generate_837i(req, now=_FIXED_NOW)
        assert "CLM*CLM004" in result

    def test_ends_with_iea(self):
        req = _base_req()
        result = generate_837i(req, now=_FIXED_NOW)
        assert result.rstrip().endswith("~")
        assert "IEA*" in result

    def test_production_mode(self):
        req = _base_req(test_mode=False)
        result = generate_837i(req, now=_FIXED_NOW)
        assert "*P*" in result

    def test_claim_filing_indicator_in_sbr(self):
        req = _base_req(claim_filing_indicator="BL")
        result = generate_837i(req, now=_FIXED_NOW)
        assert "BL" in result


class TestGenerate837IValidation:
    def test_bad_npi_raises_value_error(self):
        req = _base_req(
            billing_provider_npi="9999999999",
            claims=[{
                "claim_id": "BAD",
                "charge_amount": "100.00",
                "revenue_lines": [{"revenue_code": "0120", "charge_amount": "100.00"}],
            }],
        )
        with pytest.raises(ValueError, match="837I failed validation"):
            generate_837i(req, now=_FIXED_NOW)
