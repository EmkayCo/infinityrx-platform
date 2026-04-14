"""Unit tests for AI usage logger — Decimal cost tracking, tenant scoping."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.services.usage_logger import UsageLogger


class TestUsageLogger:
    @pytest.fixture()
    def mock_db(self) -> AsyncMock:
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_log_stores_decimal_cost(self, mock_db: AsyncMock) -> None:
        logger = UsageLogger(db=mock_db)
        await logger.log(
            tenant_id=uuid4(),
            model="gpt-4.1",
            prompt_tokens=1000,
            completion_tokens=500,
            total_cost_usd=Decimal("0.012500"),
            service_request_id=uuid4(),
        )
        mock_db.add.assert_called_once()
        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj.total_cost_usd, Decimal)

    @pytest.mark.asyncio
    async def test_log_rejects_float_cost(self, mock_db: AsyncMock) -> None:
        logger = UsageLogger(db=mock_db)
        with pytest.raises((TypeError, ValueError)):
            await logger.log(
                tenant_id=uuid4(),
                model="gpt-4.1",
                prompt_tokens=100,
                completion_tokens=50,
                total_cost_usd=0.0125,  # type: ignore[arg-type]
                service_request_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_log_includes_tenant_id(self, mock_db: AsyncMock) -> None:
        logger = UsageLogger(db=mock_db)
        tid = uuid4()
        await logger.log(
            tenant_id=tid,
            model="gpt-4.1",
            prompt_tokens=100,
            completion_tokens=50,
            total_cost_usd=Decimal("0.001"),
            service_request_id=None,
        )
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.tenant_id == tid

    @pytest.mark.asyncio
    async def test_log_commits(self, mock_db: AsyncMock) -> None:
        logger = UsageLogger(db=mock_db)
        await logger.log(
            tenant_id=uuid4(),
            model="gpt-4.1-mini",
            prompt_tokens=50,
            completion_tokens=25,
            total_cost_usd=Decimal("0.000100"),
            service_request_id=None,
        )
        mock_db.commit.assert_called_once()
