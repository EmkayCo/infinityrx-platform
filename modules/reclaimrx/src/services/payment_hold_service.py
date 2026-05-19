"""Payment hold service — prepay hold on entities under investigation."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src._shim.events import publish
from src.models.tables import PaymentHold
from src.outbox.event_outbox import OutboxService
from src.utils.money import money


def _now() -> datetime:
    return datetime.now(UTC)


class HoldInvestigationMismatchError(ValueError):
    """Hold investigation_id does not match caller-supplied investigation_id."""


class PaymentHoldService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def place_hold(
        self,
        *,
        tenant_id: uuid.UUID,
        entity_type: str,
        entity_id: str,
        entity_name: str | None,
        placed_by: uuid.UUID,
        hold_scope: str = "all",
        investigation_id: str | None = None,
        rule_filter: dict | None = None,
        amount_threshold: Decimal | None = None,
        expires_at: datetime | None = None,
    ) -> PaymentHold:
        safe_threshold = money(amount_threshold) if amount_threshold is not None else None

        hold = PaymentHold(
            tenant_id=str(tenant_id),
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            investigation_id=investigation_id,
            hold_scope=hold_scope,
            rule_filter=rule_filter,
            amount_threshold=safe_threshold,
            placed_by=str(placed_by),
            placed_at=_now(),
            expires_at=expires_at,
            is_active=True,
        )
        self._session.add(hold)
        self._session.flush()

        publish(
            "fwa.payment_hold_placed",
            {
                "tenant_id": str(tenant_id),
                "hold_id": hold.id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_name": entity_name,
                "hold_scope": hold_scope,
                "investigation_id": investigation_id,
                "placed_by": str(placed_by),
                "placed_at": hold.placed_at.isoformat(),
            },
        )
        return hold

    def release_hold(
        self,
        *,
        tenant_id: uuid.UUID,
        hold_id: str,
        released_by: uuid.UUID,
        reason: str,
        investigation_id: str | None = None,
    ) -> tuple[dict, bool]:
        """Release a payment hold with 3-case idempotency.

        Returns:
            (result_dict, is_replay) where is_replay is True for Case A.

        Raises:
            ValueError("NOT_FOUND"): hold not found for tenant.
            HoldInvestigationMismatchError: investigation_id mismatch.
            ValueError("HOLD_NOT_ACTIVE:{status}"): Case C.
            ValueError("ALREADY_RELEASED:..."): Case B conflict.
        """
        hold = self._session.execute(
            select(PaymentHold).where(
                PaymentHold.id == hold_id,
                PaymentHold.tenant_id == str(tenant_id),
            )
        ).scalar_one_or_none()
        if hold is None:
            raise ValueError("NOT_FOUND")

        # investigation_id cross-check
        if investigation_id is not None and hold.investigation_id is not None:
            if str(hold.investigation_id) != str(investigation_id):
                raise HoldInvestigationMismatchError(
                    f"Hold {hold_id} belongs to investigation {hold.investigation_id}, "
                    f"not {investigation_id}"
                )

        # Case C: hold not active and not released
        if hold.status not in ("active", "released"):
            raise ValueError(f"HOLD_NOT_ACTIVE:{hold.status}")

        # Case A/B: hold already released
        if hold.status == "released":
            same_actor = str(hold.released_by) == str(released_by)
            same_reason = hold.release_reason == reason
            if same_actor and same_reason:
                # Case A: idempotent replay
                return {
                    "id": hold.id,
                    "status": "released",
                    "released_by": str(hold.released_by),
                    "released_at": hold.released_at.isoformat() if hold.released_at else None,
                    "idempotent_replay": True,
                }, True
            # Case B: conflict
            raise ValueError(
                f"ALREADY_RELEASED:{hold.released_by}:"
                f"{hold.released_at.isoformat() if hold.released_at else ''}"
            )

        # Normal release (hold.status == "active")
        now = _now()
        hold.status = "released"
        hold.is_active = False
        hold.released_by = str(released_by)
        hold.released_at = now
        hold.release_reason = reason
        self._session.flush()

        OutboxService(self._session).write(
            event_type="payment.hold_released",
            tenant_id=tenant_id,
            idempotency_key=f"hold:release:{hold_id}",
            ordering_key=hold_id,
            payload={
                "hold_id": hold_id,
                "tenant_id": str(tenant_id),
                "entity_type": hold.entity_type,
                "entity_id": hold.entity_id,
                "release_reason": reason,
                "released_by": str(released_by),
                "released_at": now.isoformat(),
            },
        )

        return {
            "id": hold.id,
            "status": "released",
            "released_by": str(released_by),
            "released_at": now.isoformat(),
            "idempotent_replay": False,
        }, False

    def list_active_holds(
        self,
        *,
        tenant_id: uuid.UUID,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> list[PaymentHold]:
        stmt = select(PaymentHold).where(
            PaymentHold.tenant_id == str(tenant_id),
            PaymentHold.is_active.is_(True),
        )
        if entity_type:
            stmt = stmt.where(PaymentHold.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(PaymentHold.entity_id == entity_id)
        return list(self._session.execute(stmt).scalars())

    def _get_active_or_raise(self, tenant_id: uuid.UUID, hold_id: str) -> PaymentHold:
        hold = self._session.execute(
            select(PaymentHold).where(
                PaymentHold.id == hold_id,
                PaymentHold.tenant_id == str(tenant_id),
            )
        ).scalar_one_or_none()
        if hold is None:
            raise ValueError(f"Hold {hold_id} not found for tenant {tenant_id}")
        return hold
