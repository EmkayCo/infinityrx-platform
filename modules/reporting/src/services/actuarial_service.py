"""Actuarial modeling service: prospective cost, formulary impact, network savings, rebates."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import ActuarialModel


def _money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ActuarialService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_models(self, tenant_id: str) -> list[ActuarialModel]:
        stmt = (
            select(ActuarialModel)
            .where(ActuarialModel.tenant_id == tenant_id)
            .order_by(ActuarialModel.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_model(self, model_id: str, tenant_id: str) -> ActuarialModel | None:
        stmt = select(ActuarialModel).where(
            ActuarialModel.id == model_id,
            ActuarialModel.tenant_id == tenant_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def reprice_claims(self, tenant_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Reprice prospect claims under InfinityRx formulary/network/rebate assumptions.

        All monetary outputs use Decimal with ROUND_HALF_UP.
        """
        claims = params.get("claims", [])
        formulary_discount = _money(params.get("formulary_discount_pct", "0.00"))
        network_discount = _money(params.get("network_discount_pct", "0.00"))
        rebate_estimate = _money(params.get("rebate_estimate_pct", "0.00"))

        total_original = _money(sum(_money(c.get("amount_paid", 0)) for c in claims))
        discount_factor = (
            (Decimal("100") - formulary_discount - network_discount) / Decimal("100")
        ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        total_repriced = (total_original * discount_factor).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        rebate_amount = (total_repriced * rebate_estimate / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        net_cost = total_repriced - rebate_amount
        savings = total_original - net_cost

        return {
            "tenant_id": tenant_id,
            "claim_count": len(claims),
            "total_original_cost": str(total_original),
            "total_repriced_cost": str(total_repriced),
            "estimated_rebates": str(rebate_amount),
            "net_cost": str(net_cost),
            "estimated_savings": str(savings),
            "savings_pct": str(
                (savings / total_original * Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if total_original > Decimal("0")
                else Decimal("0.00")
            ),
        }

    async def run_scenario(
        self, model_id: str, tenant_id: str, scenario_params: dict[str, Any]
    ) -> dict[str, Any]:
        """Run a new scenario on an existing actuarial model."""
        model = await self.get_model(model_id, tenant_id)
        if model is None:
            raise ValueError(f"Model {model_id} not found")
        return await self.reprice_claims(tenant_id, scenario_params)
