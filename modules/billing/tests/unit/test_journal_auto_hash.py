"""SP-1 Plan D B4 -- JournalEntry.before_insert auto-computes entry_hash.

The 0007 migration drops the server_default for entry_hash; without the
event listener wired in tables.py, INSERTs without an explicit entry_hash
would fail the NOT NULL constraint. These tests verify the listener fires
and the resulting hash is the canonical computation from journal_hash.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.models.journal_hash import compute_entry_hash
from src.models.tables import JournalEntry


@pytest.fixture()
def _session(db_session):
    return db_session


def _make_entry(tenant_id: uuid.UUID, **overrides) -> JournalEntry:
    fields = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "entry_date": datetime(2026, 5, 17, tzinfo=UTC).date(),
        "entry_timestamp": datetime(2026, 5, 17, 10, 0, 0, tzinfo=UTC),
        "entry_type": "payment_out",
        "amount": Decimal("123.45"),
        "category": "ap",
        "description": "test entry",
        "created_at": datetime(2026, 5, 17, 10, 0, 0, tzinfo=UTC),
    }
    fields.update(overrides)
    return JournalEntry(**fields)


class TestJournalEntryAutoHash:
    def test_insert_without_explicit_hash_auto_computes(self, _session):
        tenant = uuid.uuid4()
        entry = _make_entry(tenant)
        assert entry.entry_hash in ("", None)
        _session.add(entry)
        _session.flush()
        assert entry.entry_hash != ""
        assert len(entry.entry_hash) == 64

    def test_insert_hash_matches_canonical(self, _session):
        tenant = uuid.uuid4()
        entry = _make_entry(tenant)
        _session.add(entry)
        _session.flush()
        expected = compute_entry_hash(entry, prev_hash=None)
        assert entry.entry_hash == expected

    def test_explicit_hash_preserved(self, _session):
        tenant = uuid.uuid4()
        entry = _make_entry(tenant, entry_hash="a" * 64)
        _session.add(entry)
        _session.flush()
        assert entry.entry_hash == "a" * 64

    def test_chained_insert_includes_prev_hash(self, _session):
        tenant = uuid.uuid4()
        first = _make_entry(tenant)
        _session.add(first)
        _session.flush()

        second = _make_entry(
            tenant,
            amount=Decimal("50.00"),
            prev_hash=first.entry_hash,
        )
        _session.add(second)
        _session.flush()

        expected = compute_entry_hash(second, prev_hash=first.entry_hash)
        assert second.entry_hash == expected
