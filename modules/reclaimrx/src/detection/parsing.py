"""Money and date-of-service parsing helpers for CSV ingestion.

Pure functions -- no I/O, no DB, no side effects.
Financial precision: Decimal only, never float.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

# Inclusive lower bound for valid dates of service.
_DOS_FLOOR = date(1990, 1, 1)


def parse_money(value: Optional[str]) -> Optional[Decimal]:
    """Parse a string money amount to Decimal.

    Returns None for empty/whitespace/None/unparseable input.
    Never returns float. Preserves sign (negative amounts allowed).
    """
    if value is None:
        return None
    stripped = str(value).strip()
    if not stripped:
        return None
    try:
        return Decimal(stripped)
    except (InvalidOperation, ValueError):
        return None


def parse_dos(value: Optional[str]) -> Optional[date]:
    """Parse an ISO-8601 date string (YYYY-MM-DD) to a date.

    Valid range: [1990-01-01, date.today()] inclusive.
    Returns None for empty/None/unparseable/out-of-range input.
    Uses date.today() -- NOT datetime.utcnow().
    """
    if value is None:
        return None
    stripped = str(value).strip()
    if not stripped:
        return None
    try:
        parsed = date.fromisoformat(stripped)
    except ValueError:
        return None
    today = date.today()
    if parsed < _DOS_FLOOR or parsed > today:
        return None
    return parsed
