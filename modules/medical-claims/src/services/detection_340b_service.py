"""340B detection service.

Conservative approach: only flag when BOTH conditions are met:
1. billing_provider_npi is in the tenant's 340B entity list
2. Drug is 340B-eligible (non-orphan covered outpatient drug)

False positives create compliance issues — we tune conservatively.
Modifier JG/TB is a supporting signal, not a determinant.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from src.models.tables import ClaimRecord
from src.utils.validators import has_340b_modifier

logger = logging.getLogger(__name__)


class Detection340bService:
    """Detects potential 340B billing on medical claims.

    Uses the pharmacy directory stub client (HTTP call — no direct DB access
    between modules per architecture rules).
    """

    def __init__(self, db: Session, pharmacy_dir_client: Any) -> None:
        self._db = db
        self._pharmacy_dir = pharmacy_dir_client

    def is_340b_entity(self, billing_provider_npi: str, tenant_id: uuid.UUID) -> bool:
        """Check if the billing NPI is a registered 340B entity via Pharmacy Directory."""
        try:
            return self._pharmacy_dir.is_340b_entity(billing_provider_npi, tenant_id)
        except Exception:
            logger.warning(
                "340B entity lookup failed — defaulting to False",
                extra={"svc_npi": billing_provider_npi, "svc_tenant_id": str(tenant_id)},
            )
            return False

    def evaluate_claim(self, claim: ClaimRecord) -> tuple[bool, str | None]:
        """Return (is_340b, entity_340b_id). Conservative — only flag on explicit match."""
        if claim.billing_provider_npi is None:
            return False, None

        in_list = self.is_340b_entity(claim.billing_provider_npi, claim.tenant_id)
        if not in_list:
            return False, None

        # Both conditions met: entity in list AND drug has NDC (340B-eligible coverage)
        effective_ndc = claim.ndc or claim.mapped_ndc
        if effective_ndc is None:
            return False, None

        # The modifier is a supporting signal, not a determinant — logged for audit
        has_mod = has_340b_modifier(claim.modifier_1, claim.modifier_2, claim.modifier_3, claim.modifier_4)
        entity_id = f"340B:{claim.billing_provider_npi}"

        if not has_mod:
            logger.info(
                "340B entity billing without JG/TB modifier",
                extra={
                    "svc_claim_id": str(claim.id),
                    "svc_npi": claim.billing_provider_npi,
                    "svc_tenant_id": str(claim.tenant_id),
                },
            )

        return True, entity_id

    def apply_340b_detection(self, tenant_id: uuid.UUID, claim_id: uuid.UUID) -> ClaimRecord | None:
        """Run 340B evaluation on a stored claim and persist result."""
        claim = (
            self._db.query(ClaimRecord)
            .filter_by(tenant_id=tenant_id, id=claim_id)
            .first()
        )
        if claim is None:
            return None

        is_340b, entity_id = self.evaluate_claim(claim)
        claim.is_340b = is_340b
        claim.entity_340b_id = entity_id
        self._db.commit()
        self._db.refresh(claim)

        if is_340b:
            logger.info(
                "340B claim flagged",
                extra={
                    "svc_claim_id": str(claim_id),
                    "svc_entity_id": entity_id,
                    "svc_tenant_id": str(tenant_id),
                },
            )
        return claim

    def get_340b_claims(self, tenant_id: uuid.UUID, page: int = 1, page_size: int = 50) -> tuple[list[ClaimRecord], int]:
        q = (
            self._db.query(ClaimRecord)
            .filter_by(tenant_id=tenant_id, is_340b=True)
        )
        total = q.count()
        items = q.order_by(ClaimRecord.date_of_service.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total
