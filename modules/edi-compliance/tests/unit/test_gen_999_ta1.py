"""Tests for 999 and TA1 generators and parsers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.x12.generators.gen_999 import generate_999, generate_ta1
from src.x12.generators.schemas import Generate999Request, GenerateTA1Request
from src.x12.parsers.parse_999 import Parsed999, ParsedTA1, parse_999, parse_ta1

_FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
_T = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TP = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _req999(**kwargs) -> Generate999Request:
    defaults = dict(
        tenant_id=_T, trading_partner_id=_TP,
        isa_control_number=2, gs_control_number=2,
        receiver_id="SUBMITTER      ",
        original_isa_control=1, original_gs_control=1,
        original_transaction_type="837",
        ack_code="A",
    )
    defaults.update(kwargs)
    return Generate999Request(**defaults)


def _reqta1(**kwargs) -> GenerateTA1Request:
    defaults = dict(
        tenant_id=_T, trading_partner_id=_TP,
        isa_control_number=3, gs_control_number=3,
        receiver_id="RECEIVER       ",
        ack_control_number=1,
        ack_date="260101",
        ack_time="1200",
        ack_code="A",
        error_code="000",
    )
    defaults.update(kwargs)
    return GenerateTA1Request(**defaults)


class TestGenerate999:
    def test_produces_output(self):
        result = generate_999(_req999(), now=_FIXED_NOW)
        assert len(result) > 0

    def test_contains_999_st_segment(self):
        result = generate_999(_req999(), now=_FIXED_NOW)
        assert "ST*999*" in result

    def test_contains_isa_and_iea(self):
        result = generate_999(_req999(), now=_FIXED_NOW)
        assert "ISA*" in result
        assert "IEA*" in result

    def test_contains_ak1_with_transaction_type(self):
        result = generate_999(_req999(), now=_FIXED_NOW)
        assert "AK1*837*" in result

    def test_contains_ik5_with_ack_code(self):
        result = generate_999(_req999(), now=_FIXED_NOW)
        assert "IK5*A~" in result

    def test_contains_ak9(self):
        result = generate_999(_req999(), now=_FIXED_NOW)
        assert "AK9*A*" in result

    def test_gs_functional_id_fa(self):
        result = generate_999(_req999(), now=_FIXED_NOW)
        assert "GS*FA*" in result

    def test_rejected_ack_code(self):
        result = generate_999(_req999(ack_code="R"), now=_FIXED_NOW)
        assert "IK5*R~" in result

    def test_error_codes_produce_ctx_segments(self):
        result = generate_999(_req999(error_codes=["I6", "I7"]), now=_FIXED_NOW)
        assert "CTX*I6~" in result
        assert "CTX*I7~" in result

    def test_production_mode(self):
        result = generate_999(_req999(test_mode=False), now=_FIXED_NOW)
        assert "*P*" in result

    def test_now_none_uses_current_time(self):
        result = generate_999(_req999())
        assert "ST*999*" in result

    def test_ak9_accepted_count_1_when_accepted(self):
        result = generate_999(_req999(ack_code="A"), now=_FIXED_NOW)
        assert "AK9*A*1*1*1" in result

    def test_ak9_accepted_count_0_when_rejected(self):
        result = generate_999(_req999(ack_code="R"), now=_FIXED_NOW)
        assert "AK9*R*1*1*0" in result


class TestParse999:
    def test_roundtrip_ack_code_accepted(self):
        raw = generate_999(_req999(), now=_FIXED_NOW)
        p = parse_999(raw)
        assert p.ack_code == "A"

    def test_roundtrip_ack_code_rejected(self):
        raw = generate_999(_req999(ack_code="R"), now=_FIXED_NOW)
        p = parse_999(raw)
        assert p.ack_code == "R"

    def test_roundtrip_original_transaction_type(self):
        raw = generate_999(_req999(), now=_FIXED_NOW)
        p = parse_999(raw)
        assert p.original_transaction_type == "837"

    def test_roundtrip_original_gs_control(self):
        raw = generate_999(_req999(), now=_FIXED_NOW)
        p = parse_999(raw)
        assert p.original_gs_control == "1"

    def test_roundtrip_error_codes(self):
        raw = generate_999(_req999(error_codes=["I5", "I6"]), now=_FIXED_NOW)
        p = parse_999(raw)
        assert "I5" in p.error_codes
        assert "I6" in p.error_codes

    def test_no_error_codes_empty(self):
        raw = generate_999(_req999(), now=_FIXED_NOW)
        p = parse_999(raw)
        assert p.error_codes == []

    def test_no_isa_raises(self):
        from unittest.mock import patch
        raw = generate_999(_req999(), now=_FIXED_NOW)
        with patch("src.x12.parsers.parse_999.parse_segments", return_value=[["GS", "FA"]]):
            with pytest.raises(ValueError, match="No ISA"):
                parse_999(raw)

    def test_sender_receiver_ids(self):
        raw = generate_999(_req999(), now=_FIXED_NOW)
        p = parse_999(raw)
        assert p.sender_id.strip() == "INFINITYRX"


class TestGenerateTA1:
    def test_produces_output(self):
        result = generate_ta1(_reqta1(), now=_FIXED_NOW)
        assert len(result) > 0

    def test_contains_isa_and_iea(self):
        result = generate_ta1(_reqta1(), now=_FIXED_NOW)
        assert "ISA*" in result
        assert "IEA*" in result

    def test_contains_ta1_segment(self):
        result = generate_ta1(_reqta1(), now=_FIXED_NOW)
        assert "TA1*" in result

    def test_ta1_contains_ack_code(self):
        result = generate_ta1(_reqta1(), now=_FIXED_NOW)
        assert "*A*" in result

    def test_ta1_error_code(self):
        result = generate_ta1(_reqta1(error_code="022"), now=_FIXED_NOW)
        assert "*022~" in result

    def test_ta1_rejected(self):
        result = generate_ta1(_reqta1(ack_code="R", error_code="022"), now=_FIXED_NOW)
        assert "*R*" in result

    def test_no_gs_ge_in_ta1(self):
        result = generate_ta1(_reqta1(), now=_FIXED_NOW)
        assert "GS*" not in result
        assert "GE*" not in result

    def test_production_mode(self):
        result = generate_ta1(_reqta1(test_mode=False), now=_FIXED_NOW)
        assert "*P*" in result

    def test_now_none_uses_current_time(self):
        result = generate_ta1(_reqta1())
        assert "TA1*" in result


class TestParseTA1:
    def test_roundtrip_ack_code(self):
        raw = generate_ta1(_reqta1(), now=_FIXED_NOW)
        p = parse_ta1(raw)
        assert p.ack_code == "A"

    def test_roundtrip_error_code(self):
        raw = generate_ta1(_reqta1(), now=_FIXED_NOW)
        p = parse_ta1(raw)
        assert p.error_code == "000"

    def test_roundtrip_ack_control(self):
        raw = generate_ta1(_reqta1(ack_control_number=42), now=_FIXED_NOW)
        p = parse_ta1(raw)
        assert p.ack_control_number.lstrip("0") == "42"

    def test_roundtrip_date_time(self):
        raw = generate_ta1(_reqta1(ack_date="260115", ack_time="0930"), now=_FIXED_NOW)
        p = parse_ta1(raw)
        assert p.ack_date == "260115"
        assert p.ack_time == "0930"

    def test_no_isa_raises(self):
        from unittest.mock import patch
        raw = generate_ta1(_reqta1(), now=_FIXED_NOW)
        with patch("src.x12.parsers.parse_999.parse_segments", return_value=[["TA1", "000000001"]]):
            with pytest.raises(ValueError, match="No ISA"):
                parse_ta1(raw)

    def test_no_ta1_raises(self):
        from unittest.mock import patch
        raw = generate_ta1(_reqta1(), now=_FIXED_NOW)
        with patch("src.x12.parsers.parse_999.parse_segments", return_value=[
            ["ISA", "", "", "", "", "", "SENDER         ", "", "RECEIVER       ",
             "", "", "^", "00501", "000000003", "0", "T", ":"],
            ["IEA", "0", "000000003"],
        ]):
            with pytest.raises(ValueError, match="No TA1"):
                parse_ta1(raw)
