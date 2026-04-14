"""Tests for shared.utils.dea_validator.

DEA number validator is security-sensitive — must achieve 100% branch coverage.
LESSON-004: Includes trailing-newline test to verify \\A...\\Z anchors.
"""

from __future__ import annotations

import pytest

from shared.utils.dea_validator import validate_dea_number


# ---------------------------------------------------------------------------
# Known-valid DEA numbers
# ---------------------------------------------------------------------------
# AS1234563: A=registrant type, S=surname initial, 123456=digits, 3=check digit
# Checksum: (1+3+5) + 2*(2+4+6) = 9 + 24 = 33 → last digit = 3 ✓

def _compute_check_digit(prefix: str, six_digits: str) -> int:
    """Helper to compute expected check digit for test construction."""
    d = [int(c) for c in six_digits]
    total = (d[0] + d[2] + d[4]) + 2 * (d[1] + d[3] + d[5])
    return total % 10


class TestDeaFormatValidation:
    def test_dea_format_rejects_wrong_length_short(self):
        valid, reason = validate_dea_number("AS12345")
        assert not valid
        assert "pattern" in reason.lower() or "must match" in reason.lower()

    def test_dea_format_rejects_wrong_length_long(self):
        valid, reason = validate_dea_number("AS1234567890")
        assert not valid

    def test_dea_format_rejects_lowercase_letters(self):
        valid, reason = validate_dea_number("as1234563")
        assert not valid
        assert "pattern" in reason.lower() or "must match" in reason.lower()

    def test_dea_format_rejects_mixed_case(self):
        valid, reason = validate_dea_number("As1234563")
        assert not valid

    def test_dea_format_rejects_all_digits(self):
        valid, reason = validate_dea_number("123456789")
        assert not valid

    def test_dea_format_rejects_non_string(self):
        valid, reason = validate_dea_number(None)  # type: ignore[arg-type]
        assert not valid
        assert "string" in reason.lower()

    def test_dea_format_rejects_trailing_newline(self):
        """LESSON-004: \\A...\\Z must reject trailing newline that ^...$ would accept."""
        valid, reason = validate_dea_number("AS1234563\n")
        assert not valid, "Trailing newline must be rejected (LESSON-004)"

    def test_dea_format_rejects_embedded_newline(self):
        valid, reason = validate_dea_number("AS12\n4563")
        assert not valid

    def test_dea_format_rejects_leading_space(self):
        valid, reason = validate_dea_number(" AS1234563")
        assert not valid

    def test_dea_format_rejects_trailing_space(self):
        valid, reason = validate_dea_number("AS1234563 ")
        assert not valid

    def test_dea_format_rejects_empty_string(self):
        valid, reason = validate_dea_number("")
        assert not valid


class TestDeaRegistrantTypeCodes:
    def test_dea_invalid_registrant_type_I(self):
        # I is not a valid registrant type
        valid, reason = validate_dea_number("IS1234563")
        assert not valid
        assert "registrant type" in reason.lower()

    def test_dea_invalid_registrant_type_O(self):
        valid, reason = validate_dea_number("OS1234563")
        assert not valid

    def test_dea_invalid_registrant_type_V(self):
        valid, reason = validate_dea_number("VS1234563")
        assert not valid

    def test_dea_invalid_registrant_type_W(self):
        valid, reason = validate_dea_number("WS1234563")
        assert not valid


class TestDeaChecksumValidation:
    def test_dea_checksum_valid_example_AS1234563(self):
        """Known-valid: AS1234563 — checksum = (1+3+5) + 2*(2+4+6) = 9+24=33 → 3."""
        valid, reason = validate_dea_number("AS1234563")
        assert valid, f"Expected valid, got: {reason}"
        assert reason == "valid"

    def test_dea_checksum_valid_example_BP9876543(self):
        """Known-valid: BP9876543 — checksum = (9+7+5) + 2*(8+6+4) = 21+36=57 → 7.
        Wait — check digit is 3, not 7. Let's verify:
        d1=9,d2=8,d3=7,d4=6,d5=5,d6=4, check=3
        (9+7+5) + 2*(8+6+4) = 21 + 36 = 57 → last = 7 ≠ 3 → invalid.
        Use a verified number instead.
        """
        # Compute the correct check digit for BP987654
        check = _compute_check_digit("BP", "987654")
        dea = f"BP987654{check}"
        valid, reason = validate_dea_number(dea)
        assert valid, f"Expected valid for {dea}, got: {reason}"

    def test_dea_checksum_valid_multiple_types(self):
        """Verify several registrant types all pass when checksum is correct."""
        for rtype in "ABCDEFJMPRS":
            six = "123456"
            check = _compute_check_digit(rtype, six)
            dea = f"{rtype}S{six}{check}"
            valid, reason = validate_dea_number(dea)
            assert valid, f"Expected valid for {dea}, got: {reason}"

    def test_dea_checksum_invalid_flipped_digit(self):
        """Flip the check digit — should fail checksum."""
        valid_dea = "AS1234563"
        # Flip check digit: 3 → 4
        invalid_dea = valid_dea[:-1] + "4"
        valid, reason = validate_dea_number(invalid_dea)
        assert not valid
        assert "check digit" in reason.lower()

    def test_dea_checksum_invalid_off_by_one(self):
        valid_dea = "AS1234563"
        # Change one interior digit
        invalid_dea = "AS1334563"
        valid2, reason2 = validate_dea_number(invalid_dea)
        # May or may not be invalid depending on coincidence — if coincidentally valid, skip
        # But AS1334563: (1+3+5)+2*(3+4+6)=9+26=35 → 5 ≠ 3 → invalid
        assert not valid2

    def test_dea_checksum_returns_reason_with_expected_and_actual(self):
        """Reason string should show expected vs actual digit."""
        valid, reason = validate_dea_number("AS1234564")
        assert not valid
        assert "expected" in reason.lower() or "mismatch" in reason.lower()

    def test_dea_checksum_all_zeros_prefix(self):
        """Edge case: all-zero digits."""
        # AS000000: (0+0+0)+2*(0+0+0)=0 → check=0
        valid, reason = validate_dea_number("AS0000000")
        assert valid, f"Expected valid, got: {reason}"

    def test_dea_checksum_boundary_digits(self):
        """Edge case: all nines."""
        check = _compute_check_digit("AS", "999999")
        dea = f"AS999999{check}"
        valid, reason = validate_dea_number(dea)
        assert valid, f"Expected valid for {dea}, got: {reason}"
