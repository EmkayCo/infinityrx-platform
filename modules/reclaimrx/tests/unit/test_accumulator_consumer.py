"""Unit tests for accumulator_consumer.

Tests the TWO A3 pattern detectors (`sudden_spike`, `multi_payer_convergence`)
plus idempotency + tenant_id consistency. `reset_evasion` and
`threshold_oscillation` detectors are explicitly deferred to B11 per the
scope note above; their tests will be added in B11/follow-on/accumulator-patterns-3-4.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.consumers.accumulator_consumer import AccumulatorConsumer, AccumulatorTenantMismatchWarning
from src.models.tables import AccumulatorAnomaly, Investigation  # added by Plan A1


def _make_payload(member_id: str, tenant_id: str, pattern: dict, envelope_tenant_id: str | None = None) -> dict:
    return {
        "envelope_tenant_id": envelope_tenant_id or tenant_id,
        "member_id": member_id,
        "tenant_id": tenant_id,
        "accumulator_type": "oop",
        "period": "2026-Q2",
        "amounts": {"oop": "500.00", "deductible": "200.00"},
        "source_payer_id": None,
        **pattern,
    }


class TestAccumulatorConsumerTenantConsistency:
    def test_tenant_mismatch_does_not_write_row(self):
        db = MagicMock()
        consumer = AccumulatorConsumer(db)
        member_id = str(uuid.uuid4())
        with pytest.raises(AccumulatorTenantMismatchWarning):
            consumer.handle(
                idempotency_key=f"accumulator:{member_id}:2026-Q2:1234",
                payload=_make_payload(
                    member_id, tenant_id="tenant-A",
                    envelope_tenant_id="tenant-B",  # mismatch
                    pattern={},
                ),
            )
        db.add.assert_not_called()


class TestAccumulatorPatternDetectors:
    @pytest.fixture()
    def db(self):
        return MagicMock()

    @pytest.fixture()
    def consumer(self, db):
        return AccumulatorConsumer(db)

    def _member_and_tid(self):
        return str(uuid.uuid4()), str(uuid.uuid4())

    def test_sudden_spike_detected_when_oop_jumps(self, consumer, db):
        member_id, tid = self._member_and_tid()
        # Simulate history showing prior oop=50; new oop=500 (10x)
        with patch.object(consumer, "_load_recent_window", return_value=[
            {"oop": Decimal("50.00")} for _ in range(3)
        ]):
            consumer.handle(
                idempotency_key=f"accumulator:{member_id}:2026-Q2:9999",
                payload=_make_payload(member_id, tid, {"amounts": {"oop": "500.00", "deductible": "50.00"}}),
            )
        # AccumulatorAnomaly row added to session
        added = [c for c in db.add.call_args_list if hasattr(c.args[0], 'pattern_type')]
        assert any(row.args[0].pattern_type == "sudden_spike" for row in added)

    def test_no_anomaly_for_normal_delta(self, consumer, db):
        member_id, tid = self._member_and_tid()
        with patch.object(consumer, "_load_recent_window", return_value=[
            {"oop": Decimal("450.00")} for _ in range(3)
        ]):
            consumer.handle(
                idempotency_key=f"accumulator:{member_id}:2026-Q2:9998",
                payload=_make_payload(member_id, tid, {"amounts": {"oop": "500.00", "deductible": "50.00"}}),
            )
        added = [c for c in db.add.call_args_list if hasattr(c.args[0], 'pattern_type')]
        assert len(added) == 0

    def test_multi_payer_convergence_detected(self, consumer, db):
        member_id, tid = self._member_and_tid()
        with patch.object(consumer, "_load_recent_window", return_value=[
            {"oop": Decimal("100.00"), "source_payer_id": f"payer-{i}"}
            for i in range(4)  # 4 distinct payers in window → convergence
        ]):
            consumer.handle(
                idempotency_key=f"accumulator:{member_id}:2026-Q2:8888",
                payload=_make_payload(member_id, tid, {
                    "amounts": {"oop": "100.00", "deductible": "50.00"},
                    "source_payer_id": "payer-new",
                }),
            )
        added = [c for c in db.add.call_args_list if hasattr(c.args[0], 'pattern_type')]
        assert any(row.args[0].pattern_type == "multi_payer_convergence" for row in added)

    def test_investigation_opened_for_high_severity(self, consumer, db):
        """When anomaly detected, auto-open Investigation."""
        member_id, tid = self._member_and_tid()
        with patch.object(consumer, "_load_recent_window", return_value=[
            {"oop": Decimal("50.00")} for _ in range(3)
        ]):
            consumer.handle(
                idempotency_key=f"accumulator:{member_id}:2026-Q2:7777",
                payload=_make_payload(member_id, tid, {"amounts": {"oop": "5000.00", "deductible": "100.00"}}),
            )
        added_types = [type(c.args[0]).__name__ for c in db.add.call_args_list]
        assert "AccumulatorAnomaly" in added_types
        assert "Investigation" in added_types
