"""Tests for 278 Prior Authorization generator and parser."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.x12.generators.gen_278 import generate_278
from src.x12.generators.schemas import Generate278Request
from src.x12.parsers.parse_278 import Parsed278, Parsed278ServiceReview, parse_278

_FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
_T = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TP = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _base_req(**kwargs) -> Generate278Request:
    defaults = dict(
        tenant_id=_T, trading_partner_id=_TP,
        isa_control_number=1, gs_control_number=1,
        receiver_id="PAYER          ",
        payer_id="PAYER01", payer_name="AETNA",
        provider_npi="1234567893", provider_name="CLINIC A",
        subscriber_id="SUB001", subscriber_last_name="JONES", subscriber_first_name="PAUL",
        service_reviews=[],
    )
    defaults.update(kwargs)
    return Generate278Request(**defaults)


class TestGenerate278:
    def test_produces_output(self):
        result = generate_278(_base_req(), now=_FIXED_NOW)
        assert len(result) > 0

    def test_contains_278_st_segment(self):
        result = generate_278(_base_req(), now=_FIXED_NOW)
        assert "ST*278*" in result

    def test_contains_isa_and_iea(self):
        result = generate_278(_base_req(), now=_FIXED_NOW)
        assert "ISA*" in result
        assert "IEA*" in result

    def test_request_uses_bht_purpose_13(self):
        result = generate_278(_base_req(is_response=False), now=_FIXED_NOW)
        assert "BHT*0007*13" in result

    def test_response_uses_bht_purpose_11(self):
        result = generate_278(_base_req(is_response=True), now=_FIXED_NOW)
        assert "BHT*0007*11" in result

    def test_contains_payer_name(self):
        result = generate_278(_base_req(), now=_FIXED_NOW)
        assert "AETNA" in result

    def test_contains_provider_npi(self):
        result = generate_278(_base_req(), now=_FIXED_NOW)
        assert "1234567893" in result

    def test_contains_subscriber_name(self):
        result = generate_278(_base_req(), now=_FIXED_NOW)
        assert "JONES" in result

    def test_with_subscriber_dob(self):
        result = generate_278(_base_req(subscriber_dob="19800101"), now=_FIXED_NOW)
        assert "DMG*D8*19800101" in result

    def test_without_subscriber_dob(self):
        result = generate_278(_base_req(), now=_FIXED_NOW)
        assert "ST*278*" in result

    def test_service_review_with_all_fields(self):
        result = generate_278(_base_req(service_reviews=[{
            "review_type": "HS",
            "service_type_code": "1",
            "procedure_code": "99213",
            "diagnosis_code": "A09",
            "units": 5,
            "from_date": "20260101",
            "to_date": "20260131",
        }]), now=_FIXED_NOW)
        assert "BJ:99213" in result
        assert "BK:A09" in result
        assert "DTP*472*D8*20260101" in result
        assert "DTP*473*D8*20260131" in result
        assert "QTY*VS*5" in result

    def test_service_review_without_procedure_code(self):
        result = generate_278(_base_req(service_reviews=[{
            "review_type": "HS",
            "service_type_code": "1",
        }]), now=_FIXED_NOW)
        assert "ST*278*" in result

    def test_response_with_auth_number(self):
        result = generate_278(_base_req(is_response=True, service_reviews=[{
            "review_type": "HS",
            "service_type_code": "1",
            "authorization_number": "AUTH123",
        }]), now=_FIXED_NOW)
        assert "REF*BB*AUTH123" in result

    def test_response_with_decision_no_auth(self):
        result = generate_278(_base_req(is_response=True, service_reviews=[{
            "review_type": "HS",
            "service_type_code": "1",
            "decision": "A3",
        }]), now=_FIXED_NOW)
        assert "HSD*" in result

    def test_production_mode(self):
        result = generate_278(_base_req(test_mode=False), now=_FIXED_NOW)
        assert "*P*" in result

    def test_now_none_uses_current_time(self):
        result = generate_278(_base_req())
        assert "ST*278*" in result

    def test_gs_functional_id_um(self):
        result = generate_278(_base_req(), now=_FIXED_NOW)
        assert "GS*UM*" in result


class TestParse278:
    def _make_raw(self, **kwargs) -> str:
        return generate_278(_base_req(**kwargs), now=_FIXED_NOW)

    def test_roundtrip_sender_receiver(self):
        raw = self._make_raw()
        p = parse_278(raw)
        assert p.sender_id.strip() == "INFINITYRX"
        assert p.receiver_id.strip() == "PAYER"

    def test_roundtrip_payer(self):
        raw = self._make_raw()
        p = parse_278(raw)
        assert p.payer_name == "AETNA"
        assert p.payer_id == "PAYER01"

    def test_roundtrip_provider(self):
        raw = self._make_raw()
        p = parse_278(raw)
        assert p.provider_npi == "1234567893"
        assert p.provider_name == "CLINIC A"

    def test_roundtrip_subscriber(self):
        raw = self._make_raw()
        p = parse_278(raw)
        assert p.subscriber_last_name == "JONES"
        assert p.subscriber_id == "SUB001"

    def test_roundtrip_is_request(self):
        raw = self._make_raw(is_response=False)
        p = parse_278(raw)
        assert p.is_response is False

    def test_roundtrip_is_response(self):
        raw = self._make_raw(is_response=True)
        p = parse_278(raw)
        assert p.is_response is True

    def test_roundtrip_subscriber_dob(self):
        raw = self._make_raw(subscriber_dob="19751230")
        p = parse_278(raw)
        assert p.subscriber_dob == "19751230"

    def test_roundtrip_service_review(self):
        raw = self._make_raw(service_reviews=[{
            "review_type": "HS",
            "service_type_code": "1",
            "procedure_code": "99213",
            "diagnosis_code": "A09",
            "units": 3,
            "from_date": "20260101",
        }])
        p = parse_278(raw)
        assert len(p.service_reviews) == 1
        r = p.service_reviews[0]
        assert r.review_type == "HS"
        assert r.procedure_code == "99213"
        assert r.diagnosis_code == "A09"
        assert r.from_date == "20260101"

    def test_no_service_reviews_empty_list(self):
        raw = self._make_raw()
        p = parse_278(raw)
        assert p.service_reviews == []

    def test_no_isa_raises(self):
        from unittest.mock import patch
        raw = self._make_raw()
        with patch("src.x12.parsers.parse_278.parse_segments", return_value=[["GS", "UM"]]):
            with pytest.raises(ValueError, match="No ISA"):
                parse_278(raw)

    def test_response_with_auth_number(self):
        raw = self._make_raw(is_response=True, service_reviews=[{
            "review_type": "HS",
            "service_type_code": "1",
            "authorization_number": "AUTH999",
        }])
        p = parse_278(raw)
        assert p.service_reviews[0].authorization_number == "AUTH999"

    def test_response_with_decision(self):
        raw = self._make_raw(is_response=True, service_reviews=[{
            "review_type": "HS",
            "service_type_code": "1",
            "decision": "A3",
        }])
        p = parse_278(raw)
        assert p.service_reviews[0].decision == "A3"
