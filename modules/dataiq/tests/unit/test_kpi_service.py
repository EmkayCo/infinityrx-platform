"""Unit tests for real-time KPI Redis counter service.

TDD: tests written before implementation.
All Redis keys MUST be prefixed with tenant:{tenant_id}:
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from src.services.kpi import (
    KPIGranularity,
    build_kpi_key,
    increment_counter,
    increment_financial_counter,
)


class TestBuildKpiKey:
    def test_key_contains_tenant_prefix(self) -> None:
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        key = build_kpi_key(
            tenant_id=tenant_id,
            metric="claim_count",
            granularity=KPIGranularity.MINUTE,
            bucket_ts=1234567890,
        )
        assert key.startswith(f"tenant:{tenant_id}:")

    def test_key_format_matches_spec(self) -> None:
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        key = build_kpi_key(
            tenant_id=tenant_id,
            metric="claim_count",
            granularity=KPIGranularity.MINUTE,
            bucket_ts=1234567890,
        )
        # Expected: tenant:{tenant_id}:kpi:claim_count:minute:1234567890
        assert key == f"tenant:{tenant_id}:kpi:claim_count:minute:1234567890"

    def test_different_tenants_produce_different_keys(self) -> None:
        tid1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
        tid2 = uuid.UUID("00000000-0000-0000-0000-000000000002")
        key1 = build_kpi_key(tid1, "claim_count", KPIGranularity.MINUTE, 1234567890)
        key2 = build_kpi_key(tid2, "claim_count", KPIGranularity.MINUTE, 1234567890)
        assert key1 != key2

    def test_different_metrics_produce_different_keys(self) -> None:
        tid = uuid.UUID("00000000-0000-0000-0000-000000000001")
        key1 = build_kpi_key(tid, "claim_count", KPIGranularity.MINUTE, 1234567890)
        key2 = build_kpi_key(tid, "reject_count", KPIGranularity.MINUTE, 1234567890)
        assert key1 != key2

    def test_hourly_granularity_in_key(self) -> None:
        tid = uuid.UUID("00000000-0000-0000-0000-000000000001")
        key = build_kpi_key(tid, "claim_count", KPIGranularity.HOUR, 1234567890)
        assert "hour" in key

    def test_daily_granularity_in_key(self) -> None:
        tid = uuid.UUID("00000000-0000-0000-0000-000000000001")
        key = build_kpi_key(tid, "claim_count", KPIGranularity.DAY, 1234567890)
        assert "day" in key


class TestIncrementCounter:
    @pytest.mark.asyncio
    async def test_increment_calls_incrby(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.incrby = AsyncMock(return_value=5)
        mock_redis.expire = AsyncMock()

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        await increment_counter(
            redis=mock_redis,
            tenant_id=tenant_id,
            metric="claim_count",
            bucket_ts=1234567890,
            amount=1,
        )

        mock_redis.incrby.assert_called_once()
        args = mock_redis.incrby.call_args
        key_arg = args[0][0]
        assert key_arg.startswith(f"tenant:{tenant_id}:")

    @pytest.mark.asyncio
    async def test_increment_sets_ttl_25_hours(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.incrby = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        await increment_counter(
            redis=mock_redis,
            tenant_id=tenant_id,
            metric="claim_count",
            bucket_ts=1234567890,
            amount=1,
        )

        mock_redis.expire.assert_called_once()
        args = mock_redis.expire.call_args
        ttl_arg = args[0][1]
        assert ttl_arg == 25 * 3600  # 25 hours in seconds

    @pytest.mark.asyncio
    async def test_increment_uses_incrby_not_set(self) -> None:
        """Must use INCRBY, never SET, to avoid race conditions."""
        mock_redis = AsyncMock()
        mock_redis.incrby = AsyncMock(return_value=3)
        mock_redis.expire = AsyncMock()

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        await increment_counter(
            redis=mock_redis,
            tenant_id=tenant_id,
            metric="claim_count",
            bucket_ts=1234567890,
            amount=5,
        )

        # Verify it called incrby with the amount, not set
        mock_redis.incrby.assert_called_once()
        call_args = mock_redis.incrby.call_args[0]
        assert call_args[1] == 5


class TestIncrementFinancialCounter:
    @pytest.mark.asyncio
    async def test_financial_counter_uses_hincrbyfloat_pattern(self) -> None:
        """Financial KPIs stored as string representation of Decimal."""
        mock_redis = AsyncMock()
        mock_redis.hincrbyfloat = AsyncMock(return_value="102.50")
        mock_redis.expire = AsyncMock()

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        await increment_financial_counter(
            redis=mock_redis,
            tenant_id=tenant_id,
            metric="total_spend",
            bucket_ts=1234567890,
            amount=Decimal("102.50"),
        )

        mock_redis.hincrbyfloat.assert_called_once()
        key_arg = mock_redis.hincrbyfloat.call_args[0][0]
        assert key_arg.startswith(f"tenant:{tenant_id}:")
