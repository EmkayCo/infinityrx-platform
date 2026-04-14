"""Usage logger — records every AI call's cost in Decimal to ai_nlp.usage_log.

Cost MUST be Decimal, never float. This is enforced at the type level.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

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
