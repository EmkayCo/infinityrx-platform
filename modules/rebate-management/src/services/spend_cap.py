"""Spend cap guarantee tracking service.

Tracks actual spend vs guaranteed ceiling. Calculates refunds when
actuals exceed ceiling per contract terms.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from src.models.tables import SpendCapActual, SpendCapGuarantee
from src.utils.money import ZERO, money

FOUR_PLACES = Decimal("0.0001")
PCT_80 = Decimal("0.80")
PCT_90 = Decimal("0.90")
PCT_100 = Decimal("1.00")


class SpendCapService:
    """Tracks and enforces spend cap guarantees."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_guarantee(
        self,
        tenant_id: uuid.UUID,
        contract_id: uuid.UUID,
        sponsor_id: uuid.UUID,
        cap_type: str,
        guarantee_ceiling: Decimal,
        guarantee_period_start: date,
        guarantee_period_end: date,
        program_id: uuid.UUID | None = None,
        refund_terms: dict | None = None,
    ) -> SpendCapGuarantee:
        now = datetime.now(UTC)
        guarantee = SpendCapGuarantee(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            contract_id=contract_id,
            sponsor_id=sponsor_id,
            program_id=program_id,
            cap_type=cap_type,
            guarantee_ceiling=money(guarantee_ceiling),
            guarantee_period_start=guarantee_period_start,
            guarantee_period_end=guarantee_period_end,
            refund_terms=refund_terms,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self._db.add(guarantee)
        self._db.flush()
        return guarantee

    def record_monthly_actual(
        self,
        tenant_id: uuid.UUID,
        guarantee_id: uuid.UUID,
        tracking_month: date,
        actual_spend: Decimal,
    ) -> tuple[SpendCapActual, list[str]]:
        """Record actual spend for a month and check alert thresholds.

        Returns:
            Tuple of (SpendCapActual record, list of alert strings fired).
        """
        guarantee = (
            self._db.query(SpendCapGuarantee)
            .filter(
                SpendCapGuarantee.tenant_id == tenant_id,
                SpendCapGuarantee.id == guarantee_id,
            )
            .first()
        )
        if guarantee is None:
            raise ValueError(f"SpendCapGuarantee {guarantee_id} not found")

        # Compute cumulative spend (all months up to and including this one)
        from sqlalchemy import func
        prev_cumulative = (
            self._db.query(func.sum(SpendCapActual.actual_spend))
            .filter(
                SpendCapActual.tenant_id == tenant_id,
                SpendCapActual.guarantee_id == guarantee_id,
                SpendCapActual.tracking_month < tracking_month,
            )
            .scalar()
        )
        prev_cum = Decimal(str(prev_cumulative)) if prev_cumulative else ZERO
        actual = money(actual_spend)
        cumulative = money(prev_cum + actual)
        ceiling = guarantee.guarantee_ceiling
        utilization_pct = (cumulative / ceiling).quantize(
            FOUR_PLACES, rounding=ROUND_HALF_UP
        ) if ceiling > ZERO else ZERO

        # Refund calculation
        refund_owed = ZERO
        if cumulative > ceiling:
            refund_owed = money(cumulative - ceiling)

        # Check alert thresholds
        alerts: list[str] = []
        alert_80 = False
        alert_90 = False
        alert_100 = False

        # Check if thresholds were already fired for this guarantee
        prev_actuals = (
            self._db.query(SpendCapActual)
            .filter(
                SpendCapActual.tenant_id == tenant_id,
                SpendCapActual.guarantee_id == guarantee_id,
                SpendCapActual.tracking_month < tracking_month,
            )
            .all()
        )
        already_80 = any(a.alert_80_fired for a in prev_actuals)
        already_90 = any(a.alert_90_fired for a in prev_actuals)
        already_100 = any(a.alert_100_fired for a in prev_actuals)

        if not already_80 and utilization_pct >= PCT_80:
            alert_80 = True
            alerts.append("spend_cap.threshold_80_exceeded")
        if not already_90 and utilization_pct >= PCT_90:
            alert_90 = True
            alerts.append("spend_cap.threshold_90_exceeded")
        if not already_100 and utilization_pct >= PCT_100:
            alert_100 = True
            alerts.append("spend_cap.threshold_100_exceeded")

        now = datetime.now(UTC)
        # Upsert actual record
        existing = (
            self._db.query(SpendCapActual)
            .filter(
                SpendCapActual.tenant_id == tenant_id,
                SpendCapActual.guarantee_id == guarantee_id,
                SpendCapActual.tracking_month == tracking_month,
            )
            .first()
        )
        if existing:
            existing.actual_spend = actual
            existing.cumulative_spend = cumulative
            existing.ceiling_at_time = ceiling
            existing.utilization_pct = utilization_pct
            existing.refund_owed = refund_owed
            existing.alert_80_fired = existing.alert_80_fired or alert_80
            existing.alert_90_fired = existing.alert_90_fired or alert_90
            existing.alert_100_fired = existing.alert_100_fired or alert_100
            self._db.flush()
            return existing, alerts

        record = SpendCapActual(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            guarantee_id=guarantee_id,
            tracking_month=tracking_month,
            actual_spend=actual,
            cumulative_spend=cumulative,
            ceiling_at_time=ceiling,
            utilization_pct=utilization_pct,
            refund_owed=refund_owed,
            alert_80_fired=alert_80,
            alert_90_fired=alert_90,
            alert_100_fired=alert_100,
            created_at=now,
        )
        self._db.add(record)
        self._db.flush()
        return record, alerts

    def get_status(
        self, tenant_id: uuid.UUID, guarantee_id: uuid.UUID
    ) -> dict:
        """Return current status of a spend cap guarantee."""
        guarantee = (
            self._db.query(SpendCapGuarantee)
            .filter(
                SpendCapGuarantee.tenant_id == tenant_id,
                SpendCapGuarantee.id == guarantee_id,
            )
            .first()
        )
        if guarantee is None:
            raise ValueError(f"SpendCapGuarantee {guarantee_id} not found")

        from sqlalchemy import func
        agg = (
            self._db.query(
                func.sum(SpendCapActual.actual_spend).label("total_spend"),
                func.sum(SpendCapActual.refund_owed).label("total_refund"),
            )
            .filter(
                SpendCapActual.tenant_id == tenant_id,
                SpendCapActual.guarantee_id == guarantee_id,
            )
            .first()
        )

        total_spend = money(
            Decimal(str(agg.total_spend)) if agg.total_spend else ZERO
        )
        total_refund = money(
            Decimal(str(agg.total_refund)) if agg.total_refund else ZERO
        )
        ceiling = guarantee.guarantee_ceiling
        utilization = (total_spend / ceiling).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        ) if ceiling > ZERO else ZERO

        return {
            "guarantee_id": str(guarantee_id),
            "ceiling": str(ceiling),
            "total_spend": str(total_spend),
            "total_refund_owed": str(total_refund),
            "utilization_pct": str(utilization),
            "is_active": guarantee.is_active,
            "period_start": guarantee.guarantee_period_start.isoformat(),
            "period_end": guarantee.guarantee_period_end.isoformat(),
        }
