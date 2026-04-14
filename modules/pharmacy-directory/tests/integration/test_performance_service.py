"""Integration tests for PerformanceService."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import Pharmacy, PharmacyPerformanceSnapshot
from src.services.performance import PerformanceService


class TestPerformanceService:
    @pytest.mark.asyncio
    async def test_upsert_snapshot_creates_record(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy
    ) -> None:
        svc = PerformanceService(db_session)
        snapshot = await svc.upsert_snapshot(
            pharmacy_id=pharmacy_a.id,
            period_year=2026,
            period_month=1,
            total_claims=500,
            total_dollar_volume=Decimal("25000.00"),
            unique_members_served=200,
            generic_fill_rate=Decimal("0.8500"),
        )
        assert snapshot.total_claims == 500
        assert snapshot.total_dollar_volume == Decimal("25000.00")

    @pytest.mark.asyncio
    async def test_upsert_snapshot_is_idempotent(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy
    ) -> None:
        svc = PerformanceService(db_session)
        await svc.upsert_snapshot(pharmacy_a.id, 2026, 2, total_claims=100)
        await svc.upsert_snapshot(pharmacy_a.id, 2026, 2, total_claims=200)

        stmt = select(PharmacyPerformanceSnapshot).where(
            PharmacyPerformanceSnapshot.pharmacy_id == pharmacy_a.id,
            PharmacyPerformanceSnapshot.period_year == 2026,
            PharmacyPerformanceSnapshot.period_month == 2,
        )
        result = (await db_session.execute(stmt)).scalars().all()
        assert len(result) == 1
        assert result[0].total_claims == 200

    @pytest.mark.asyncio
    async def test_total_dollar_volume_rounded_half_up(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy
    ) -> None:
        svc = PerformanceService(db_session)
        snapshot = await svc.upsert_snapshot(
            pharmacy_a.id, 2026, 3,
            total_dollar_volume=Decimal("100.005"),
        )
        assert snapshot.total_dollar_volume == Decimal("100.01")

    @pytest.mark.asyncio
    async def test_avg_claim_cost_rounded(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy
    ) -> None:
        svc = PerformanceService(db_session)
        snapshot = await svc.upsert_snapshot(
            pharmacy_a.id, 2026, 4,
            avg_claim_cost=Decimal("99.999"),
        )
        assert snapshot.avg_claim_cost == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_get_rankings_returns_sorted_list(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, pharmacy_b: Pharmacy
    ) -> None:
        svc = PerformanceService(db_session)
        await svc.upsert_snapshot(pharmacy_a.id, 2026, 5, total_claims=100)
        await svc.upsert_snapshot(pharmacy_b.id, 2026, 5, total_claims=500)

        rankings = await svc.get_rankings("total_claims", 2026, 5)
        assert rankings[0]["value"] == "500"
        assert rankings[0]["rank"] == 1

    @pytest.mark.asyncio
    async def test_get_rankings_with_null_metric_sorts_last(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, pharmacy_b: Pharmacy
    ) -> None:
        svc = PerformanceService(db_session)
        # generic_fill_rate is nullable — leave it as None for pharmacy_a
        await svc.upsert_snapshot(pharmacy_a.id, 2026, 6, total_claims=10)
        await svc.upsert_snapshot(
            pharmacy_b.id, 2026, 6, total_claims=10,
            generic_fill_rate=Decimal("0.9000"),
        )
        # ranking on generic_fill_rate — pharmacy_a has None, should be ranked last
        rankings = await svc.get_rankings("generic_fill_rate", 2026, 6)
        assert len(rankings) == 2
        ranked_ids = [r["pharmacy_id"] for r in rankings]
        assert ranked_ids[0] == str(pharmacy_b.id)
