"""Date parsing utilities for reference-data ingestion pipelines.

Handles the common NCPDP / CMS date formats:
  - MMDDYYYY  (most NCPDP fixed-width files)
  - YYYYMMDD  (some CMS / FDA files)
  - MM/DD/YYYY (delimited files)

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


__all__ = [
    "parse_mmddyyyy",
    "parse_yyyymmdd",
    "parse_mm_slash_dd_slash_yyyy",
    "parse_ncpdp_date",
]
