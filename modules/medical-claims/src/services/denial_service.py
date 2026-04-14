"""Denial management with CARC/RARC reason codes and appeal workflow."""
from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy.orm import Session

from src.models.tables import ClaimRecord
from src.services.claim_service import ClaimService

logger = logging.getLogger(__name__)

# Common CARC codes for medical drug claim denials
COMMON_CARC_CODES = {
    "1": "Deductible amount",
    "2": "Coinsurance amount",
    "4": "The procedure code is inconsistent with the modifier used",
    "5": "The procedure code/type of bill is inconsistent with the place of service",
    "16": "Claim/service lacks information or has submission/billing error(s)",
    "18": "Duplicate claim/service",
    "19": "Claim denied because this is a work-related injury/illness",
    "22": "This care may be covered by another payer",
    "50": "These are non-covered services because this is not deemed a medical necessity",
    "96": "Non-covered charge(s)",
    "97": "The benefit for this service is included in the payment/allowance for another service",
    "197": "Precertification/authorization/notification/pre-treatment absent",
}


class DenialService:
    """Handles claim denial tracking, analytics, and appeal workflow."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._claim_svc = ClaimService(db)

    # ------------------------------------------------------------------
    # Deny a claim
    # ------------------------------------------------------------------

    def deny_claim(
        self,
        tenant_id: uuid.UUID,
        claim_id: uuid.UUID,
        reason_code: str,
        reason_description: str | None = None,
    ) -> ClaimRecord | None:
        """Transition a claim to denied status with CARC code."""
        description = reason_description or COMMON_CARC_CODES.get(reason_code, "Claim denied")

        return self._claim_svc.transition_status(
            tenant_id=tenant_id,
            claim_id=claim_id,
            new_status="denied",
            denial_reason_code=reason_code,
            denial_reason_description=description,
        )

    # ------------------------------------------------------------------
    # Appeal
    # ------------------------------------------------------------------

    def initiate_appeal(
        self,
        tenant_id: uuid.UUID,
        claim_id: uuid.UUID,
        appeal_reason: str,
        supporting_documentation: str | None = None,
    ) -> ClaimRecord | None:
        """Transition a denied claim to appealed status."""
        claim = (
            self._db.query(ClaimRecord)
            .filter_by(tenant_id=tenant_id, id=claim_id)
            .first()
        )
        if claim is None:
            return None

        if claim.status != "denied":
            raise ValueError(f"Can only appeal denied claims. Current status: {claim.status}")

        return self._claim_svc.transition_status(
            tenant_id=tenant_id,
            claim_id=claim_id,
            new_status="appealed",
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_denied_claims(
        self,
        tenant_id: uuid.UUID,
        reason_code: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ClaimRecord], int]:
        q = (
            self._db.query(ClaimRecord)
            .filter_by(tenant_id=tenant_id)
            .filter(ClaimRecord.status.in_(["denied", "appealed"]))
        )

        if reason_code:
            q = q.filter(ClaimRecord.denial_reason_code == reason_code)
        if date_from:
            q = q.filter(ClaimRecord.date_of_service >= date_from)
        if date_to:
            q = q.filter(ClaimRecord.date_of_service <= date_to)

        total = q.count()
        items = q.order_by(ClaimRecord.date_of_service.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    # ------------------------------------------------------------------
    # Denial analytics
    # ------------------------------------------------------------------

    def get_denial_analytics(
        self,
        tenant_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> dict[str, Any]:
        """Aggregate denial rates by reason code, provider, and HCPCS."""
        from sqlalchemy import func

        all_claims = (
            self._db.query(func.count(ClaimRecord.id))
            .filter_by(tenant_id=tenant_id)
            .filter(ClaimRecord.date_of_service >= date_from)
            .filter(ClaimRecord.date_of_service <= date_to)
            .scalar()
        ) or 0

        denied_claims = (
            self._db.query(func.count(ClaimRecord.id))
            .filter_by(tenant_id=tenant_id)
            .filter(ClaimRecord.status.in_(["denied", "appealed"]))
            .filter(ClaimRecord.date_of_service >= date_from)
            .filter(ClaimRecord.date_of_service <= date_to)
            .scalar()
        ) or 0

        denial_rate = Decimal(str(denied_claims / all_claims * 100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ) if all_claims > 0 else Decimal("0.00")

        # By reason code
        by_reason = (
            self._db.query(ClaimRecord.denial_reason_code, func.count(ClaimRecord.id))
            .filter_by(tenant_id=tenant_id)
            .filter(ClaimRecord.status.in_(["denied", "appealed"]))
            .filter(ClaimRecord.date_of_service >= date_from)
            .filter(ClaimRecord.date_of_service <= date_to)
            .group_by(ClaimRecord.denial_reason_code)
            .all()
        )

        # By provider NPI
        by_provider = (
            self._db.query(ClaimRecord.rendering_provider_npi, func.count(ClaimRecord.id))
            .filter_by(tenant_id=tenant_id)
            .filter(ClaimRecord.status.in_(["denied", "appealed"]))
            .filter(ClaimRecord.date_of_service >= date_from)
            .filter(ClaimRecord.date_of_service <= date_to)
            .group_by(ClaimRecord.rendering_provider_npi)
            .order_by(func.count(ClaimRecord.id).desc())
            .limit(20)
            .all()
        )

        # By HCPCS code
        by_hcpcs = (
            self._db.query(ClaimRecord.procedure_code, func.count(ClaimRecord.id))
            .filter_by(tenant_id=tenant_id)
            .filter(ClaimRecord.status.in_(["denied", "appealed"]))
            .filter(ClaimRecord.date_of_service >= date_from)
            .filter(ClaimRecord.date_of_service <= date_to)
            .group_by(ClaimRecord.procedure_code)
            .order_by(func.count(ClaimRecord.id).desc())
            .limit(20)
            .all()
        )

        return {
            "period_start": date_from,
            "period_end": date_to,
            "total_denied": denied_claims,
            "denial_rate": denial_rate,
            "by_reason_code": [
                {"reason_code": code, "count": cnt, "description": COMMON_CARC_CODES.get(code or "", "Unknown")}
                for code, cnt in by_reason
            ],
            "by_provider": [
                {"rendering_provider_npi": npi, "count": cnt}
                for npi, cnt in by_provider
            ],
            "by_hcpcs": [
                {"procedure_code": code, "count": cnt}
                for code, cnt in by_hcpcs
            ],
        }
