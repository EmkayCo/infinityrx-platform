"""Unit tests for JournalEntry hash-chain logic (SP-1 Plan D Task 3).

Covers:
  - compute_entry_hash() produces correct SHA-256 hex
  - chain integrity: hash[i].prev_hash == hash[i-1].entry_hash
  - chain break detection: tamper with row[1].amount -> row[2].prev_hash mismatch
  - first entry has prev_hash == None
  - canonical_amount rounds with ROUND_HALF_UP
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from types import SimpleNamespace

import pytest

# ---------------------------------------------------------------------------
# Import the helpers directly from the migration module.
# The migration lives in alembic/versions/ which is not on the default path;
# we add it so the import works without executing any alembic machinery.
# ---------------------------------------------------------------------------

import sys
from pathlib import Path

_ALEMBIC_VERSIONS = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions"
)
if str(_ALEMBIC_VERSIONS) not in sys.path:
    sys.path.insert(0, str(_ALEMBIC_VERSIONS))

# Import the helpers from the migration file directly.
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "migration_0006",
    _ALEMBIC_VERSIONS / "0006_add_journal_hash_chain.py",
)
_mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_compute_entry_hash = _mod._compute_entry_hash
_canonical_amount = _mod._canonical_amount

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _make_row(
    *,
    amount: Decimal = Decimal("100.00"),
    entry_type: str = "ap_created",
    category: str = "claims_payable",
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
    tenant_id: uuid.UUID = _TENANT,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        entry_type=entry_type,
        amount=amount,
        category=category,
        reference_type=reference_type,
        reference_id=reference_id,
        created_at=created_at or datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC),
    )


def _naive_iso(dt) -> str:
    """Mirror _naive_utc_iso from migration 0006 / journal.py."""
    if dt is None:
        return ""
    if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
        from datetime import timezone as _tz
        dt = dt.astimezone(_tz.utc).replace(tzinfo=None)
    return dt.isoformat()


def _expected_hash(row, prev_hash: str | None) -> str:
    ph = prev_hash or ""
    ref_type = row.reference_type or ""
    ref_id = str(row.reference_id) if row.reference_id else ""
    created_iso = _naive_iso(row.created_at)
    amount_str = str(
        Decimal(str(row.amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    canonical = "|".join([
        str(row.tenant_id),
        str(row.entry_type),
        amount_str,
        str(row.category),
        ref_type,
        ref_id,
        created_iso,
        ph,
    ])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Tests: canonical_amount
# ---------------------------------------------------------------------------


class TestCanonicalAmount:
    def test_basic_two_decimal(self) -> None:
        assert _canonical_amount(Decimal("100.00")) == "100.00"

    def test_rounds_half_up(self) -> None:
        # 100.005 rounds UP to 100.01 with ROUND_HALF_UP
        result = _canonical_amount(Decimal("100.005"))
        assert result == "100.01"

    def test_integer_input(self) -> None:
        assert _canonical_amount(100) == "100.00"

    def test_string_input(self) -> None:
        assert _canonical_amount("50.50") == "50.50"


# ---------------------------------------------------------------------------
# Tests: compute_entry_hash
# ---------------------------------------------------------------------------


class TestComputeEntryHash:
    def test_returns_64_hex_chars(self) -> None:
        row = _make_row()
        h = _compute_entry_hash(row, None)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_first_entry_no_prev_hash(self) -> None:
        row = _make_row()
        h = _compute_entry_hash(row, None)
        expected = _expected_hash(row, None)
        assert h == expected

    def test_deterministic_same_input(self) -> None:
        row = _make_row()
        assert _compute_entry_hash(row, "abc") == _compute_entry_hash(row, "abc")

    def test_different_prev_hash_produces_different_result(self) -> None:
        row = _make_row()
        h1 = _compute_entry_hash(row, None)
        h2 = _compute_entry_hash(row, "deadbeef" * 8)
        assert h1 != h2

    def test_different_amount_produces_different_result(self) -> None:
        row1 = _make_row(amount=Decimal("100.00"))
        row2 = _make_row(
            amount=Decimal("200.00"),
            created_at=row1.created_at,
        )
        # Same prev_hash, different amounts -> different hashes
        h1 = _compute_entry_hash(row1, None)
        h2 = _compute_entry_hash(row2, None)
        assert h1 != h2


# ---------------------------------------------------------------------------
# Tests: chain integrity (3 entries)
# ---------------------------------------------------------------------------


class TestChainIntegrity:
    def test_chain_of_three_entries(self) -> None:
        """hash[i].prev_hash == entry_hash[i-1]; first entry prev_hash is None."""
        rows = [
            _make_row(amount=Decimal("100.00"), created_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)),
            _make_row(amount=Decimal("200.00"), created_at=datetime(2026, 1, 15, 11, 0, 0, tzinfo=UTC)),
            _make_row(amount=Decimal("300.00"), created_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)),
        ]

        hashes: list[str] = []
        prev: str | None = None
        for row in rows:
            h = _compute_entry_hash(row, prev)
            hashes.append(h)
            prev = h

        # Verify chain: recompute each and confirm linkage
        prev = None
        for i, row in enumerate(rows):
            expected = _expected_hash(row, prev)
            assert hashes[i] == expected, f"Hash mismatch at index {i}"
            prev = hashes[i]

    def test_first_entry_prev_hash_none(self) -> None:
        row = _make_row()
        h = _compute_entry_hash(row, None)
        # Recompute with explicit empty prev_hash -- must match
        h_check = _expected_hash(row, None)
        assert h == h_check


# ---------------------------------------------------------------------------
# Tests: chain break detection
# ---------------------------------------------------------------------------


class TestChainBreakDetection:
    def test_tamper_with_row1_amount_breaks_row2_prev_hash(self) -> None:
        """Simulate tampering with row[1].amount and verify row[2].prev_hash mismatches.

        This mirrors what the POST /verify-chain endpoint does:
        - Recompute each hash from scratch.
        - Compare recomputed hash to *stored* hash.
        - Compare stored prev_hash[i] to recomputed hash[i-1].
        A tampered row[1].amount makes its recomputed hash != stored hash,
        which means row[2]'s stored prev_hash != the recomputed hash of row[1].
        """
        rows = [
            _make_row(amount=Decimal("100.00"), created_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)),
            _make_row(amount=Decimal("200.00"), created_at=datetime(2026, 1, 15, 11, 0, 0, tzinfo=UTC)),
            _make_row(amount=Decimal("300.00"), created_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)),
        ]

        # Build original chain: stored hashes + stored prev_hashes
        stored_hashes: list[str] = []
        stored_prev: list[str | None] = []
        prev: str | None = None
        for row in rows:
            stored_prev.append(prev)
            h = _compute_entry_hash(row, prev)
            stored_hashes.append(h)
            prev = h

        # Tamper: change row[1].amount to something different
        tampered_rows = list(rows)
        tampered_rows[1] = SimpleNamespace(
            **{**vars(rows[1]), "amount": Decimal("999.99")}
        )

        # Simulate verifier: recompute from row[0] onward
        recomputed_prev: str | None = None
        broken_at: int | None = None
        for i, row in enumerate(tampered_rows):
            recomputed_hash = _compute_entry_hash(row, recomputed_prev)
            # Check: stored hash must match recomputed hash
            if recomputed_hash != stored_hashes[i]:
                broken_at = i
                break
            # Check: stored prev_hash must match what we computed as prev
            if stored_prev[i] != recomputed_prev:
                broken_at = i
                break
            recomputed_prev = recomputed_hash

        # Tamper was on row[1] -> broken_at should be 1
        assert broken_at == 1

    def test_untampered_chain_verifies_clean(self) -> None:
        rows = [
            _make_row(amount=Decimal("10.00"), created_at=datetime(2026, 2, 1, 8, 0, 0, tzinfo=UTC)),
            _make_row(amount=Decimal("20.00"), created_at=datetime(2026, 2, 1, 9, 0, 0, tzinfo=UTC)),
            _make_row(amount=Decimal("30.00"), created_at=datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)),
        ]
        stored_hashes: list[str] = []
        stored_prev: list[str | None] = []
        prev: str | None = None
        for row in rows:
            stored_prev.append(prev)
            h = _compute_entry_hash(row, prev)
            stored_hashes.append(h)
            prev = h

        # Verify: should find no break
        recomputed_prev: str | None = None
        broken_at = None
        for i, row in enumerate(rows):
            recomputed_hash = _compute_entry_hash(row, recomputed_prev)
            if recomputed_hash != stored_hashes[i]:
                broken_at = i
                break
            if stored_prev[i] != recomputed_prev:
                broken_at = i
                break
            recomputed_prev = recomputed_hash

        assert broken_at is None
