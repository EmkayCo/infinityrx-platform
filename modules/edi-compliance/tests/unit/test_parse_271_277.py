"""Tests for 271 and 277 parsers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.x12.generators.gen_271 import generate_271
from src.x12.generators.gen_277 import generate_277
from src.x12.generators.schemas import Generate271Request, Generate277Request
from src.x12.parsers.parse_271 import Parsed271, Parsed271Benefit, parse_271
from src.x12.parsers.parse_277 import Parsed277, Parsed277ClaimStatus, parse_277

_FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TP_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


# ---------- 271 parser ----------

def _make_271(benefit_info=None, subscriber_dob=None,
               plan_begin=None, plan_end=None, eligibility_status="1") -> str:
    req = Generate271Request(
        tenant_id=_TENANT_ID,
        trading_partner_id=_TP_ID,
        isa_control_number=1,
        gs_control_number=1,
        receiver_id="RECEIVER       ",
        payer_id="PAYER01",
        payer_name="ANTHEM",
        subscriber_id="SUB001",
        subscriber_last_name="HILL",
        subscriber_first_name="MARY",
        subscriber_dob=subscriber_dob,
        plan_begin_date=plan_begin,
        plan_end_date=plan_end,
        eligibility_status=eligibility_status,
        benefit_info=benefit_info or [],
    )
    return generate_271(req, now=_FIXED_NOW)


class TestParse271:
    def test_roundtrip_sender_receiver(self):
        raw = _make_271()
        parsed = parse_271(raw)
        assert parsed.sender_id.strip() == "INFINITYRX"
        assert parsed.receiver_id.strip() == "RECEIVER"

    def test_roundtrip_payer(self):
        raw = _make_271()
        parsed = parse_271(raw)
        assert parsed.payer_name == "ANTHEM"
        assert parsed.payer_id == "PAYER01"

    def test_roundtrip_subscriber(self):
        raw = _make_271()
        parsed = parse_271(raw)
        assert parsed.subscriber_last_name == "HILL"
        assert parsed.subscriber_first_name == "MARY"
        assert parsed.subscriber_id == "SUB001"

    def test_roundtrip_subscriber_dob(self):
        raw = _make_271(subscriber_dob="19800101")
        parsed = parse_271(raw)
        assert parsed.subscriber_dob == "19800101"

    def test_roundtrip_plan_dates(self):
        raw = _make_271(plan_begin="20260101", plan_end="20261231")
        parsed = parse_271(raw)
        assert parsed.plan_begin_date == "20260101"
        assert parsed.plan_end_date == "20261231"

    def test_plan_dates_absent_are_empty(self):
        raw = _make_271()
        parsed = parse_271(raw)
        assert parsed.plan_begin_date == ""
        assert parsed.plan_end_date == ""

    def test_roundtrip_eligibility_status(self):
        raw = _make_271(eligibility_status="6")
        parsed = parse_271(raw)
        assert parsed.eligibility_status == "6"

    def test_roundtrip_benefits(self):
        raw = _make_271(benefit_info=[
            {"eligibility_code": "1", "coverage_level": "IND",
             "service_type_code": "30", "monetary_amount": "500.00"},
        ])
        parsed = parse_271(raw)
        # generator emits 1 base EB + 1 per benefit_info = 2 total
        assert len(parsed.benefits) == 2
        # the extra benefit (from benefit_info) has our monetary_amount
        extra = parsed.benefits[1]
        assert extra.eligibility_code == "1"
        assert extra.coverage_level == "IND"
        assert extra.service_type_code == "30"
        assert extra.monetary_amount == "500.00"

    def test_no_isa_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_271("NOT*VALID~")

    def test_benefit_in_network_field(self):
        raw = _make_271(benefit_info=[
            {"eligibility_code": "1", "coverage_level": "IND", "service_type_code": "30",
             "in_plan_network": "Y"},
        ])
        parsed = parse_271(raw)
        # index 1 is the benefit from benefit_info
        assert parsed.benefits[1].in_plan_network == "Y"

    def test_multiple_benefits(self):
        raw = _make_271(benefit_info=[
            {"eligibility_code": "1", "coverage_level": "IND", "service_type_code": "30"},
            {"eligibility_code": "C", "coverage_level": "IND", "service_type_code": "30",
             "monetary_amount": "20.00"},
        ])
        parsed = parse_271(raw)
        # 1 base + 2 from benefit_info = 3
        assert len(parsed.benefits) == 3

    def test_isa_control_number(self):
        raw = _make_271()
        parsed = parse_271(raw)
        assert parsed.isa_control_number == "000000001"


# ---------- 277 parser ----------

def _make_277(claim_statuses=None) -> str:
    req = Generate277Request(
        tenant_id=_TENANT_ID,
        trading_partner_id=_TP_ID,
        isa_control_number=1,
        gs_control_number=1,
        receiver_id="SUBMITTER      ",
        payer_id="PAYER01",
        payer_name="UHC",
        claim_statuses=claim_statuses or [],
    )
    return generate_277(req, now=_FIXED_NOW)


class TestParse277:
    def test_roundtrip_sender_receiver(self):
        raw = _make_277()
        parsed = parse_277(raw)
        assert parsed.sender_id.strip() == "INFINITYRX"
        assert parsed.receiver_id.strip() == "SUBMITTER"

    def test_roundtrip_payer(self):
        raw = _make_277()
        parsed = parse_277(raw)
        assert parsed.payer_name == "UHC"
        assert parsed.payer_id == "PAYER01"

    def test_no_statuses_empty_list(self):
        raw = _make_277()
        parsed = parse_277(raw)
        assert parsed.claim_statuses == []

    def test_roundtrip_claim_status(self):
        raw = _make_277(claim_statuses=[{
            "subscriber_id": "SUB001",
            "subscriber_last_name": "REED",
            "subscriber_first_name": "TOM",
            "claim_id": "CLM001",
            "provider_npi": "1234567893",
            "provider_name": "CLINIC A",
            "status_category_code": "F1",
            "status_code": "0",
            "date_of_service": "20260101",
            "charge_amount": "300.00",
        }])
        parsed = parse_277(raw)
        assert len(parsed.claim_statuses) == 1
        s = parsed.claim_statuses[0]
        assert s.subscriber_last_name == "REED"
        assert s.subscriber_id == "SUB001"
        assert s.claim_id == "CLM001"
        assert s.status_category_code == "F1"
        assert s.status_code == "0"
        assert s.date_of_service == "20260101"
        assert s.charge_amount == "300.00"

    def test_roundtrip_status_without_info_code(self):
        raw = _make_277(claim_statuses=[{
            "status_category_code": "A0",
        }])
        parsed = parse_277(raw)
        assert parsed.claim_statuses[0].status_category_code == "A0"
        assert parsed.claim_statuses[0].status_code == ""

    def test_multiple_statuses(self):
        raw = _make_277(claim_statuses=[
            {"status_category_code": "F1", "subscriber_id": "S1",
             "claim_id": "C1", "provider_npi": "1234567893"},
            {"status_category_code": "F2", "subscriber_id": "S2",
             "claim_id": "C2", "provider_npi": "1234567893"},
        ])
        parsed = parse_277(raw)
        assert len(parsed.claim_statuses) == 2

    def test_no_isa_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_277("NOT*VALID~")

    def test_isa_control_number_parsed(self):
        raw = _make_277()
        parsed = parse_277(raw)
        assert parsed.isa_control_number == "000000001"

    def test_paid_amount_parsed(self):
        raw = _make_277(claim_statuses=[{
            "status_category_code": "F1",
            "charge_amount": "100.00",
            "paid_amount": "80.00",
        }])
        parsed = parse_277(raw)
        assert parsed.claim_statuses[0].paid_amount == "80.00"
