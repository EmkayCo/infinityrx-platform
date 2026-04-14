"""Input validation for pharmacy identifiers.

Uses \\A...\\Z anchors (LESSON-004) -- never re.match with ^...$
"""
from __future__ import annotations

import re


class InvalidNpiNumberError(ValueError):
    pass


class InvalidNabpNumberError(ValueError):
    pass


class InvalidDeaNumberError(ValueError):
    pass


_NPI_RE = re.compile(r"\A\d{10}\Z")
_NABP_RE = re.compile(r"\A\d{7}\Z")
# DEA: 2-letter prefix (letter + letter/digit) + 7 digits
_DEA_RE = re.compile(r"\A[A-Z][A-Z9]\d{7}\Z")


def validate_npi(value: str) -> str:
    if not _NPI_RE.match(value):
        raise InvalidNpiNumberError(f"NPI must be exactly 10 digits: {value!r}")
    return value


def validate_nabp_number(value: str) -> str:
    if not _NABP_RE.match(value):
        raise InvalidNabpNumberError(f"NABP must be exactly 7 digits: {value!r}")
    return value


def validate_dea_number(value: str) -> str:
    if not _DEA_RE.match(value):
        raise InvalidDeaNumberError(f"DEA must be 2-letter prefix + 7 digits: {value!r}")
    return value
