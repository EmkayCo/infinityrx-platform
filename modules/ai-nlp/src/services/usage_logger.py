"""Usage logger — records every AI call's cost in Decimal to ai_nlp.usage_log.

Cost MUST be Decimal, never float. This is enforced at the type level.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import AiNlpUsageLog


class UsageLogger:
    """Log AI call usage and cost to the database."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def log(
        self,
        tenant_id: UUID,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_cost_usd: Decimal,
        service_request_id: UUID | None,
    ) -> None:
        if not isinstance(total_cost_usd, Decimal):
            raise TypeError(
                f"total_cost_usd must be Decimal, got {type(total_cost_usd).__name__}"
            )
        entry = AiNlpUsageLog(
            tenant_id=tenant_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_cost_usd=total_cost_usd,
            service_request_id=service_request_id,
        )
        self._db.add(entry)
        await self._db.commit()

    async def get_usage_stats(self, tenant_id: UUID) -> list[dict[str, Any]]:
        """Return per-model usage totals for the tenant."""
        stmt = (
            select(
                AiNlpUsageLog.model,
                func.count(AiNlpUsageLog.id).label("call_count"),
                func.sum(AiNlpUsageLog.prompt_tokens).label("total_prompt_tokens"),
                func.sum(AiNlpUsageLog.completion_tokens).label("total_completion_tokens"),
                func.sum(AiNlpUsageLog.total_cost_usd).label("total_cost_usd"),
            )
            .where(AiNlpUsageLog.tenant_id == tenant_id)
            .group_by(AiNlpUsageLog.model)
            .order_by(AiNlpUsageLog.model)
        )
        result = await self._db.execute(stmt)
        rows = result.fetchall()
        return [
            {
                "model": row.model,
                "call_count": row.call_count,
                "total_prompt_tokens": row.total_prompt_tokens or 0,
                "total_completion_tokens": row.total_completion_tokens or 0,
                "total_cost_usd": str(
                    Decimal(str(row.total_cost_usd)).quantize(Decimal("0.000001"))
                ) if row.total_cost_usd is not None else "0.000000",
            }
            for row in rows
        ]

    async def get_usage_by_module(self, tenant_id: UUID) -> list[dict[str, Any]]:
        """Return usage grouped by requesting_module via service_request join."""
        stmt = text(
            """
            SELECT sr.requesting_module,
                   COUNT(ul.id) AS call_count,
                   SUM(ul.total_cost_usd) AS total_cost_usd
            FROM ai_nlp.usage_log ul
            LEFT JOIN ai_nlp.service_requests sr
                ON ul.service_request_id = sr.id
            WHERE ul.tenant_id = :tenant_id
            GROUP BY sr.requesting_module
            ORDER BY sr.requesting_module
            """
        )
        result = await self._db.execute(stmt, {"tenant_id": tenant_id})
        rows = result.fetchall()
        return [
            {
                "requesting_module": row.requesting_module or "unknown",
                "call_count": row.call_count,
                "total_cost_usd": str(
                    Decimal(str(row.total_cost_usd)).quantize(Decimal("0.000001"))
                ) if row.total_cost_usd is not None else "0.000000",
            }
            for row in rows
        ]
