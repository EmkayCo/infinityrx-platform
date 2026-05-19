"""Unit tests for OutboxService — transactional outbox writer.

TDD: these tests MUST FAIL before Task 2 implements the service.
Run: pytest modules/reclaimrx/tests/unit/test_outbox_service.py -v
Expected: ImportError or AttributeError (OutboxService does not exist yet).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from unittest.mock import MagicMock, patch

from src.outbox.event_outbox import OutboxService  # FAILS until Task 2


class TestOutboxServiceWrite:
    """OutboxService.write() must persist an OutboxEvent row atomically."""

    def test_write_inserts_pending_row(self, db_session):
        """write() inserts a row with status='pending' and correct fields."""
        from src.models.tables import OutboxEvent

        svc = OutboxService(db_session)
        hold_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        svc.write(
            event_type="payment.hold_released",
            tenant_id=tenant_id,
            idempotency_key=f"hold:release:{hold_id}",
            ordering_key=str(hold_id),
            payload={
                "hold_id": str(hold_id),
                "amount": "123.45",
                "released_by": "user-sub-123",
                "reason": "duplicate billing",
                "investigation_id": str(uuid.uuid4()),
                "released_at": datetime.now(UTC).isoformat(),
            },
            source_module="reclaimrx",
        )

        row = db_session.query(OutboxEvent).filter_by(
            idempotency_key=f"hold:release:{hold_id}"
        ).one()
        assert row.status == "pending"
        assert row.event_type == "payment.hold_released"
        assert row.attempt_count == 0
        assert row.published_at is None
        assert row.last_error is None
        assert row.tenant_id == str(tenant_id)

    def test_write_stores_valid_event_envelope_json(self, db_session):
        """envelope_json stored by write() must deserialize to valid EventEnvelope."""
        import json
        from shared.events.types import EventEnvelope
        from src.models.tables import OutboxEvent

        svc = OutboxService(db_session)
        hold_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        svc.write(
            event_type="fwa.graph_run_completed",
            tenant_id=tenant_id,
            idempotency_key=f"graph_run:{hold_id}:completed",
            ordering_key=str(hold_id),
            payload={"graph_run_id": str(hold_id), "status": "completed",
                     "rings_detected": 3, "investigations_opened": 1,
                     "records_scanned": 5000, "lookback_window_days": 90,
                     "started_at": datetime.now(UTC).isoformat(),
                     "completed_at": datetime.now(UTC).isoformat(),
                     "failed_at": None, "error_code": None, "error_message": None},
            source_module="reclaimrx",
        )

        row = db_session.query(OutboxEvent).filter_by(
            idempotency_key=f"graph_run:{hold_id}:completed"
        ).one()
        envelope = EventEnvelope.from_wire(json.loads(row.envelope_json))
        assert envelope.event_type == "fwa.graph_run_completed"
        assert envelope.tenant_id == tenant_id
        assert envelope.source_module == "reclaimrx"
        assert "graph_run_id" in envelope.payload

    def test_write_idempotency_key_unique_constraint_raises(self, db_session):
        """Duplicate idempotency_key raises IntegrityError (UNIQUE constraint)."""
        import pytest
        from sqlalchemy.exc import IntegrityError

        svc = OutboxService(db_session)
        tenant_id = uuid.uuid4()
        hold_id = uuid.uuid4()
        key = f"hold:release:{hold_id}"

        svc.write(
            event_type="payment.hold_released",
            tenant_id=tenant_id,
            idempotency_key=key,
            ordering_key=str(hold_id),
            payload={"hold_id": str(hold_id)},
            source_module="reclaimrx",
        )
        db_session.flush()

        with pytest.raises(IntegrityError):
            svc.write(
                event_type="payment.hold_released",
                tenant_id=tenant_id,
                idempotency_key=key,  # same key
                ordering_key=str(hold_id),
                payload={"hold_id": str(hold_id)},
                source_module="reclaimrx",
            )
            db_session.flush()
