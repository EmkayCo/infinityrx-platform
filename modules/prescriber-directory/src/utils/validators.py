"""NPI and DEA number validation utilities.

Security-sensitive validators:
- NPI: 10-digit Luhn check with 80840 prefix (CMS specification)
- DEA: 2-letter + 7-digit format with DEA check digit algorithm

LESSON-004: All regex uses re.fullmatch() or \\A...\\Z anchors — never re.match with ^$.
"""

from __future__ import annotations

import re


class NpiValidationError(ValueError):
    pass


class DeaValidationError(ValueError):
    pass


_NPI_RE = re.compile(r"\A\d{10}\Z")

# Valid first-letter registrant codes for DEA numbers
_DEA_FIRST_LETTERS = frozenset("ABCDEFGHJKMPRSTU X")


def validate_npi(npi: str) -> bool:
    """Validate a 10-digit NPI using the Luhn algorithm with 80840 prefix.

    The CMS check-digit algorithm prepends '80840' to the NPI before running
    Luhn, which is part of the NPI specification (CMS NPI Final Rule).

    Raises NpiValidationError on invalid input, returns True on success.
    """
    if not isinstance(npi, str):
        raise NpiValidationError("NPI must be a string")
    if not _NPI_RE.match(npi):
        if not npi:
            raise NpiValidationError("NPI must be 10 digits, got empty string")
        if not re.fullmatch(r"\d+", npi):
            raise NpiValidationError("NPI must contain only digits")
        raise NpiValidationError(f"NPI must be 10 digits, got {len(npi)}")

    # CMS Luhn: prepend 80840, then run standard Luhn on 15-digit string
    padded = "80840" + npi
    total = 0
    for i, ch in enumerate(reversed(padded)):
        digit = int(ch)
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit

    if total % 10 != 0:
        raise NpiValidationError(f"NPI {npi} fails Luhn check digit validation")

    return True


def validate_dea_number(dea: str) -> bool:
    """Validate a DEA registration number.

    Format: 2 uppercase letters + 7 digits.
    First letter: registrant type code (A/B/C/D/E/F/G/H/J/K/M/P/R/S/T/U/X).
    Second letter: first letter of registrant's last name (A-Z).
    Check digit: (sum of digits 1,3,5) + 2*(sum of digits 2,4,6) → last digit of total.

    LESSON-004: uses re.fullmatch — not re.match which would accept trailing newline.
    """
    if not isinstance(dea, str) or not dea:
        raise DeaValidationError("DEA number must be a non-empty string")

    if len(dea) != 9:
        raise DeaValidationError(f"DEA number must be 9 characters, got {len(dea)}")

    if not re.fullmatch(r"\A[A-Z]{2}\d{7}\Z", dea):
        if not dea[0].isupper() or not dea[0].isalpha():
            raise DeaValidationError("DEA number first character must be an uppercase letter")
        if not dea[1].isupper() or not dea[1].isalpha():
            raise DeaValidationError("DEA number second character must be an uppercase letter")
        raise DeaValidationError("DEA number must be 2 uppercase letters followed by 7 digits")

    first = dea[0]
    if first not in _DEA_FIRST_LETTERS:
        raise DeaValidationError(
            f"DEA registrant type code '{first}' is not a valid registrant letter"
        )

    digits = [int(c) for c in dea[2:]]
    odd_sum = digits[0] + digits[2] + digits[4]
    even_sum = digits[1] + digits[3] + digits[5]
    total = odd_sum + 2 * even_sum
    expected_check = total % 10

    if expected_check != digits[6]:
        raise DeaValidationError(
            f"DEA number {dea} fails check digit validation "
            f"(expected {expected_check}, got {digits[6]})"
        )

    return True
