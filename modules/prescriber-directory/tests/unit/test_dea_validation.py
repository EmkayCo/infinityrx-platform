"""Tests for DEA number format validation.

DEA number format: 2 letters + 7 digits, check digit formula.
100% coverage required (security path).
"""

from __future__ import annotations

import pytest

from src.utils.validators import validate_dea_number, DeaValidationError


class TestDeaFormat:
    def test_valid_dea_passes(self):
        # AB1234563 — valid format and check digit
        assert validate_dea_number("AB1234563") is True

    def test_dea_wrong_length_raises(self):
        with pytest.raises(DeaValidationError, match="9 characters"):
            validate_dea_number("AB123456")

    def test_dea_invalid_first_letter_raises(self):
        """First letter must be A, B, C, D, E, F, G, H, J, K, M, P, R, S, T, U, X."""
        with pytest.raises(DeaValidationError, match="registrant"):
            validate_dea_number("ZB1234563")

    def test_dea_second_char_not_letter_raises(self):
        with pytest.raises(DeaValidationError, match="letter"):
            validate_dea_number("A11234563")

    def test_dea_trailing_newline_rejected(self):
        """LESSON-004: must use fullmatch/\\A\\Z anchors."""
        with pytest.raises(DeaValidationError):
            validate_dea_number("AB1234563\n")

    def test_dea_bad_check_digit_raises(self):
        with pytest.raises(DeaValidationError, match="check digit"):
            validate_dea_number("AB1234560")

    def test_dea_lowercase_rejected(self):
        """DEA numbers are uppercase only."""
        with pytest.raises(DeaValidationError):
            validate_dea_number("ab1234563")

    def test_dea_empty_raises(self):
        with pytest.raises(DeaValidationError):
            validate_dea_number("")

    def test_dea_letters_ok_but_non_digit_in_number_part_raises(self):
        """Both first chars uppercase letters but digit section has non-digit."""
        with pytest.raises(DeaValidationError, match="uppercase letters followed by 7 digits"):
            validate_dea_number("AB123456X")  # X is not a digit
