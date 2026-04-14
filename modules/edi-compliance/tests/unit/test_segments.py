"""Tests for X12 segment builder and ISA field padding rules."""

from __future__ import annotations

import pytest

from src.x12.delimiters import Delimiters
from src.x12.segments import (
    build_segment,
    pad_isa_control,
    pad_isa_id,
    parse_segments,
)

_DELIMS = Delimiters(element="*", sub_element=":", segment="~")


def test_pad_isa_id_pads_to_15():
    result = pad_isa_id("INFINITYRX")
    assert len(result) == 15
    assert result == "INFINITYRX     "


def test_pad_isa_id_exact_15():
    result = pad_isa_id("123456789012345")
    assert result == "123456789012345"
    assert len(result) == 15


def test_pad_isa_id_too_long_raises():
    with pytest.raises(ValueError, match="exceeds 15 characters"):
        pad_isa_id("1234567890123456")


def test_pad_isa_id_preserves_trailing_spaces():
    """Trailing spaces in ISA06/ISA08 are structurally significant — never strip."""
    result = pad_isa_id("ABC")
    assert result.endswith("   ")
    assert result == "ABC            "


def test_pad_isa_control_leading_zeros():
    assert pad_isa_control(42) == "000000042"
    assert pad_isa_control(1) == "000000001"
    assert pad_isa_control(999999999) == "999999999"


def test_pad_isa_control_too_large():
    with pytest.raises(ValueError, match="exceeds 9 digits"):
        pad_isa_control(1000000000)


def test_build_segment_basic():
    result = build_segment("CLM", ["CLAIM001", "100.00", "1"], _DELIMS)
    assert result == "CLM*CLAIM001*100.00*1~"


def test_build_segment_none_becomes_empty():
    result = build_segment("REF", ["HPI", None], _DELIMS)
    assert result == "REF*HPI*~"


def test_parse_segments_basic():
    raw = "ISA*00*    *~GS*HC*~"
    segs = parse_segments(raw, _DELIMS)
    assert len(segs) == 2
    assert segs[0][0] == "ISA"
    assert segs[1][0] == "GS"


def test_parse_segments_preserves_isa_fields():
    """ISA06/ISA08 must NOT be stripped — trailing spaces are structurally significant."""
    raw = "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *~"
    segs = parse_segments(raw, _DELIMS)
    isa = segs[0]
    assert isa[6] == "SENDER         "
    assert len(isa[6]) == 15
    assert isa[8] == "RECEIVER       "
    assert len(isa[8]) == 15
