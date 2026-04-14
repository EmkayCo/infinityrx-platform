"""Tests targeting uncovered lines/branches in parsers."""

from __future__ import annotations

import pytest

from src.x12.parsers.parse_271 import parse_271
from src.x12.parsers.parse_277 import parse_277


def _make_x12_no_isa(isa_replace: str = "GS") -> str:
    """Build a valid-delimiter X12 file with no ISA segment."""
    return (
        f"{isa_replace}*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
        "*260101*1200*^*00501*000000001*0*T*:~"
        "GE*1*1~"
        "IEA*1*000000001~"
    )


class TestParse271NoIsa:
    def test_no_isa_segment_raises_value_error(self):
        # Build a file that passes detect_delimiters (has ISA at col 3/104/105)
        # but where we swap ISA to something else so parse finds no ISA
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*HB*SENDER*RECEIVER*20260101*1200*1*X*005010X279A1~"
            "SE*4*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        # Replace ISA with a valid-delimiter file that detect_delimiters can parse
        # but has GS as first segment instead of ISA
        from unittest.mock import patch

        real_segs = [
            ["GS", "HB", "SENDER", "RECEIVER"],
            ["SE", "4", "0001"],
            ["GE", "1", "1"],
            ["IEA", "1", "000000001"],
        ]
        with patch("src.x12.parsers.parse_271.parse_segments", return_value=real_segs):
            with pytest.raises(ValueError, match="No ISA segment"):
                parse_271(raw)


class TestParse277NoIsa:
    def test_no_isa_segment_raises_value_error(self):
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*HN*SENDER*RECEIVER*20260101*1200*1*X*005010X212~"
            "SE*4*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        from unittest.mock import patch
        real_segs = [
            ["GS", "HN", "SENDER"],
            ["SE", "4", "0001"],
            ["GE", "1", "1"],
        ]
        with patch("src.x12.parsers.parse_277.parse_segments", return_value=real_segs):
            with pytest.raises(ValueError, match="No ISA segment"):
                parse_277(raw)


class TestParse277SegmentBranches:
    """Cover short-segment guard branches in parse_277 loop."""

    def test_nm1_segment_too_short_skipped(self):
        """NM1 with < 3 elements — should not crash."""
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*HN*SENDER*RECEIVER*20260101*1200*1*X*005010X212~"
            "ST*277*0001*005010X212~"
            "BHT*0010*08*RESP000000001*20260101*1200~"
            "HL*1**20*1~"
            "NM1*PR~"  # too short: only 2 elements
            "NM1*PR*2*PAYER*****PI*P01~"
            "SE*8*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        # Should parse without error, payer_name set from the valid NM1
        parsed = parse_277(raw)
        assert parsed.payer_name == "PAYER"

    def test_hl_segment_too_short(self):
        """HL with < 4 elements — level_code should default to empty string."""
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*HN*SENDER*RECEIVER*20260101*1200*1*X*005010X212~"
            "ST*277*0001*005010X212~"
            "BHT*0010*08*RESP000000001*20260101*1200~"
            "HL*1~"  # too short
            "NM1*PR*2*PAYER*****PI*P01~"
            "SE*7*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        parsed = parse_277(raw)
        assert parsed.payer_name == "PAYER"


class TestParse271SegmentBranches:
    """Cover short NM1 guard branch in parse_271."""

    def test_nm1_with_4_elements_processed(self):
        """NM1 with exactly 4 elements (entity qualifier but no id code)."""
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*HB*SENDER*RECEIVER*20260101*1200*1*X*005010X279A1~"
            "ST*271*0001*005010X279A1~"
            "BHT*0022*11*ELIG000000001*20260101*1200~"
            "HL*1**20*1~"
            "NM1*PR*2*PAYER~"
            "NM1*PR*2*PAYER2*****PI*P01~"
            "HL*2*1*21*1~"
            "NM1*1P*2*PROV*****XX*0000000000~"
            "HL*3*2*22*0~"
            "NM1*IL*1*HILL*MARY****MI*S01~"
            "EB*1*IND*30*HM~"
            "SE*13*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        parsed = parse_271(raw)
        # The valid NM1*PR with 9+ elements sets payer
        assert parsed.payer_name == "PAYER2"
