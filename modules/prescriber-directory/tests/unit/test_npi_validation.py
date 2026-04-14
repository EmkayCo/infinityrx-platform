"""Tests for NPI validation — Luhn check with 80840 prefix.

100% coverage required (security path).
"""

from __future__ import annotations

import pytest

from src.utils.validators import validate_npi, NpiValidationError


class TestNpiFormat:
    def test_valid_npi_passes(self):
        # 1234567893 is a valid Luhn-conforming NPI (80840 + npi = check)
        assert validate_npi("1234567893") is True

    def test_npi_wrong_length_raises(self):
        with pytest.raises(NpiValidationError, match="10 digits"):
            validate_npi("12345")

    def test_npi_non_digit_raises(self):
        with pytest.raises(NpiValidationError, match="digits"):
            validate_npi("123456789X")

    def test_npi_trailing_newline_rejected(self):
        """LESSON-004: re.match with $ accepts trailing newline — use fullmatch."""
        with pytest.raises(NpiValidationError):
            validate_npi("1234567893\n")

    def test_npi_with_spaces_rejected(self):
        with pytest.raises(NpiValidationError):
            validate_npi(" 1234567893")

    def test_npi_bad_luhn_raises(self):
        with pytest.raises(NpiValidationError, match="Luhn"):
            validate_npi("1234567890")

    def test_npi_empty_string_raises(self):
        with pytest.raises(NpiValidationError):
            validate_npi("")

    def test_npi_none_raises(self):
        with pytest.raises((NpiValidationError, TypeError)):
            validate_npi(None)  # type: ignore[arg-type]


class TestNpiLuhnAlgorithm:
    """Verify the Luhn algorithm includes the 80840 prefix."""

    def test_known_valid_npis(self):
        # These are known-valid 10-digit NPIs with correct Luhn check digits
        valid_npis = [
            "1234567893",
            "1679576722",
            "1003000126",
        ]
        for npi in valid_npis:
            assert validate_npi(npi) is True, f"Expected {npi} to be valid"

    def test_check_digit_off_by_one_fails(self):
        # Take a valid NPI, change the last digit by 1 → should fail Luhn
        with pytest.raises(NpiValidationError, match="Luhn"):
            validate_npi("1234567892")  # last digit 2 instead of 3
