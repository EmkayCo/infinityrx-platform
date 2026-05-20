"""Shared journal entry hash-chain helpers.

Used by both:
  - the journal_router's verify-chain endpoint (recompute on read)
  - the JournalEntry before_insert event listener (auto-compute on write)
  - the alembic 0006 backfill migration

Algorithm: SHA-256 of pipe-delimited canonical row representation:
  tenant_id | entry_type | amount(2dp ROUND_HALF_UP) | category
  | reference_type | reference_id | created_at(naive UTC ISO) | prev_hash

Naive UTC ISO is used because SQLite drops tzinfo on SELECT while Postgres
preserves it; stripping tzinfo before formatting makes hashes stable across
both drivers.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


def canonical_amount(amount: Any) -> str:
    """Quantize to 2dp ROUND_HALF_UP and return as string."""
    return str(Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def naive_utc_iso(dt: datetime | None) -> str:
    """Return a timezone-naive UTC ISO string for *dt* (driver-stable)."""
    if dt is None:
        return ""
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.isoformat()


def compute_entry_hash(entry: Any, prev_hash: str | None) -> str:
    """SHA-256 of the pipe-delimited canonical representation of *entry*.

    *entry* must expose: tenant_id, entry_type, amount, category,
    reference_type, reference_id, created_at.
    """
    ph = prev_hash or ""
    ref_type = entry.reference_type or ""
    ref_id = str(entry.reference_id) if entry.reference_id else ""
    created_iso = naive_utc_iso(entry.created_at)
    canonical = "|".join([
        str(entry.tenant_id),
        str(entry.entry_type),
        canonical_amount(entry.amount),
        str(entry.category),
        ref_type,
        ref_id,
        created_iso,
        ph,
    ])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
