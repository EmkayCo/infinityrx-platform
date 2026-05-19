"""Integration test: outbox row + domain row commit/rollback atomically.

R1 CONCERN 2 fix: prove single-transaction guarantees in a real domain flow.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from src.models.tables import PaymentHold, OutboxEvent
from src.outbox.event_outbox import OutboxService


def test_rollback_drops_both_rows(db, tenant_a_id):
    """Mutating PaymentHold + writing outbox, then rollback -> hold reverts AND
    no outbox row persists.

    R6 WARN-3 fix: seed the hold first (commit), then mutate + write outbox +
    rollback, then assert the hold reverted to 'active' and no outbox row exists.
    """
    hold = _seed_hold(db, tenant_a_id)
    db.commit()  # seed survives

    hold.status = "released"
    hold.released_at = datetime.now(UTC)
    OutboxService(db).write(
        event_type="payment.hold_released",
        tenant_id=uuid.UUID(tenant_a_id),
        payload={"hold_id": hold.id, "released_at": hold.released_at.isoformat()},
        ordering_key=hold.id,
        idempotency_key=f"hold:release:{hold.id}",
    )

    db.rollback()

    refreshed = db.execute(
        select(PaymentHold).where(PaymentHold.id == hold.id)
    ).scalar_one_or_none()
    outbox_row = db.execute(
        select(OutboxEvent).where(OutboxEvent.idempotency_key == f"hold:release:{hold.id}")
    ).scalar_one_or_none()
    assert refreshed is not None
    assert refreshed.status == "active"
    assert refreshed.released_at is None
    assert outbox_row is None


def test_commit_persists_both_rows(db, tenant_a_id):
    """Updating PaymentHold + writing outbox, then commit -> both persist."""
    hold = _seed_hold(db, tenant_a_id)
    db.commit()

    hold.status = "released"
    OutboxService(db).write(
        event_type="payment.hold_released",
        tenant_id=uuid.UUID(tenant_a_id),
        payload={"hold_id": hold.id},
        ordering_key=hold.id,
        idempotency_key=f"hold:release:{hold.id}",
    )
    db.commit()

    refreshed = db.execute(select(PaymentHold).where(PaymentHold.id == hold.id)).scalar_one()
    assert refreshed.status == "released"

    outbox_row = db.execute(
        select(OutboxEvent).where(OutboxEvent.idempotency_key == f"hold:release:{hold.id}")
    ).scalar_one()
    assert outbox_row.event_type == "payment.hold_released"
    assert outbox_row.status == "pending"


def _seed_hold(db, tenant_id: str) -> PaymentHold:
    from src._shim.auth import CurrentUser, set_current_user
    import uuid as _uuid
    # Place user in context so placed_by has a valid value
    h = PaymentHold(
        id=str(_uuid.uuid4()),
        tenant_id=tenant_id,
        entity_type="claim",
        entity_id=str(_uuid.uuid4()),
        placed_by=str(_uuid.uuid4()),
        amount_threshold=Decimal("100.00"),
        hold_scope="all",
        status="active",
        is_active=True,
        created_at=datetime.now(UTC),
    )
    db.add(h)
    return h
