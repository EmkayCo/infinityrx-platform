"""Tests for 271, 276, and 277 generators."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.x12.generators.gen_271 import generate_271
from src.x12.generators.gen_276 import generate_276
from src.x12.generators.gen_277 import generate_277
from src.x12.generators.schemas import (
    Generate271Request,
    Generate276Request,
    Generate277Request,
)

_FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TP_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


# ---------- 271 ----------

class TestGenerate271:
    def _req(self, **kwargs) -> Generate271Request:
        defaults = dict(
            tenant_id=_TENANT_ID,
            trading_partner_id=_TP_ID,
            isa_control_number=1,
            gs_control_number=1,
            st_control_number=1,
            receiver_id="PAYER          ",
            payer_id="PAYER01",
            payer_name="AETNA",
            subscriber_id="SUB001",
            subscriber_last_name="JONES",
            subscriber_first_name="ALICE",
        )
        defaults.update(kwargs)
        return Generate271Request(**defaults)

    def test_produces_output(self):
        result = generate_271(self._req(), now=_FIXED_NOW)
        assert len(result) > 0

    def test_contains_271_st_segment(self):
        result = generate_271(self._req(), now=_FIXED_NOW)
        assert "ST*271*" in result

    def test_contains_isa_and_iea(self):
        result = generate_271(self._req(), now=_FIXED_NOW)
        assert "ISA*" in result
        assert "IEA*" in result

    def test_contains_payer_name(self):
        result = generate_271(self._req(), now=_FIXED_NOW)
        assert "AETNA" in result

    def test_contains_subscriber_name(self):
        result = generate_271(self._req(), now=_FIXED_NOW)
        assert "JONES" in result

    def test_contains_subscriber_id(self):
        result = generate_271(self._req(), now=_FIXED_NOW)
        assert "SUB001" in result

    def test_with_subscriber_dob(self):
        result = generate_271(self._req(subscriber_dob="19800101"), now=_FIXED_NOW)
        assert "DMG*D8*19800101" in result

    def test_without_subscriber_dob(self):
        result = generate_271(self._req(subscriber_dob=None), now=_FIXED_NOW)
        assert "ST*271*" in result  # doesn't crash

    def test_with_plan_dates(self):
        result = generate_271(
            self._req(plan_begin_date="20260101", plan_end_date="20261231"),
            now=_FIXED_NOW,
        )
        assert "DTP*346*D8*20260101" in result
        assert "DTP*347*D8*20261231" in result

    def test_without_plan_dates(self):
        result = generate_271(self._req(), now=_FIXED_NOW)
        assert "ST*271*" in result

    def test_with_benefit_info(self):
        result = generate_271(
            self._req(benefit_info=[
                {"eligibility_code": "1", "coverage_level": "IND", "service_type_code": "30",
                 "monetary_amount": "1000.00"},
            ]),
            now=_FIXED_NOW,
        )
        assert "EB*1*IND*30" in result

    def test_with_original_270_control(self):
        result = generate_271(
            self._req(original_270_control="000000042"),
            now=_FIXED_NOW,
        )
        assert "000000042" in result

    def test_with_inactive_eligibility_status(self):
        result = generate_271(self._req(eligibility_status="6"), now=_FIXED_NOW)
        assert "6" in result

    def test_production_mode(self):
        result = generate_271(self._req(test_mode=False), now=_FIXED_NOW)
        assert "*P*" in result


# ---------- 276 ----------

class TestGenerate276:
    def _req(self, **kwargs) -> Generate276Request:
        defaults = dict(
            tenant_id=_TENANT_ID,
            trading_partner_id=_TP_ID,
            isa_control_number=1,
            gs_control_number=1,
            st_control_number=1,
            receiver_id="PAYER          ",
            payer_id="PAYER01",
            payer_name="CIGNA",
            provider_npi="1234567893",
            provider_name="BEST CLINIC",
        )
        defaults.update(kwargs)
        return Generate276Request(**defaults)

    def test_produces_output(self):
        result = generate_276(self._req(), now=_FIXED_NOW)
        assert len(result) > 0

    def test_contains_276_st_segment(self):
        result = generate_276(self._req(), now=_FIXED_NOW)
        assert "ST*276*" in result

    def test_contains_isa_and_iea(self):
        result = generate_276(self._req(), now=_FIXED_NOW)
        assert "ISA*" in result
        assert "IEA*" in result

    def test_contains_payer_name(self):
        result = generate_276(self._req(), now=_FIXED_NOW)
        assert "CIGNA" in result

    def test_contains_provider_npi(self):
        result = generate_276(self._req(), now=_FIXED_NOW)
        assert "1234567893" in result

    def test_with_claim_inquiries(self):
        result = generate_276(
            self._req(claim_inquiries=[
                {
                    "subscriber_id": "SUB001",
                    "subscriber_last_name": "SMITH",
                    "subscriber_first_name": "BOB",
                    "claim_id": "CLM001",
                    "date_of_service": "20260101",
                },
            ]),
            now=_FIXED_NOW,
        )
        assert "SMITH" in result
        assert "REF*1K*CLM001" in result
        assert "DTP*472*D8*20260101" in result

    def test_inquiry_without_dos(self):
        result = generate_276(
            self._req(claim_inquiries=[{
                "subscriber_id": "SUB002",
                "subscriber_last_name": "DOE",
                "subscriber_first_name": "JIM",
            }]),
            now=_FIXED_NOW,
        )
        assert "DOE" in result

    def test_inquiry_without_claim_id(self):
        result = generate_276(
            self._req(claim_inquiries=[{
                "subscriber_id": "SUB003",
                "date_of_service": "20260115",
            }]),
            now=_FIXED_NOW,
        )
        assert "DTP*472" in result

    def test_production_mode(self):
        result = generate_276(self._req(test_mode=False), now=_FIXED_NOW)
        assert "*P*" in result


# ---------- 277 ----------

class TestGenerate277:
    def _req(self, **kwargs) -> Generate277Request:
        defaults = dict(
            tenant_id=_TENANT_ID,
            trading_partner_id=_TP_ID,
            isa_control_number=1,
            gs_control_number=1,
            st_control_number=1,
            receiver_id="SUBMITTER      ",
            payer_id="PAYER01",
            payer_name="HUMANA",
        )
        defaults.update(kwargs)
        return Generate277Request(**defaults)

    def test_produces_output(self):
        result = generate_277(self._req(), now=_FIXED_NOW)
        assert len(result) > 0

    def test_contains_277_st_segment(self):
        result = generate_277(self._req(), now=_FIXED_NOW)
        assert "ST*277*" in result

    def test_contains_isa_and_iea(self):
        result = generate_277(self._req(), now=_FIXED_NOW)
        assert "ISA*" in result
        assert "IEA*" in result

    def test_contains_payer_name(self):
        result = generate_277(self._req(), now=_FIXED_NOW)
        assert "HUMANA" in result

    def test_with_claim_status(self):
        result = generate_277(
            self._req(claim_statuses=[{
                "subscriber_id": "SUB001",
                "subscriber_last_name": "LEE",
                "subscriber_first_name": "KIM",
                "claim_id": "CLM001",
                "provider_npi": "1234567893",
                "provider_name": "CLINIC X",
                "status_category_code": "F1",
                "status_code": "0",
                "date_of_service": "20260101",
                "charge_amount": "250.00",
                "paid_amount": "200.00",
            }]),
            now=_FIXED_NOW,
        )
        assert "LEE" in result
        assert "REF*1K*CLM001" in result
        assert "STC*F1:0" in result
        assert "DTP*472*D8*20260101" in result

    def test_status_without_status_code_no_colon(self):
        result = generate_277(
            self._req(claim_statuses=[{
                "subscriber_id": "SUB002",
                "status_category_code": "A0",
            }]),
            now=_FIXED_NOW,
        )
        assert "STC*A0*" in result

    def test_status_without_dos(self):
        result = generate_277(
            self._req(claim_statuses=[{
                "subscriber_id": "SUB003",
                "status_category_code": "P1",
            }]),
            now=_FIXED_NOW,
        )
        assert "STC*P1*" in result

    def test_status_without_claim_id(self):
        result = generate_277(
            self._req(claim_statuses=[{
                "status_category_code": "A6",
                "status_code": "512",
                "date_of_service": "20260101",
            }]),
            now=_FIXED_NOW,
        )
        assert "STC*A6:512*" in result

    def test_multiple_statuses(self):
        result = generate_277(
            self._req(claim_statuses=[
                {"subscriber_id": "SUB001", "status_category_code": "F1"},
                {"subscriber_id": "SUB002", "status_category_code": "F2"},
            ]),
            now=_FIXED_NOW,
        )
        assert result.count("STC*") == 2

    def test_production_mode(self):
        result = generate_277(self._req(test_mode=False), now=_FIXED_NOW)
        assert "*P*" in result

    def test_charge_without_paid_amount(self):
        result = generate_277(
            self._req(claim_statuses=[{
                "status_category_code": "F1",
                "charge_amount": "100.00",
            }]),
            now=_FIXED_NOW,
        )
        assert "STC*F1*" in result

    def test_paid_amount_without_charge(self):
        result = generate_277(
            self._req(claim_statuses=[{
                "status_category_code": "F1",
                "paid_amount": "90.00",
            }]),
            now=_FIXED_NOW,
        )
        assert "STC*F1*" in result
