"""Branch coverage for envelope.py."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.x12.delimiters import Delimiters, _DEFAULT_DELIMITERS
from src.x12.envelope import EnvelopeConfig, build_isa, build_gs

_DELIMS = Delimiters(element="*", sub_element=":", segment="~")
_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_build_isa_test_mode():
    """build_isa with test_mode=True uses ISA15=T."""
    config = EnvelopeConfig(
        sender_qualifier="ZZ",
        sender_id="SENDER",
        receiver_qualifier="ZZ",
        receiver_id="RECEIVER",
        isa_control_number=1,
        gs_control_number=1,
        test_mode=True,
    )
    isa = build_isa(config, _DELIMS, _NOW)
    elements = isa.split("*")
    assert elements[15] == "T"


def test_build_isa_production_mode():
    """build_isa with test_mode=False uses ISA15=P."""
    config = EnvelopeConfig(
        sender_qualifier="ZZ",
        sender_id="SENDER",
        receiver_qualifier="ZZ",
        receiver_id="RECEIVER",
        isa_control_number=1,
        gs_control_number=1,
        test_mode=False,
    )
    isa = build_isa(config, _DELIMS, _NOW)
    elements = isa.split("*")
    assert elements[15] == "P"


def test_build_isa_pads_sender_id():
    """build_isa pads sender_id to 15 chars."""
    config = EnvelopeConfig(
        sender_qualifier="ZZ",
        sender_id="SHORT",
        receiver_qualifier="ZZ",
        receiver_id="RECEIVER",
        isa_control_number=5,
        gs_control_number=5,
    )
    isa = build_isa(config, _DELIMS, _NOW)
    elements = isa.split("*")
    assert len(elements[6]) == 15
    assert elements[6] == "SHORT          "


def test_build_isa_now_defaults_to_utc():
    """build_isa without now parameter uses current UTC time (non-deterministic, just checks format)."""
    config = EnvelopeConfig(
        sender_qualifier="ZZ",
        sender_id="SENDER",
        receiver_qualifier="ZZ",
        receiver_id="RECEIVER",
        isa_control_number=1,
        gs_control_number=1,
    )
    isa = build_isa(config, _DELIMS)  # no now parameter
    # ISA09 is date in YYMMDD format — 6 digits
    elements = isa.split("*")
    assert len(elements[9]) == 6
    assert elements[9].isdigit()


def test_build_gs_now_defaults_to_utc():
    """build_gs without now parameter uses current UTC time."""
    gs = build_gs("HP", "SENDER", "RECEIVER", 1, version="005010X221A1", delims=_DELIMS)
    # GS04 is date in YYYYMMDD — 8 digits
    elements = gs.split("*")
    assert len(elements[4]) == 8
    assert elements[4].isdigit()
