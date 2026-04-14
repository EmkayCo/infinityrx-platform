"""Accumulator integration service.

Calls Member Management accumulator HTTP endpoint to apply patient_responsibility
from medical claims to deductible and OOP accumulators.
Stubbed client — wire to real service when Member Management is ready.
"""
from __future__ import annotations

import logging
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.exc import OperationalError, TimeoutError as SATimeoutError
from sqlalchemy.orm import Session

from src.models.tables import ClaimRecord

logger = logging.getLogger(__name__)

_TWO_DP = Decimal("0.01")


def _money(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(_TWO_DP, rounding=ROUND_HALF_UP)


class AccumulatorService:
    """Applies patient responsibility amounts to member deductible/OOP accumulators."""

    def __init__(self, db: Session, member_mgmt_client: Any) -> None:
        self._db = db
        self._member_mgmt = member_mgmt_client

    def apply_accumulator(self, tenant_id: uuid.UUID, claim_id: uuid.UUID) -> ClaimRecord | None:
        """Compute patient responsibility breakdown and call Member Management accumulator."""
        claim = (
            self._db.query(ClaimRecord)
            .filter_by(tenant_id=tenant_id, id=claim_id)
            .first()
        )
        if claim is None:
            return None

        patient_resp = claim.patient_responsibility or Decimal("0.00")
        deductible = claim.deductible_amount or Decimal("0.00")
        copay = claim.copay_amount or Decimal("0.00")
        coinsurance = claim.coinsurance_amount or Decimal("0.00")

        # Amount that applies to deductible (deductible portion of patient responsibility)
        applied_deductible = _money(deductible)
        # Amount that applies to OOP (deductible + coinsurance, copay typically excluded from OOP max on some plans)
        applied_oop = _money(deductible + coinsurance)

        try:
            result = self._member_mgmt.apply_claim_accumulator(
                tenant_id=str(tenant_id),
                member_id=str(claim.member_id) if claim.member_id else claim.patient_member_id,
                date_of_service=claim.date_of_service.isoformat(),
                claim_id=str(claim.id),
                benefit_type="medical",
                applied_to_deductible=str(applied_deductible),
                applied_to_oop=str(applied_oop),
            )
            # Update claim with actual applied amounts from Member Management response
            if result:
                applied_deductible = _money(result.get("applied_to_deductible", applied_deductible))
                applied_oop = _money(result.get("applied_to_oop", applied_oop))
        except (OperationalError, SATimeoutError, ConnectionError, TimeoutError) as exc:
            # Only swallow transient infrastructure errors; re-raise data/logic errors
            logger.warning(
                "accumulator service call failed — using local calculation",
                extra={
                    "svc_claim_id": str(claim_id),
                    "svc_tenant_id": str(tenant_id),
                    "svc_error_type": type(exc).__name__,
                },
            )
        except Exception:
            # Non-transient error (e.g. InvalidOperation, ValueError) — propagate
            logger.error(
                "accumulator service non-transient failure",
                extra={"svc_claim_id": str(claim_id), "svc_tenant_id": str(tenant_id)},
                exc_info=True,
            )
            raise

        claim.applied_to_deductible = applied_deductible
        claim.applied_to_oop = applied_oop
        self._db.commit()
        self._db.refresh(claim)
        return claim
