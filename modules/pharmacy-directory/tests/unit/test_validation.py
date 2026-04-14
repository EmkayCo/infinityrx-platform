"""RED tests: NPI/NABP/DEA validation using \\A\\Z anchors (LESSON-004)."""
from __future__ import annotations

import pytest

from src.utils.validation import (
    InvalidDeaNumberError,
    InvalidNabpNumberError,
    InvalidNpiNumberError,
    validate_dea_number,
    validate_nabp_number,
    validate_npi,
)


class TestNpiValidation:
    def test_valid_npi_passes(self) -> None:
        assert validate_npi("1234567893") == "1234567893"

    def test_npi_must_be_ten_digits(self) -> None:
        with pytest.raises(InvalidNpiNumberError):
            validate_npi("123456789")

    def test_npi_trailing_newline_rejected(self) -> None:
        with pytest.raises(InvalidNpiNumberError):
            validate_npi("1234567893\n")

    def test_npi_non_digits_rejected(self) -> None:
        with pytest.raises(InvalidNpiNumberError):
            validate_npi("123456789X")

    def test_empty_npi_rejected(self) -> None:
        with pytest.raises(InvalidNpiNumberError):
            validate_npi("")


class TestNabpValidation:
    def test_valid_nabp_passes(self) -> None:
        assert validate_nabp_number("1234567") == "1234567"

    def test_nabp_must_be_seven_digits(self) -> None:
        with pytest.raises(InvalidNabpNumberError):
            validate_nabp_number("123456")

    def test_nabp_trailing_newline_rejected(self) -> None:
        with pytest.raises(InvalidNabpNumberError):
            validate_nabp_number("1234567\n")

    def test_nabp_too_long_rejected(self) -> None:
        with pytest.raises(InvalidNabpNumberError):
            validate_nabp_number("12345678")


class TestDeaValidation:
    def test_valid_dea_format_passes(self) -> None:
        result = validate_dea_number("AB1234563")
        assert result == "AB1234563"

    def test_dea_trailing_newline_rejected(self) -> None:
        with pytest.raises(InvalidDeaNumberError):
            validate_dea_number("AB1234563\n")

    def test_dea_wrong_length_rejected(self) -> None:
        with pytest.raises(InvalidDeaNumberError):
            validate_dea_number("AB123456")

    def test_dea_invalid_prefix_rejected(self) -> None:
        with pytest.raises(InvalidDeaNumberError):
            validate_dea_number("11234563X")
