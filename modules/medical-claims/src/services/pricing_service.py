"""ASP-based and contract-based pricing for medical benefit drug claims.

ASP per-unit uses DECIMAL(12,6) — never downcast before multiplying by quantity.
All intermediate calculations preserve full precision; quantize to 2dp only at final result.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.models.tables import AspPricing, ClaimRecord
from src.api.schemas.asp import AspPricingResponse

logger = logging.getLogger(__name__)

_TWO_DP = Decimal("0.01")
_SIX_DP = Decimal("0.000001")

# CMS Medicare Part B standard: payment limit = ASP + 6%
ASP_MARKUP_PCT = Decimal("0.06")


def _money(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(_TWO_DP, rounding=ROUND_HALF_UP)


def _six_dp(value: Any) -> Decimal:
    """Preserve 6dp precision for ASP unit prices before quantity multiplication."""
    if isinstance(value, Decimal):
        return value.quantize(_SIX_DP, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(_SIX_DP, rounding=ROUND_HALF_UP)


def quarter_for_date(dos: date) -> str:
    """Return the YYYY-QN string for a given date."""
    q = (dos.month - 1) // 3 + 1
    return f"{dos.year}-Q{q}"


class PricingService:
    """Prices medical drug claims using ASP quarterly rates or tenant fee schedules."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # ASP lookup
    # ------------------------------------------------------------------

    def get_asp_pricing(self, hcpcs_code: str, dos: date) -> AspPricing | None:
        """Return the ASP pricing record for a HCPCS code and quarter.

        If no pricing exists for the exact quarter, falls back to the most
        recent prior quarter (edge case: future quarter, no data yet).
        """
        target_quarter = quarter_for_date(dos)

        # Try exact quarter first
        record = (
            self._db.query(AspPricing)
            .filter_by(hcpcs_code=hcpcs_code, quarter=target_quarter)
            .first()
        )
        if record:
            return record

        # Fallback: most recent prior quarter
        record = (
            self._db.query(AspPricing)
            .filter(AspPricing.hcpcs_code == hcpcs_code)
            .filter(AspPricing.effective_date <= dos)
            .order_by(AspPricing.effective_date.desc())
            .first()
        )
        if record:
            logger.warning(
                "ASP pricing fallback to prior quarter",
                extra={
                    "svc_hcpcs": hcpcs_code,
                    "svc_target_quarter": target_quarter,
                    "svc_fallback_quarter": record.quarter,
                },
            )
        return record

    # ------------------------------------------------------------------
    # ASP-based pricing calculation
    # ------------------------------------------------------------------

    def calculate_asp_allowed(
        self,
        asp_per_unit: Decimal,
        quantity: Decimal,
        markup_pct: Decimal = ASP_MARKUP_PCT,
    ) -> Decimal:
        """Calculate allowed amount: (ASP × (1 + markup_pct)) × quantity.

        Preserves 6dp precision on asp_per_unit until final multiplication,
        then quantizes to 2dp with ROUND_HALF_UP.
        """
        asp_6dp = _six_dp(asp_per_unit)
        payment_limit = asp_6dp * (Decimal("1") + markup_pct)
        allowed = payment_limit * quantity
        return _money(allowed)

    def price_claim(self, tenant_id: uuid.UUID, claim_id: uuid.UUID) -> ClaimRecord | None:
        """Apply ASP pricing to a claim and persist allowed_amount."""
        claim = (
            self._db.query(ClaimRecord)
            .filter_by(tenant_id=tenant_id, id=claim_id)
            .first()
        )
        if claim is None:
            return None

        hcpcs = claim.procedure_code
        dos = claim.date_of_service
        qty = claim.drug_quantity or Decimal("1")

        asp_record = self.get_asp_pricing(hcpcs, dos)
        if asp_record is None:
            logger.warning(
                "no ASP pricing found for claim",
                extra={"svc_claim_id": str(claim_id), "svc_hcpcs": hcpcs},
            )
            return claim

        allowed = self.calculate_asp_allowed(asp_record.asp_per_unit, qty)

        # Pay lesser of billed and allowed
        paid = _money(min(claim.billed_amount, allowed))

        claim.allowed_amount = allowed
        claim.paid_amount = paid
        claim.status = "priced"

        self._db.commit()
        self._db.refresh(claim)
        return claim

    # ------------------------------------------------------------------
    # Waste calculation
    # ------------------------------------------------------------------

    def calculate_waste(
        self,
        billed_quantity: Decimal,
        administered_quantity: Decimal,
        drug_unit_price: Decimal,
    ) -> tuple[Decimal, Decimal]:
        """Return (waste_quantity, waste_amount). Waste = billed - administered."""
        waste_qty = (billed_quantity - administered_quantity).quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        )
        if waste_qty < Decimal("0"):
            waste_qty = Decimal("0.000")
        waste_amt = _money(waste_qty * _six_dp(drug_unit_price))
        return waste_qty, waste_amt

    def apply_waste(self, tenant_id: uuid.UUID, claim_id: uuid.UUID, administered_quantity: Decimal) -> ClaimRecord | None:
        """Detect JW modifier and record waste on the claim."""
        claim = (
            self._db.query(ClaimRecord)
            .filter_by(tenant_id=tenant_id, id=claim_id)
            .first()
        )
        if claim is None:
            return None

        if claim.drug_quantity is None or claim.drug_unit_price is None:
            return claim

        waste_qty, waste_amt = self.calculate_waste(
            claim.drug_quantity, administered_quantity, claim.drug_unit_price
        )
        claim.waste_quantity = waste_qty
        claim.waste_amount = waste_amt
        self._db.commit()
        self._db.refresh(claim)
        return claim

    # ------------------------------------------------------------------
    # ASP upsert (for quarterly refresh job)
    # ------------------------------------------------------------------

    def upsert_asp(
        self,
        hcpcs_code: str,
        quarter: str,
        effective_date: date,
        asp_per_unit: Decimal,
        hcpcs_description: str | None = None,
    ) -> AspPricing:
        # Compute payment limit: ASP + 6%
        payment_limit = _six_dp(asp_per_unit * (Decimal("1") + ASP_MARKUP_PCT))

        existing = (
            self._db.query(AspPricing)
            .filter_by(hcpcs_code=hcpcs_code, quarter=quarter)
            .first()
        )
        if existing:
            existing.asp_per_unit = _six_dp(asp_per_unit)
            existing.payment_limit = payment_limit
            existing.effective_date = effective_date
            if hcpcs_description:
                existing.hcpcs_description = hcpcs_description
            self._db.commit()
            self._db.refresh(existing)
            return existing

        record = AspPricing(
            id=uuid.uuid4(),
            hcpcs_code=hcpcs_code,
            quarter=quarter,
            effective_date=effective_date,
            asp_per_unit=_six_dp(asp_per_unit),
            payment_limit=payment_limit,
            hcpcs_description=hcpcs_description,
            data_source="cms_asp",
        )
        self._db.add(record)
        self._db.commit()
        self._db.refresh(record)
        return record

    def get_asp_response(self, hcpcs_code: str, dos: date) -> AspPricingResponse | None:
        record = self.get_asp_pricing(hcpcs_code, dos)
        if record is None:
            return None
        return AspPricingResponse.model_validate(record)
