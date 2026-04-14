"""HCPCS-to-NDC drug mapping service.

Multi-step confidence scoring:
  EXACT   — NDC present directly on claim
  HIGH    — single NDC from crosswalk
  MEDIUM  — narrowed from multiple crosswalk matches (not yet implemented)
  LOW     — multiple NDCs, cannot narrow, flag for manual review
  MANUAL  — no crosswalk entry, operator mapped
"""
from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.models.tables import ClaimRecord, HcpcsNdcCrosswalk
from src.api.schemas.crosswalk import CrosswalkResponse, CrosswalkLookupResponse

logger = logging.getLogger(__name__)

# Threshold: if more than this many NDC matches exist → LOW confidence, flag for manual review
_MANY_NDCS_THRESHOLD = 5


class MappingService:
    """Resolves HCPCS codes to NDCs with multi-step confidence scoring."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Crosswalk lookup
    # ------------------------------------------------------------------

    def lookup_crosswalk(self, hcpcs_code: str, as_of: date | None = None) -> CrosswalkLookupResponse:
        """Return all active crosswalk entries for a HCPCS code on a given date."""
        ref_date = as_of or date.today()

        q = (
            self._db.query(HcpcsNdcCrosswalk)
            .filter(HcpcsNdcCrosswalk.hcpcs_code == hcpcs_code)
            .filter(HcpcsNdcCrosswalk.effective_date <= ref_date)
            .filter(
                (HcpcsNdcCrosswalk.termination_date == None)  # noqa: E711
                | (HcpcsNdcCrosswalk.termination_date >= ref_date)
            )
            .all()
        )

        matches = [CrosswalkResponse.model_validate(row) for row in q]
        n = len(matches)

        if n == 0:
            confidence = "manual"
            requires_manual = True
        elif n == 1:
            confidence = "high"
            requires_manual = False
        elif n <= _MANY_NDCS_THRESHOLD:
            confidence = "medium"
            requires_manual = False
        else:
            confidence = "low"
            requires_manual = True

        return CrosswalkLookupResponse(
            hcpcs_code=hcpcs_code,
            matches=matches,
            confidence=confidence,
            requires_manual_review=requires_manual,
        )

    # ------------------------------------------------------------------
    # Claim mapping
    # ------------------------------------------------------------------

    def map_claim(self, claim: ClaimRecord) -> tuple[str | None, str]:
        """Determine mapped_ndc and mapping_confidence for a claim.

        Returns (mapped_ndc, confidence). If multiple NDCs are possible,
        returns (None, 'low') and the claim is flagged for manual review.
        50+ NDCs handled gracefully — all returned with LOW confidence.
        """
        # Step 1 — direct NDC on claim
        if claim.ndc:
            return claim.ndc, "exact"

        # Step 2 — HCPCS crosswalk
        result = self.lookup_crosswalk(claim.procedure_code, as_of=claim.date_of_service)

        if result.confidence == "high":
            return result.matches[0].ndc, "high"

        if result.confidence in {"medium", "low"}:
            # Multiple matches — cannot pick one safely
            return None, result.confidence

        # Step 3 — no crosswalk, needs manual
        return None, "manual"

    def apply_mapping_to_claim(self, tenant_id: uuid.UUID, claim_id: uuid.UUID) -> ClaimRecord | None:
        """Run the mapping pipeline on a stored claim and persist the result."""
        claim = (
            self._db.query(ClaimRecord)
            .filter_by(tenant_id=tenant_id, id=claim_id)
            .first()
        )
        if claim is None:
            return None

        mapped_ndc, confidence = self.map_claim(claim)
        claim.mapped_ndc = mapped_ndc
        claim.mapping_confidence = confidence
        self._db.commit()
        self._db.refresh(claim)

        logger.info(
            "drug mapping applied",
            extra={
                "svc_claim_id": str(claim_id),
                "svc_confidence": confidence,
                "svc_tenant_id": str(tenant_id),
            },
        )
        return claim

    # ------------------------------------------------------------------
    # Manual override
    # ------------------------------------------------------------------

    def set_manual_mapping(
        self, tenant_id: uuid.UUID, claim_id: uuid.UUID, ndc: str
    ) -> ClaimRecord | None:
        claim = (
            self._db.query(ClaimRecord)
            .filter_by(tenant_id=tenant_id, id=claim_id)
            .first()
        )
        if claim is None:
            return None

        claim.mapped_ndc = ndc
        claim.mapping_confidence = "manual"
        self._db.commit()
        self._db.refresh(claim)
        return claim

    # ------------------------------------------------------------------
    # Crosswalk CRUD (for admin / CMS refresh)
    # ------------------------------------------------------------------

    def upsert_crosswalk_entry(
        self,
        hcpcs_code: str,
        ndc: str,
        effective_date: date,
        **kwargs: Any,
    ) -> HcpcsNdcCrosswalk:
        existing = (
            self._db.query(HcpcsNdcCrosswalk)
            .filter_by(hcpcs_code=hcpcs_code, ndc=ndc, effective_date=effective_date)
            .first()
        )
        if existing:
            for k, v in kwargs.items():
                setattr(existing, k, v)
            self._db.commit()
            self._db.refresh(existing)
            return existing

        entry = HcpcsNdcCrosswalk(
            id=uuid.uuid4(),
            hcpcs_code=hcpcs_code,
            ndc=ndc,
            effective_date=effective_date,
            **kwargs,
        )
        self._db.add(entry)
        self._db.commit()
        self._db.refresh(entry)
        return entry

    def list_unmapped_claims(self, tenant_id: uuid.UUID) -> list[ClaimRecord]:
        """Return claims where NDC mapping is still pending manual review."""
        return (
            self._db.query(ClaimRecord)
            .filter_by(tenant_id=tenant_id)
            .filter(ClaimRecord.mapping_confidence.in_(["manual", "low"]))
            .filter(ClaimRecord.mapped_ndc == None)  # noqa: E711
            .all()
        )
