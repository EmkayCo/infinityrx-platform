"""Tamper-evident hash chain for rebate ledger entries.

Algorithm
---------
entry_hash = sha256(prev_hash || canonical_json(entry_fields))

canonical_json: fields sorted alphabetically, Decimal serialized as str,
datetime as ISO-8601, UUID as str. This makes the digest deterministic
regardless of insertion order on the Python dict.

Sentinel
--------
The genesis entry (first in a chain) uses:
    prev_hash = "0" * 64  (64 zero hex chars)

Verification
------------
Walk the chain in insertion order; for each entry:
    expected = compute_entry_hash(prev_hash, entry_fields)
    assert entry.entry_hash == expected

Any tampering with any field in any entry will break all subsequent hashes.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

GENESIS_HASH: str = "0" * 64


def _canonical_default(obj: object) -> str:
    """JSON serializer for types not handled natively."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Cannot serialize type {type(obj).__name__} for hash chain")


def canonical_json(fields: dict) -> str:
    """Produce deterministic JSON from a dict — keys sorted, types normalized."""
    return json.dumps(fields, sort_keys=True, default=_canonical_default)


def compute_entry_hash(prev_hash: str, entry_fields: dict) -> str:
    """Return the sha256 hex digest of prev_hash || canonical_json(entry_fields).

    Args:
        prev_hash:     The ``entry_hash`` of the preceding entry (or GENESIS_HASH
                       for the first entry in the chain).
        entry_fields:  Dict of the entry's data fields — everything that should
                       be covered by the integrity guarantee (amounts, dates,
                       IDs, etc.).  Do NOT include ``prev_hash`` or
                       ``entry_hash`` themselves in ``entry_fields``.

    Returns:
        64-character lowercase hex digest.
    """
    payload = prev_hash + canonical_json(entry_fields)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_chain(entries: list[dict]) -> bool:
    """Verify the integrity of a list of ordered chain entries.

    Each entry dict must have ``prev_hash`` and ``entry_hash`` keys plus
    all data fields.  The data fields to rehash are everything except
    ``prev_hash`` and ``entry_hash``.

    Returns:
        True if the chain is unbroken.

    Raises:
        ValueError: on the first entry whose hash does not match, with a
                    descriptive message including the entry index.
    """
    expected_prev = GENESIS_HASH
    for i, entry in enumerate(entries):
        entry_prev = entry.get("prev_hash", "")
        if entry_prev != expected_prev:
            raise ValueError(
                f"Chain break at entry {i}: expected prev_hash={expected_prev!r} "
                f"but found {entry_prev!r}"
            )
        fields = {k: v for k, v in entry.items() if k not in ("prev_hash", "entry_hash")}
        expected_hash = compute_entry_hash(entry_prev, fields)
        stored_hash = entry.get("entry_hash", "")
        if stored_hash != expected_hash:
            raise ValueError(
                f"Hash mismatch at entry {i}: expected {expected_hash!r} "
                f"but stored {stored_hash!r}"
            )
        expected_prev = stored_hash
    return True
