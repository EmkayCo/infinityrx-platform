"""Input validators for medical claims.

Uses \\A...\\Z anchors (LESSON-004) for all security-sensitive regex.
"""
from __future__ import annotations

import re

# Compiled patterns — \\A...\\Z are strict anchors (no trailing-newline bypass)
_NPI_RE = re.compile(r"\A\d{10}\Z")
_NDC_RE = re.compile(r"\A\d{11}\Z")
_HCPCS_RE = re.compile(r"\A[A-Z]\d{4}\Z")
_QUARTER_RE = re.compile(r"\A\d{4}-Q[1-4]\Z")


def is_valid_npi(value: str) -> bool:
    """NPI must be exactly 10 digits."""
    return bool(_NPI_RE.match(value))


def is_valid_ndc(value: str) -> bool:
    """NDC must be exactly 11 digits (no dashes)."""
    return bool(_NDC_RE.match(value))


def is_drug_hcpcs(code: str) -> bool:
    """True if code is a HCPCS J-code, Q-code, or C-code."""
    if not code:
        return False
    return bool(re.match(r"\A[JQC]\d{4}\Z", code))


def is_valid_quarter(quarter: str) -> bool:
    """Quarter format: YYYY-Q1 through YYYY-Q4."""
    return bool(_QUARTER_RE.match(quarter))


def classify_site_of_care(place_of_service: str | None) -> str | None:
    """Map CMS POS code to site-of-care category."""
    _MAP = {
        "11": "office_infusion",
        "22": "hospital_outpatient",
        "24": "asc",
        "12": "home_infusion",
        "01": "specialty_pharmacy",
    }
    if place_of_service is None:
        return None
    return _MAP.get(place_of_service)


def has_jw_modifier(m1: str | None, m2: str | None, m3: str | None, m4: str | None) -> bool:
    """True if the JW waste modifier is present on the claim line."""
    return "JW" in {m for m in (m1, m2, m3, m4) if m}


def has_340b_modifier(m1: str | None, m2: str | None, m3: str | None, m4: str | None) -> bool:
    """True if modifier JG or TB (340B indicators) is present."""
    mods = {m for m in (m1, m2, m3, m4) if m}
    return bool(mods & {"JG", "TB"})
