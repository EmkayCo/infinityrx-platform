"""DEA registration number format and checksum validator.

DEA number format: 2 letters + 6 digits + 1 check digit = 9 chars total

First letter (registrant type):
    A/B/C/D/E/F/G/H/J/K/L/M/P/R/S/T/U/X

Second letter: first letter of registrant surname (A-Z) for practitioners;
    businesses may use specific letters.

Check digit algorithm:
    d1..d6 are the 6 numeric digits (positions 2-7).
    checksum = (d1 + d3 + d5) + 2*(d2 + d4 + d6)
    Check digit = last digit of checksum (checksum % 10).

LESSON-004: Uses \\A...\\Z anchors — never re.match with ^...$
"""

from __future__ import annotations

import re

# LESSON-004: \A...\Z strict anchors
_DEA_FORMAT_RE = re.compile(r"\A[A-Z]{2}\d{7}\Z")

_VALID_REGISTRANT_TYPES = frozenset("ABCDEFGHJKLMPRSTUX")


def validate_dea_number(dea_number: str) -> tuple[bool, str]:
    """Validate a DEA registration number format and check digit.

    Parameters
    ----------
    dea_number:
        The 9-character DEA number to validate.

    Returns
    -------
    tuple[bool, str]
        (True, "valid") on success, or (False, <reason>) on failure.
    """
    if not isinstance(dea_number, str):
        return False, "DEA number must be a string"

    if not _DEA_FORMAT_RE.match(dea_number):
        return False, f"DEA number must match pattern [A-Z]{{2}}[0-9]{{7}}, got: {dea_number!r}"

    registrant_type = dea_number[0]
    if registrant_type not in _VALID_REGISTRANT_TYPES:
        return False, f"Invalid registrant type code: {registrant_type!r}"

    digits = dea_number[2:]  # 7 chars: d1-d6 + check digit
    d1, d2, d3, d4, d5, d6, check = (int(c) for c in digits)

    computed = (d1 + d3 + d5) + 2 * (d2 + d4 + d6)
    expected_check = computed % 10

    if check != expected_check:
        return False, f"Check digit mismatch: expected {expected_check}, got {check}"

    return True, "valid"


__all__ = ["validate_dea_number"]
