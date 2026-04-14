"""Unified drug spend service.

Populates unified_drug_spend from both medical claims and pharmacy claim events.
COB (Coordination of Benefits) protection: same member + same NDC + same DOS
with different payer sequences must NOT be double-counted.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.models.tables import ClaimRecord, UnifiedDrugSpend

logger = logging.getLogger(__name__)

_TWO_DP = Decimal("0.01")


def _money(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value.quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(_TWO_DP, rounding=ROUND_HALF_UP)


class UnifiedDrugSpendService:
    """Maintains unified_drug_spend across pharmacy and medical benefits."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Medical claim → unified spend
    # ------------------------------------------------------------------

    def record_medical_claim(self, claim: ClaimRecord) -> UnifiedDrugSpend:
        """Create a unified_drug_spend record for an adjudicated medical claim."""
        effective_ndc = claim.ndc or claim.mapped_ndc

        record = UnifiedDrugSpend(
            id=uuid.uuid4(),
            tenant_id=claim.tenant_id,
            member_id=claim.member_id,
            member_id_display=claim.patient_member_id,
            ndc=effective_ndc,
            drug_name=claim.drug_name,
            therapeutic_class=None,  # populated by Drug Database enrichment
            benefit_type="medical",
            medical_claim_id=claim.id,
            pharmacy_claim_id=None,
            date_of_service=claim.date_of_service,
            billed_amount=_money(claim.billed_amount),
            allowed_amount=_money(claim.allowed_amount),
            paid_amount=_money(claim.paid_amount),
            patient_pay=_money(claim.patient_responsibility),
            quantity=claim.drug_quantity,
            days_supply=None,
        )
        self._db.add(record)
        self._db.commit()
        self._db.refresh(record)
        return record

    # ------------------------------------------------------------------
    # Pharmacy claim event → unified spend
    # ------------------------------------------------------------------

    def record_pharmacy_claim(
        self,
        tenant_id: uuid.UUID,
        pharmacy_claim_id: uuid.UUID,
        member_id: uuid.UUID | None,
        member_id_display: str | None,
        ndc: str | None,
        drug_name: str | None,
        dos: date,
        billed_amount: Decimal | None,
        allowed_amount: Decimal | None,
        paid_amount: Decimal | None,
        patient_pay: Decimal | None,
        quantity: Decimal | None,
        days_supply: int | None,
        therapeutic_class: str | None = None,
    ) -> UnifiedDrugSpend:
        """Create a unified_drug_spend record from a pharmacy claim.adjudicated event."""
        record = UnifiedDrugSpend(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            member_id=member_id,
            member_id_display=member_id_display,
            ndc=ndc,
            drug_name=drug_name,
            therapeutic_class=therapeutic_class,
            benefit_type="pharmacy",
            pharmacy_claim_id=pharmacy_claim_id,
            medical_claim_id=None,
            date_of_service=dos,
            billed_amount=_money(billed_amount),
            allowed_amount=_money(allowed_amount),
            paid_amount=_money(paid_amount),
            patient_pay=_money(patient_pay),
            quantity=quantity,
            days_supply=days_supply,
        )
        self._db.add(record)
        self._db.commit()
        self._db.refresh(record)
        return record

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_spend(
        self,
        tenant_id: uuid.UUID,
        member_id: uuid.UUID | None = None,
        ndc: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        benefit_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[UnifiedDrugSpend], int]:
        q = self._db.query(UnifiedDrugSpend).filter_by(tenant_id=tenant_id)

        if member_id:
            q = q.filter(UnifiedDrugSpend.member_id == member_id)
        if ndc:
            q = q.filter(UnifiedDrugSpend.ndc == ndc)
        if date_from:
            q = q.filter(UnifiedDrugSpend.date_of_service >= date_from)
        if date_to:
            q = q.filter(UnifiedDrugSpend.date_of_service <= date_to)
        if benefit_type:
            q = q.filter(UnifiedDrugSpend.benefit_type == benefit_type)

        total = q.count()
        items = q.order_by(UnifiedDrugSpend.date_of_service.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    def get_member_timeline(
        self, tenant_id: uuid.UUID, member_id: uuid.UUID
    ) -> list[UnifiedDrugSpend]:
        """Chronological drug timeline across both benefits for a member."""
        return (
            self._db.query(UnifiedDrugSpend)
            .filter_by(tenant_id=tenant_id, member_id=member_id)
            .order_by(UnifiedDrugSpend.date_of_service.desc())
            .all()
        )

    def detect_therapeutic_duplications(self, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
        """Find members with the same NDC on both pharmacy and medical benefits.

        COB exclusion: pairs where payer_sequence differs for the same member/drug/date
        are COB, not duplication. We exclude those by checking the claim table.
        """
        # Get all pharmacy+medical pairs for the same member/ndc/date
        from sqlalchemy import and_, func
        from sqlalchemy.orm import aliased

        PharmacySpend = aliased(UnifiedDrugSpend)
        MedicalSpend = aliased(UnifiedDrugSpend)

        pairs = (
            self._db.query(PharmacySpend, MedicalSpend)
            .filter(PharmacySpend.tenant_id == tenant_id)
            .filter(MedicalSpend.tenant_id == tenant_id)
            .filter(PharmacySpend.benefit_type == "pharmacy")
            .filter(MedicalSpend.benefit_type == "medical")
            .filter(PharmacySpend.member_id == MedicalSpend.member_id)
            .filter(PharmacySpend.ndc == MedicalSpend.ndc)
            .filter(PharmacySpend.date_of_service == MedicalSpend.date_of_service)
            .filter(PharmacySpend.member_id != None)  # noqa: E711
            .all()
        )

        duplications = []
        for pharmacy_row, medical_row in pairs:
            # COB check: if the medical claim has a payer_sequence, it's COB not duplication
            medical_claim = None
            if medical_row.medical_claim_id:
                medical_claim = (
                    self._db.query(ClaimRecord)
                    .filter_by(id=medical_row.medical_claim_id)
                    .first()
                )

            is_cob = medical_claim is not None and medical_claim.payer_sequence in {"secondary", "tertiary"}
            if is_cob:
                continue

            duplications.append({
                "member_id": pharmacy_row.member_id,
                "member_id_display": pharmacy_row.member_id_display,
                "ndc": pharmacy_row.ndc,
                "drug_name": pharmacy_row.drug_name,
                "date_of_service": pharmacy_row.date_of_service,
                "pharmacy_record": pharmacy_row,
                "medical_record": medical_row,
            })

        return duplications
