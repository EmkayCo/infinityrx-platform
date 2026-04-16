"""Tests for pass-through ledger — CAA 2026 compliance.

The critical invariant: manufacturer_received == sponsor_passed for every entry.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.services.pass_through import PassThroughError, PassThroughService
from src.utils.money import ZERO, money


class FakeDB:
    """Minimal DB stand-in for unit tests that don't need real persistence."""

    def __init__(self):
        self._store: list = []
        self._flushed: list = []

    def add(self, obj):
        self._store.append(obj)

    def flush(self):
        self._flushed.extend(self._store)

    def query(self, model):
        return FakeQuery(self._flushed, model)


class FakeQuery:
    def __init__(self, store, model):
        self._store = store
        self._model = model
        self._filters = []

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def first(self):
        return None

    def scalar(self):
        return None


class TestPassThroughValidation:
    """Test that imbalanced pass-through entries are rejected."""

    def test_balanced_entry_accepted(self):
        """manufacturer_received == sponsor_passed → no error."""
        svc = PassThroughService(FakeDB())
        entry = svc.record_pass_through(
            tenant_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            ndc11="12345678901",
            period_month=date(2026, 1, 1),
            sponsor_id=uuid.uuid4(),
            manufacturer_received=Decimal("1500.00"),
            sponsor_passed=Decimal("1500.00"),
            rebate_category="commercial",
        )
        assert entry.manufacturer_received == Decimal("1500.00")
        assert entry.sponsor_passed == Decimal("1500.00")

    def test_imbalanced_entry_rejected(self):
        """manufacturer_received != sponsor_passed → PassThroughError."""
        svc = PassThroughService(FakeDB())
        with pytest.raises(PassThroughError, match="Pass-through imbalance"):
            svc.record_pass_through(
                tenant_id=uuid.uuid4(),
                transaction_id=uuid.uuid4(),
                ndc11="12345678901",
                period_month=date(2026, 1, 1),
                sponsor_id=uuid.uuid4(),
                manufacturer_received=Decimal("1500.00"),
                sponsor_passed=Decimal("1499.99"),
                rebate_category="commercial",
            )

    def test_one_penny_difference_rejected(self):
        """Even $0.01 difference must be rejected."""
        svc = PassThroughService(FakeDB())
        with pytest.raises(PassThroughError):
            svc.record_pass_through(
                tenant_id=uuid.uuid4(),
                transaction_id=uuid.uuid4(),
                ndc11="12345678901",
                period_month=date(2026, 1, 1),
                sponsor_id=uuid.uuid4(),
                manufacturer_received=Decimal("10000.00"),
                sponsor_passed=Decimal("10000.01"),
                rebate_category="commercial",
            )

    def test_zero_amounts_balanced(self):
        """Zero pass-through (BFSF-only contract) is valid."""
        svc = PassThroughService(FakeDB())
        entry = svc.record_pass_through(
            tenant_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            ndc11="12345678901",
            period_month=date(2026, 1, 1),
            sponsor_id=uuid.uuid4(),
            manufacturer_received=Decimal("0.00"),
            sponsor_passed=Decimal("0.00"),
            rebate_category="commercial",
        )
        assert entry.manufacturer_received == ZERO
        assert entry.sponsor_passed == ZERO

    def test_entry_has_hash_chain(self):
        """Every entry must have prev_hash and entry_hash set."""
        svc = PassThroughService(FakeDB())
        entry = svc.record_pass_through(
            tenant_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            ndc11="12345678901",
            period_month=date(2026, 1, 1),
            sponsor_id=uuid.uuid4(),
            manufacturer_received=Decimal("500.00"),
            sponsor_passed=Decimal("500.00"),
            rebate_category="formulary_access",
        )
        assert len(entry.prev_hash) == 64
        assert len(entry.entry_hash) == 64

    def test_large_amounts_precise(self):
        """Verify billion-dollar pass-through stays precise."""
        svc = PassThroughService(FakeDB())
        big = Decimal("1234567890.12")
        entry = svc.record_pass_through(
            tenant_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            ndc11="12345678901",
            period_month=date(2026, 1, 1),
            sponsor_id=uuid.uuid4(),
            manufacturer_received=big,
            sponsor_passed=big,
            rebate_category="commercial",
        )
        assert entry.manufacturer_received == big
        assert entry.sponsor_passed == big
