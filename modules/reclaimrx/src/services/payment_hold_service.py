"""Payment hold service — prepay hold on entities under investigation."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src._shim.events import publish
from src.models.tables import PaymentHold
from src.utils.money import money


def _now() -> datetime:
    return datetime.now(UTC)


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
    ) -> PaymentHold:
        hold = self._get_active_or_raise(tenant_id, hold_id)
        hold.is_active = False
        hold.released_by = str(released_by)
        hold.released_at = _now()
        hold.release_reason = reason
        self._session.flush()

        publish(
            "fwa.payment_hold_released",
            {
                "tenant_id": str(tenant_id),
                "hold_id": hold_id,
                "entity_type": hold.entity_type,
                "entity_id": hold.entity_id,
                "release_reason": reason,
                "released_by": str(released_by),
                "released_at": hold.released_at.isoformat() if hold.released_at else None,
            },
        )
        return hold

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
