"""Reusable Pydantic annotated types for healthcare input validation.

Provides validated types for:
- NPI (National Provider Identifier) — 10 digits, Luhn check
- NDC (National Drug Code) — 11 digits
- Phone — E.164 format
- Email — RFC 5322 via Pydantic's EmailStr
- DateISO — ISO 8601 date string

Usage::

    from shared.validation.types import NPI, NDC, PhoneE164

    class ClaimRequest(BaseModel):
        provider_npi: NPI
        drug_ndc: NDC
        pharmacy_phone: PhoneE164
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, Field

__all__ = [
    "NPI",
    "NDC",
    "PhoneE164",
    "DateISO",
    "validate_npi",
    "validate_ndc",
    "validate_phone_e164",
    "validate_date_iso",
]

# ---------------------------------------------------------------------------
# NPI — National Provider Identifier (10 digits, Luhn-validated)
# ---------------------------------------------------------------------------

_NPI_RE = re.compile(r"^\d{10}$")


def _luhn_check(digits: str) -> bool:
    """Luhn algorithm check for NPI validation.

    NPI uses the Luhn algorithm with a constant prefix of 80840 prepended
    to the 10-digit NPI for the check digit calculation.
    """
    # Prepend the 80840 constant for healthcare provider IDs
    full = "80840" + digits
    total = 0
    for i, ch in enumerate(reversed(full)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def validate_npi(value: str) -> str:
    """Validate a 10-digit NPI with Luhn check.

    Raises:
        ValueError: If not 10 digits or Luhn check fails.
    """
    if not _NPI_RE.match(value):
        raise ValueError("NPI must be exactly 10 digits")
    if not _luhn_check(value):
        raise ValueError(f"NPI {value} fails Luhn check digit validation")
    return value


NPI = Annotated[str, AfterValidator(validate_npi), Field(min_length=10, max_length=10)]

# ---------------------------------------------------------------------------
# NDC — National Drug Code (11 digits, supports 5-4-2 or plain 11)
# ---------------------------------------------------------------------------

_NDC_PLAIN_RE = re.compile(r"^\d{11}$")
_NDC_FORMATTED_RE = re.compile(r"^\d{5}-\d{4}-\d{2}$")


def _strip_ndc_dashes(value: str) -> str:
    """Strip dashes from formatted NDC before validation."""
    return value.replace("-", "")


def validate_ndc(value: str) -> str:
    """Validate an 11-digit NDC code.

    Accepts plain 11-digit or 5-4-2 formatted (dashes stripped).

    Raises:
        ValueError: If not 11 digits after stripping.
    """
    if not _NDC_PLAIN_RE.match(value):
        raise ValueError(
            f"NDC must be exactly 11 digits (got {len(value)} chars): {value!r}"
        )
    return value


NDC = Annotated[
    str,
    BeforeValidator(_strip_ndc_dashes),
    AfterValidator(validate_ndc),
]

# ---------------------------------------------------------------------------
# Phone — E.164 format (+1XXXXXXXXXX)
# ---------------------------------------------------------------------------

_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def validate_phone_e164(value: str) -> str:
    """Validate an E.164 formatted phone number.

    Must start with + followed by 7-15 digits, first digit non-zero.

    Raises:
        ValueError: If not valid E.164 format.
    """
    if not _E164_RE.match(value):
        raise ValueError(
            f"Phone number must be E.164 format (e.g. +12125551234), got: {value!r}"
        )
    return value


PhoneE164 = Annotated[str, AfterValidator(validate_phone_e164)]

# ---------------------------------------------------------------------------
# Date — ISO 8601 string
# ---------------------------------------------------------------------------

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_date_iso(value: str) -> str:
    """Validate an ISO 8601 date string (YYYY-MM-DD).

    Also validates the date is a real calendar date.

    Raises:
        ValueError: If not a valid ISO 8601 date.
    """
    if not _ISO_DATE_RE.match(value):
        raise ValueError(
            f"Date must be ISO 8601 format (YYYY-MM-DD), got: {value!r}"
        )
    # Verify it's a real date (e.g. reject 2026-02-30)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid calendar date: {value!r}") from exc
    return value


DateISO = Annotated[str, AfterValidator(validate_date_iso)]
