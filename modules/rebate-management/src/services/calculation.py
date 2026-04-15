"""Rebate calculation engine.

Batch-run per period (typically quarterly). Inputs: claim data, active
contracts, utilization. Output: per-NDC rebate earned per contract.

All Decimal with ROUND_HALF_UP. Tiered market-share calculations.
Accrual accounting: recognize earned rebates monthly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.models.tables import (
    RebateAccrual,
    RebateContract,
    RebateContractNDC,
    RebateTier,
    RebateTransaction,
)
from src.utils.hash_chain import GENESIS_HASH, compute_entry_hash
from src.utils.money import ZERO, money

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


@dataclass
class ClaimLineInput:
    """Single adjudicated claim line for rebate calculation."""

    ndc11: str
    date_of_service: date
    units_dispensed: Decimal
    wac_per_unit: Decimal
    sponsor_id: uuid.UUID
    claim_id: uuid.UUID | None = None


@dataclass
class NDCRebateResult:
    """Per-NDC rebate calculation result."""

    contract_id: uuid.UUID
    ndc11: str
    units_dispensed: Decimal
    wac_per_unit: Decimal
    gross_wac: Decimal
    base_rebate: Decimal
    formulary_bonus: Decimal
    growth_bonus: Decimal
    tier_bonus: Decimal
    total_rebate: Decimal
    rebate_category: str


@dataclass
class PeriodCalculationResult:
    """Full period calculation summary."""

    period_start: date
    period_end: date
    ndc_results: list[NDCRebateResult] = field(default_factory=list)
    total_rebate: Decimal = ZERO
    transaction_ids: list[uuid.UUID] = field(default_factory=list)


def _apply_tier(
    tiers: list[RebateTier],
    tier_type: str,
    measure_value: Decimal,
) -> Decimal:
    """Return the highest tier rebate percent where threshold is met.

    Args:
        tiers:         Sorted list of tier records for this contract.
        tier_type:     ``"volume"`` or ``"market_share"``.
        measure_value: Actual volume or market share to evaluate.

    Returns:
        Rebate percent (e.g. Decimal("5.0000") = 5%) for the best
        qualifying tier, or ZERO if no tier is met.
    """
    qualifying = [
        t for t in tiers
        if t.tier_type == tier_type
        and measure_value >= t.threshold_value
    ]
    if not qualifying:
        return ZERO
    best = max(qualifying, key=lambda t: t.threshold_value)
    return best.rebate_percent.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def calculate_ndc_rebate(
    ndc_term: RebateContractNDC,
    tiers: list[RebateTier],
    units_dispensed: Decimal,
    wac_per_unit: Decimal,
    market_share: Decimal = ZERO,
) -> NDCRebateResult:
    """Calculate rebate for a single NDC-11 under a contract term.

    Supports:
      - percent_wac: base_rebate = units * wac * rebate_percent / 100
      - flat_per_unit: base_rebate = units * rebate_per_unit
      - Formulary position bonus %
      - Growth bonus %
      - Volume / market-share tier bonus %

    All arithmetic in Decimal with ROUND_HALF_UP.
    """
    gross_wac = (units_dispensed * wac_per_unit).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )

    # Base rebate
    if ndc_term.rebate_type == "percent_wac":
        pct = (ndc_term.rebate_percent or ZERO).quantize(
            FOUR_PLACES, rounding=ROUND_HALF_UP
        )
        base_rebate = (gross_wac * pct / Decimal("100")).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
    elif ndc_term.rebate_type == "flat_per_unit":
        rpu = (ndc_term.rebate_per_unit or ZERO).quantize(
            FOUR_PLACES, rounding=ROUND_HALF_UP
        )
        base_rebate = (units_dispensed * rpu).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
    else:
        base_rebate = ZERO

    # Formulary position bonus
    if ndc_term.formulary_position_bonus_percent:
        fp_pct = ndc_term.formulary_position_bonus_percent.quantize(
            FOUR_PLACES, rounding=ROUND_HALF_UP
        )
        formulary_bonus = (gross_wac * fp_pct / Decimal("100")).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
    else:
        formulary_bonus = ZERO

    # Growth bonus
    if ndc_term.growth_bonus_percent:
        g_pct = ndc_term.growth_bonus_percent.quantize(
            FOUR_PLACES, rounding=ROUND_HALF_UP
        )
        growth_bonus = (gross_wac * g_pct / Decimal("100")).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
    else:
        growth_bonus = ZERO

    # Tier bonus (volume-based)
    tier_pct = _apply_tier(tiers, "volume", units_dispensed)
    if tier_pct == ZERO:
        # Try market-share tier
        tier_pct = _apply_tier(tiers, "market_share", market_share)
    tier_bonus = (gross_wac * tier_pct / Decimal("100")).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )

    total_rebate = money(base_rebate + formulary_bonus + growth_bonus + tier_bonus)

    return NDCRebateResult(
        contract_id=ndc_term.contract_id,
        ndc11=ndc_term.ndc11,
        units_dispensed=units_dispensed,
        wac_per_unit=wac_per_unit,
        gross_wac=gross_wac,
        base_rebate=base_rebate,
        formulary_bonus=formulary_bonus,
        growth_bonus=growth_bonus,
        tier_bonus=tier_bonus,
        total_rebate=total_rebate,
        rebate_category="commercial",
    )


class CalculationEngine:
    """Orchestrates rebate calculations for a period."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def _get_prev_tx_hash(self, tenant_id: uuid.UUID) -> str:
        """Get the most recent transaction hash to extend the chain."""
        last = (
            self._db.query(RebateTransaction)
            .filter(RebateTransaction.tenant_id == tenant_id)
            .order_by(RebateTransaction.created_at.desc())
            .first()
        )
        return last.entry_hash if last else GENESIS_HASH

    def run_period(
        self,
        tenant_id: uuid.UUID,
        period_start: date,
        period_end: date,
        claim_lines: list[ClaimLineInput],
        market_shares: dict[str, Decimal] | None = None,
    ) -> PeriodCalculationResult:
        """Run rebate calculation for a period.

        Args:
            tenant_id:    Tenant scoping.
            period_start: First day of the calculation period.
            period_end:   Last day of the calculation period.
            claim_lines:  Adjudicated claim lines in the period.
            market_shares: Optional dict {ndc11: market_share_pct} for
                          market-share tiers.

        Returns:
            PeriodCalculationResult with per-NDC breakdowns.
        """
        market_shares = market_shares or {}

        # Aggregate units + WAC by (contract_id, ndc11)
        aggregates: dict[tuple[uuid.UUID, str], dict[str, Any]] = {}

        # Get active contracts covering the period
        contracts = (
            self._db.query(RebateContract)
            .filter(
                RebateContract.tenant_id == tenant_id,
                RebateContract.status == "active",
                RebateContract.effective_date <= period_end,
            )
            .all()
        )
        if not contracts:
            return PeriodCalculationResult(
                period_start=period_start,
                period_end=period_end,
            )

        # Build NDC → contract term map
        ndc_terms: dict[str, RebateContractNDC] = {}
        contract_tiers: dict[uuid.UUID, list[RebateTier]] = {}
        for contract in contracts:
            if contract.termination_date and contract.termination_date < period_start:
                continue
            for ndc_term in contract.ndcs:
                if ndc_term.effective_date > period_end:
                    continue
                if ndc_term.termination_date and ndc_term.termination_date < period_start:
                    continue
                ndc_terms[ndc_term.ndc11] = ndc_term
            contract_tiers[contract.id] = list(contract.tiers)

        # Aggregate claims by (contract_id, ndc11, sponsor_id)
        sponsor_aggregates: dict[
            tuple[uuid.UUID, str, uuid.UUID], dict[str, Any]
        ] = {}
        for line in claim_lines:
            if line.ndc11 not in ndc_terms:
                continue
            ndc_term = ndc_terms[line.ndc11]
            key = (ndc_term.contract_id, line.ndc11, line.sponsor_id)
            if key not in sponsor_aggregates:
                sponsor_aggregates[key] = {
                    "units": ZERO,
                    "total_wac": ZERO,
                    "count": 0,
                    "ndc_term": ndc_term,
                    "sponsor_id": line.sponsor_id,
                }
            sponsor_aggregates[key]["units"] += line.units_dispensed
            sponsor_aggregates[key]["total_wac"] += (
                line.units_dispensed * line.wac_per_unit
            ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            sponsor_aggregates[key]["count"] += 1

        results: list[NDCRebateResult] = []
        tx_ids: list[uuid.UUID] = []
        prev_hash = self._get_prev_tx_hash(tenant_id)
        now = datetime.now(UTC)

        for (contract_id, ndc11, sponsor_id), agg in sponsor_aggregates.items():
            ndc_term = agg["ndc_term"]
            units = agg["units"]
            # Weighted average WAC
            avg_wac = (
                agg["total_wac"] / units if units > ZERO
                else ZERO
            ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

            tiers = contract_tiers.get(contract_id, [])
            mkt_share = market_shares.get(ndc11, ZERO)
            result = calculate_ndc_rebate(
                ndc_term=ndc_term,
                tiers=tiers,
                units_dispensed=units,
                wac_per_unit=avg_wac,
                market_share=mkt_share,
            )
            results.append(result)

            # Write immutable transaction record
            tx_id = uuid.uuid4()
            entry_fields = {
                "id": str(tx_id),
                "contract_id": str(contract_id),
                "ndc11": ndc11,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "transaction_type": "calculated",
                "rebate_category": result.rebate_category,
                "units_dispensed": str(units),
                "wac_per_unit": str(avg_wac),
                "gross_wac": str(result.gross_wac),
                "rebate_amount": str(result.total_rebate),
                "sponsor_id": str(sponsor_id),
                "tenant_id": str(tenant_id),
            }
            entry_hash = compute_entry_hash(prev_hash, entry_fields)
            tx = RebateTransaction(
                id=tx_id,
                tenant_id=tenant_id,
                contract_id=contract_id,
                ndc11=ndc11,
                period_start=period_start,
                period_end=period_end,
                transaction_type="calculated",
                rebate_category=result.rebate_category,
                units_dispensed=units,
                wac_per_unit=avg_wac,
                gross_wac=result.gross_wac,
                rebate_amount=result.total_rebate,
                sponsor_id=sponsor_id,
                prev_hash=prev_hash,
                entry_hash=entry_hash,
                created_at=now,
            )
            self._db.add(tx)
            tx_ids.append(tx_id)
            prev_hash = entry_hash

        self._db.flush()

        total = money(sum(r.total_rebate for r in results))
        return PeriodCalculationResult(
            period_start=period_start,
            period_end=period_end,
            ndc_results=results,
            total_rebate=total,
            transaction_ids=tx_ids,
        )

    def accrue_monthly(
        self,
        tenant_id: uuid.UUID,
        contract_id: uuid.UUID,
        ndc11: str,
        accrual_month: date,
        accrued_amount: Decimal,
    ) -> RebateAccrual:
        """Record a monthly accrual for earned-but-not-yet-received rebates."""
        now = datetime.now(UTC)
        existing = (
            self._db.query(RebateAccrual)
            .filter(
                RebateAccrual.tenant_id == tenant_id,
                RebateAccrual.contract_id == contract_id,
                RebateAccrual.ndc11 == ndc11,
                RebateAccrual.accrual_month == accrual_month,
            )
            .first()
        )
        if existing:
            # Update accrual if not yet recognized
            if not existing.recognized:
                existing.accrued_amount = money(accrued_amount)
            return existing

        accrual = RebateAccrual(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            contract_id=contract_id,
            ndc11=ndc11,
            accrual_month=accrual_month,
            accrued_amount=money(accrued_amount),
            recognized=False,
            created_at=now,
        )
        self._db.add(accrual)
        self._db.flush()
        return accrual

    def recognize_accrual(
        self,
        tenant_id: uuid.UUID,
        accrual_id: uuid.UUID,
        actual_payment_id: uuid.UUID | None = None,
    ) -> RebateAccrual:
        """Mark an accrual as recognized when manufacturer payment arrives."""
        accrual = (
            self._db.query(RebateAccrual)
            .filter(
                RebateAccrual.tenant_id == tenant_id,
                RebateAccrual.id == accrual_id,
            )
            .first()
        )
        if accrual is None:
            raise ValueError(f"Accrual {accrual_id} not found")
        if accrual.recognized:
            raise ValueError(f"Accrual {accrual_id} already recognized")
        accrual.recognized = True
        accrual.recognized_at = datetime.now(UTC)
        accrual.actual_payment_id = actual_payment_id
        self._db.flush()
        return accrual
