"""NDC normalization utility.

Normalizes NDC codes from any common format to the canonical 11-digit
zero-padded format (NDC-11) used throughout the platform.

Supported input formats:
- NDC-11: 11 digits, no dashes (e.g., "00093314905")
- 5-4-2 with dashes (e.g., "00093-3149-05")
- 10-digit (leading zero stripped from labeler segment)
- 10-digit with dashes: 4-4-2, 5-3-2, 5-4-1

LESSON-004: All validation uses re.fullmatch — never re.match with ^ and $
which accepts trailing newlines.
"""
from __future__ import annotations

import re


class InvalidNDCError(ValueError):
    """Raised when an NDC string cannot be parsed or normalized."""


_DIGITS_ONLY = re.compile(r"\A\d+\Z")
_NDC_11 = re.compile(r"\A\d{11}\Z")
_NDC_10 = re.compile(r"\A\d{10}\Z")

# Dash formats: segment lengths must sum to 10 or 11
_DASH_FORMAT = re.compile(r"\A(\d+)-(\d+)-(\d+)\Z")


def normalize_ndc(raw: str) -> str:
    """Return canonical 11-digit NDC-11 from any supported NDC format.

    Raises InvalidNDCError for unparseable or invalid input.
    """
    # Strip only ASCII spaces/tabs — NOT newlines (LESSON-004)
    ndc = raw.strip(" \t")

    if not ndc:
        raise InvalidNDCError("NDC must not be empty")

    # Reject any remaining whitespace (newlines, etc.)
    if any(c in ndc for c in ("\n", "\r", "\x0b", "\x0c")):
        raise InvalidNDCError(f"NDC contains whitespace/newlines: {raw!r}")

    if "-" in ndc:
        return _normalize_dashed(ndc)

    # Digits-only path
    if not _DIGITS_ONLY.match(ndc):
        raise InvalidNDCError(f"NDC contains invalid characters: {raw!r}")

    if _NDC_11.match(ndc):
        return ndc

    if _NDC_10.match(ndc):
        # Pad labeler (first segment) with one leading zero
        return "0" + ndc

    raise InvalidNDCError(
        f"NDC must be 10 or 11 digits (no dashes) or a valid dash format, got {len(ndc)} digits: {raw!r}"
    )


def _normalize_dashed(ndc: str) -> str:
    """Normalize a dash-separated NDC to 11-digit NDC-11."""
    m = _DASH_FORMAT.match(ndc)
    if not m:
        raise InvalidNDCError(f"Invalid NDC dash format: {ndc!r}")

    seg1, seg2, seg3 = m.group(1), m.group(2), m.group(3)
    total = len(seg1) + len(seg2) + len(seg3)

    if total not in (10, 11):
        raise InvalidNDCError(
            f"NDC dash segments must total 10 or 11 digits, got {total}: {ndc!r}"
        )

    # Pad each segment to canonical 5-4-2
    labeler = seg1.zfill(5)
    product = seg2.zfill(4)
    package = seg3.zfill(2)

    return labeler + product + package


def format_ndc(ndc_11: str) -> str:
    """Format an NDC-11 string as 5-4-2 with dashes (e.g., "00093-3149-05")."""
    ndc = normalize_ndc(ndc_11)
    return f"{ndc[:5]}-{ndc[5:9]}-{ndc[9:]}"
