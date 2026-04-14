"""Pharmacy performance metrics service.

Ingests metric events from billing/reclaimrx and stores monthly snapshots.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from shared.utils.money import money
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import PharmacyPerformanceSnapshot

logger = logging.getLogger("pharmacy-directory.performance")


class PerformanceService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def upsert_snapshot(
        self,
        pharmacy_id: UUID,
        period_year: int,
        period_month: int,
        total_claims: int = 0,
        total_dollar_volume: Decimal = Decimal("0.00"),
        unique_members_served: int = 0,
        generic_fill_rate: Decimal | None = None,
        reversal_rate: Decimal | None = None,
        fwa_flag_count: int = 0,
        daw_rate: Decimal | None = None,
        avg_claim_cost: Decimal | None = None,
    ) -> PharmacyPerformanceSnapshot:
        stmt = select(PharmacyPerformanceSnapshot).where(
            PharmacyPerformanceSnapshot.pharmacy_id == pharmacy_id,
            PharmacyPerformanceSnapshot.period_year == period_year,
            PharmacyPerformanceSnapshot.period_month == period_month,
        )
        result = await self._db.execute(stmt)
        snapshot = result.scalar_one_or_none()

        if snapshot is None:
            snapshot = PharmacyPerformanceSnapshot(
                pharmacy_id=pharmacy_id,
                period_year=period_year,
                period_month=period_month,
            )
            self._db.add(snapshot)

        snapshot.total_claims = total_claims
        snapshot.total_dollar_volume = money(total_dollar_volume)
        snapshot.unique_members_served = unique_members_served
        snapshot.generic_fill_rate = generic_fill_rate
        snapshot.reversal_rate = reversal_rate
        snapshot.fwa_flag_count = fwa_flag_count
        snapshot.daw_rate = daw_rate
        snapshot.avg_claim_cost = money(avg_claim_cost) if avg_claim_cost is not None else None

        await self._db.flush()
        return snapshot

    async def get_rankings(
        self,
        metric: str,
        period_year: int,
        period_month: int,
        limit: int = 20,
    ) -> list[dict]:
        stmt = select(PharmacyPerformanceSnapshot).where(
            PharmacyPerformanceSnapshot.period_year == period_year,
            PharmacyPerformanceSnapshot.period_month == period_month,
        )
        result = await self._db.execute(stmt)
        snapshots = result.scalars().all()

        def _metric_value(s: PharmacyPerformanceSnapshot) -> float:
            val = getattr(s, metric, None)
            if val is None:
                return -1.0
            return float(val)

        ranked = sorted(snapshots, key=_metric_value, reverse=True)[:limit]
        return [
            {
                "pharmacy_id": str(s.pharmacy_id),
                "period_year": s.period_year,
                "period_month": s.period_month,
                "metric": metric,
                "value": str(getattr(s, metric)) if getattr(s, metric) is not None else None,
                "rank": idx + 1,
            }
            for idx, s in enumerate(ranked)
        ]
