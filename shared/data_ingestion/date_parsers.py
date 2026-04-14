"""Date parsing utilities for reference-data ingestion pipelines.

Handles the common NCPDP / CMS / FDA date formats:
  - MMDDYYYY    (most NCPDP fixed-width files)
  - YYYYMMDD    (some CMS / FDA files)
  - MM/DD/YYYY  (delimited files)
  - Mmm DD, YYYY  (FDA Orange Book — e.g. "Jan 1, 1982")

All functions return ``datetime.date | None``.  '00000000', blank strings,
and strings that cannot be parsed all return ``None`` rather than raising.

LESSON-004: No regex with ``^...$`` anchors — all patterns use ``\\A...\\Z``
via ``re.fullmatch`` so they do not accept trailing newlines.
"""

from __future__ import annotations

import re
from datetime import date

# LESSON-004: fullmatch so patterns cannot match with trailing newlines.
_MMDDYYYY = re.compile(r"\A(\d{2})(\d{2})(\d{4})\Z")
_YYYYMMDD = re.compile(r"\A(\d{4})(\d{2})(\d{2})\Z")
_MM_DD_YYYY = re.compile(r"\A(\d{1,2})/(\d{1,2})/(\d{4})\Z")

# FDA Orange Book "Mmm DD, YYYY" format, e.g. "Jan 1, 1982" or "Dec 31, 2029"
# Also matches single-digit day without leading zero.
_MMM_DD_YYYY = re.compile(
    r"\A([A-Za-z]{3})\s+(\d{1,2}),\s*(\d{4})\Z"
)
_MONTH_ABBR: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_mmddyyyy(value: str | None) -> date | None:
    """Parse an MMDDYYYY string to a ``datetime.date``.

    Returns ``None`` for blank, '00000000', or invalid dates.
    """
    if not value or not value.strip():
        return None
    val = value.strip()
    if val == "00000000":
        return None
    m = _MMDDYYYY.fullmatch(val)
    if not m:
        return None
    mm, dd, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(yyyy, mm, dd)
    except ValueError:
        return None


def parse_yyyymmdd(value: str | None) -> date | None:
    """Parse a YYYYMMDD string to a ``datetime.date``.

    Returns ``None`` for blank, '00000000', or invalid dates.
    """
    if not value or not value.strip():
        return None
    val = value.strip()
    if val == "00000000":
        return None
    m = _YYYYMMDD.fullmatch(val)
    if not m:
        return None
    yyyy, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(yyyy, mm, dd)
    except ValueError:
        return None


def parse_mm_slash_dd_slash_yyyy(value: str | None) -> date | None:
    """Parse an MM/DD/YYYY string to a ``datetime.date``.

    Returns ``None`` for blank or invalid dates.
    """
    if not value or not value.strip():
        return None
    m = _MM_DD_YYYY.fullmatch(value.strip())
    if not m:
        return None
    mm, dd, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(yyyy, mm, dd)
    except ValueError:
        return None


def parse_ncpdp_date(value: str | None) -> date | None:
    """Try all common NCPDP date formats: MMDDYYYY, YYYYMMDD, MM/DD/YYYY.

    Returns the first successful parse, or ``None`` if all fail.
    """
    if not value or not value.strip():
        return None
    val = value.strip()
    return (
        parse_mmddyyyy(val)
        or parse_yyyymmdd(val)
        or parse_mm_slash_dd_slash_yyyy(val)
    )


def parse_mmm_dd_yyyy(value: str | None) -> date | None:
    """Parse an FDA Orange Book "Mmm DD, YYYY" string to a ``datetime.date``.

    Accepts abbreviated month names (case-insensitive), one or two digit day,
    and four-digit year. Examples:
      "Jan 1, 1982"  → date(1982, 1, 1)
      "Dec 31, 2029" → date(2029, 12, 31)

    Returns ``None`` for blank, unrecognised month abbreviations, or invalid
    calendar values. Never raises.

    LESSON-004: Uses \\A...\\Z anchors — the raw value (not stripped) is passed
    to fullmatch so trailing newlines and other whitespace cause a non-match.
    Leading/trailing whitespace is NOT stripped before matching; callers that
    receive raw field values from files should strip them first if needed.
    """
    if not value:
        return None
    # LESSON-004: pass value as-is to fullmatch so \A...\Z rejects trailing newlines.
    m = _MMM_DD_YYYY.fullmatch(value)
    if not m:
        return None
    month_num = _MONTH_ABBR.get(m.group(1).lower())
    if month_num is None:
        return None
    try:
        return date(int(m.group(3)), month_num, int(m.group(2)))
    except ValueError:
        return None


__all__ = [
    "parse_mmddyyyy",
    "parse_mmm_dd_yyyy",
    "parse_mm_slash_dd_slash_yyyy",
    "parse_ncpdp_date",
    "parse_yyyymmdd",
]
