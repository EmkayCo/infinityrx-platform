"""Tests for X12 delimiter detection."""

from __future__ import annotations

import pytest

from src.x12.delimiters import Delimiters, detect_delimiters


def _make_isa(elem: str = "*", sub: str = ":", seg: str = "~") -> str:
    """Build a minimal 106-char ISA string with specific delimiter chars."""
    # ISA segment is fixed: "ISA" + elem + 15 fixed fields separated by elem
    # Total: 3 + 1 (elem) + 15 * (2 + 1) padded = complex; easier to build directly
    # Position 3 = elem, position 104 = sub, position 105 = seg
    base = "ISA" + elem
    # Fill 101 chars to reach position 104 (0-indexed) for sub-element separator
    filler = "X" * 100
    return base + filler + sub + seg


def test_detect_delimiters_default():
    raw = _make_isa("*", ":", "~")
    delims = detect_delimiters(raw)
    assert delims.element == "*"
    assert delims.sub_element == ":"
    assert delims.segment == "~"


def test_detect_delimiters_custom():
    raw = _make_isa("|", ">", "\n")
    delims = detect_delimiters(raw)
    assert delims.element == "|"
    assert delims.sub_element == ">"
    assert delims.segment == "\n"


def test_detect_delimiters_too_short():
    with pytest.raises(ValueError, match="too short"):
        detect_delimiters("ISA*short")


def test_detect_delimiters_not_isa():
    with pytest.raises(ValueError, match="must start with 'ISA'"):
        detect_delimiters("GS*" + "X" * 103)


def test_delimiters_validate_distinct():
    d = Delimiters(element="*", sub_element="*", segment="~")
    with pytest.raises(ValueError, match="distinct"):
        d.validate()


def test_delimiters_validate_length():
    d = Delimiters(element="**", sub_element=":", segment="~")
    with pytest.raises(ValueError, match="exactly 1 character"):
        d.validate()
