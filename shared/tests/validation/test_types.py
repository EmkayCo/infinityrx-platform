"""Tests for shared.validation.types — input validation framework.

Covers NPI (Luhn), NDC, Phone (E.164), DateISO with valid, invalid,
and edge cases.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from shared.validation.types import (
    NPI,
    NDC,
    PhoneE164,
    DateISO,
    validate_npi,
    validate_ndc,
    validate_phone_e164,
    validate_date_iso,
)


# ---------------------------------------------------------------------------
# NPI — National Provider Identifier
# ---------------------------------------------------------------------------


class NPIModel(BaseModel):
    npi: NPI


def test_npi_valid_known():
    """Known valid NPI: 1234567893 passes Luhn with 80840 prefix."""
    assert validate_npi("1234567893") == "1234567893"


def test_npi_valid_via_model():
    m = NPIModel(npi="1234567893")
    assert m.npi == "1234567893"


def test_npi_wrong_length():
    with pytest.raises(ValueError, match="10 digits"):
        validate_npi("12345")


def test_npi_non_digits():
    with pytest.raises(ValueError, match="10 digits"):
        validate_npi("12345ABCDE")


def test_npi_fails_luhn():
    with pytest.raises(ValueError, match="Luhn"):
        validate_npi("1234567890")


def test_npi_model_rejects_invalid():
    with pytest.raises(ValidationError):
        NPIModel(npi="0000000000")


def test_npi_all_ones_check():
    """1111111111 — check if Luhn passes (it doesn't — verify rejection)."""
    with pytest.raises(ValueError):
        validate_npi("1111111111")


# ---------------------------------------------------------------------------
# NDC — National Drug Code
# ---------------------------------------------------------------------------


class NDCModel(BaseModel):
    ndc: NDC


def test_ndc_valid_11_digits():
    assert validate_ndc("00000000000") == "00000000000"


def test_ndc_formatted_5_4_2():
    """5-4-2 format should be stripped to 11 digits."""
    m = NDCModel(ndc="12345-6789-01")
    assert m.ndc == "12345678901"


def test_ndc_wrong_length():
    with pytest.raises(ValueError, match="11 digits"):
        validate_ndc("1234567890")


def test_ndc_non_digits():
    with pytest.raises(ValueError, match="11 digits"):
        validate_ndc("1234567890A")


def test_ndc_12_digits():
    with pytest.raises(ValueError, match="11 digits"):
        validate_ndc("123456789012")


# ---------------------------------------------------------------------------
# Phone — E.164
# ---------------------------------------------------------------------------


class PhoneModel(BaseModel):
    phone: PhoneE164


def test_phone_valid_us():
    assert validate_phone_e164("+12125551234") == "+12125551234"


def test_phone_valid_uk():
    assert validate_phone_e164("+442071234567") == "+442071234567"


def test_phone_valid_short():
    """Minimum E.164: +1234567 (7 digits after +)."""
    assert validate_phone_e164("+1234567") == "+1234567"


def test_phone_missing_plus():
    with pytest.raises(ValueError, match="E.164"):
        validate_phone_e164("12125551234")


def test_phone_leading_zero_country():
    with pytest.raises(ValueError, match="E.164"):
        validate_phone_e164("+0123456789")


def test_phone_too_short():
    with pytest.raises(ValueError, match="E.164"):
        validate_phone_e164("+12345")


def test_phone_too_long():
    with pytest.raises(ValueError, match="E.164"):
        validate_phone_e164("+1234567890123456")  # 16 digits


def test_phone_letters():
    with pytest.raises(ValueError, match="E.164"):
        validate_phone_e164("+1212555ABCD")


# ---------------------------------------------------------------------------
# DateISO — ISO 8601
# ---------------------------------------------------------------------------


class DateModel(BaseModel):
    d: DateISO


def test_date_valid():
    assert validate_date_iso("2026-04-13") == "2026-04-13"


def test_date_leap_year():
    assert validate_date_iso("2024-02-29") == "2024-02-29"


def test_date_invalid_calendar():
    with pytest.raises(ValueError, match="Invalid calendar date"):
        validate_date_iso("2026-02-30")


def test_date_wrong_format_slashes():
    with pytest.raises(ValueError, match="ISO 8601"):
        validate_date_iso("04/13/2026")


def test_date_wrong_format_no_dashes():
    with pytest.raises(ValueError, match="ISO 8601"):
        validate_date_iso("20260413")


def test_date_month_13():
    with pytest.raises(ValueError):
        validate_date_iso("2026-13-01")


def test_date_model_valid():
    m = DateModel(d="2026-01-15")
    assert m.d == "2026-01-15"


def test_date_model_rejects_invalid():
    with pytest.raises(ValidationError):
        DateModel(d="not-a-date")
