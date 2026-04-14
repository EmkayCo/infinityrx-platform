"""RED tests for NDC normalization utility.

NDC formats:
- NDC-11: 11 digits, no dashes (e.g., "00093314905")
- 5-4-2 with dashes (e.g., "00093-3149-05")
- 10-digit (e.g., "0093314905") — leading zero may be stripped
- 10-digit with dashes in various segment patterns: 5-3-2, 4-4-2, 5-4-1

Normalization target: always 11-digit no-dash (NDC-11) with zero-padding.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from src.utils.ndc import InvalidNDCError, normalize_ndc


class TestNormalizeNdcExact11Digit:
    def test_already_11_digits_returned_unchanged(self) -> None:
        assert normalize_ndc("00093314905") == "00093314905"

    def test_11_digit_with_leading_zeros_preserved(self) -> None:
        assert normalize_ndc("00002143601") == "00002143601"

    def test_all_zeros_edge_case(self) -> None:
        assert normalize_ndc("00000000000") == "00000000000"


class TestNormalizeNdcDashFormats:
    def test_5_4_2_with_dashes(self) -> None:
        assert normalize_ndc("00093-3149-05") == "00093314905"

    def test_5_4_2_with_leading_zero_preserved(self) -> None:
        assert normalize_ndc("00002-1436-01") == "00002143601"

    def test_4_4_2_format_zero_padded_to_5_4_2(self) -> None:
        # 4-4-2: labeler is 4 digits → pad to 5
        assert normalize_ndc("0093-3149-05") == "00093314905"

    def test_5_3_2_format_zero_padded_to_5_4_2(self) -> None:
        # 5-3-2: product is 3 digits → pad to 4
        assert normalize_ndc("00093-314-05") == "00093031405"

    def test_5_4_1_format_zero_padded_to_5_4_2(self) -> None:
        # 5-4-1: package is 1 digit → pad to 2
        assert normalize_ndc("00093-3149-5") == "00093314905"


class TestNormalizeNdc10Digit:
    def test_10_digit_infers_5_4_1_to_5_4_2(self) -> None:
        # Ambiguous: FDA typically strips leading zero from labeler
        # Standard inference: pad labeler (position 0) with leading zero
        assert normalize_ndc("0093314905") == "00093314905"

    def test_10_digit_no_leading_zero_stripped(self) -> None:
        # If labeler starts with non-zero, still pad to 11
        assert normalize_ndc("1234567890") == "01234567890"


class TestNormalizeNdcWhitespaceStripped:
    def test_whitespace_stripped(self) -> None:
        assert normalize_ndc("  00093314905  ") == "00093314905"

    def test_dash_format_with_whitespace(self) -> None:
        assert normalize_ndc(" 00093-3149-05 ") == "00093314905"


class TestNormalizeNdcInvalid:
    def test_empty_string_raises(self) -> None:
        with pytest.raises(InvalidNDCError):
            normalize_ndc("")

    def test_too_short_raises(self) -> None:
        with pytest.raises(InvalidNDCError):
            normalize_ndc("1234")

    def test_too_long_raises(self) -> None:
        with pytest.raises(InvalidNDCError):
            normalize_ndc("123456789012")

    def test_non_digit_non_dash_raises(self) -> None:
        with pytest.raises(InvalidNDCError):
            normalize_ndc("0009A-3149-05")

    def test_newline_trailing_raises(self) -> None:
        # LESSON-004: must use fullmatch/\A\Z, not re.match with ^$
        with pytest.raises(InvalidNDCError):
            normalize_ndc("00093314905\n")


class TestNormalizeNdcFormatOutput:
    def test_format_ndc_returns_5_4_2_dashes(self) -> None:
        from src.utils.ndc import format_ndc

        assert format_ndc("00093314905") == "00093-3149-05"

    def test_format_ndc_single_digit_package_padded(self) -> None:
        from src.utils.ndc import format_ndc

        assert format_ndc("00093314900") == "00093-3149-00"
