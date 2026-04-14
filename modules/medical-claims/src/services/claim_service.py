"""Core claim ingestion, CRUD, and status management service."""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, UTC
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.models.tables import ClaimRecord
from src.utils.validators import is_drug_hcpcs, classify_site_of_care
from src.api.schemas.claims import ClaimCreate, ClaimUpdate

logger = logging.getLogger(__name__)

VALID_STATUSES = frozenset({
    "received", "validated", "priced", "adjudicated",
    "paid", "denied", "appealed", "voided",
})

# Status transition rules: current → allowed next states
STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "received": frozenset({"validated", "voided"}),
    "validated": frozenset({"priced", "denied", "voided"}),
    "priced": frozenset({"adjudicated", "denied", "voided"}),
    "adjudicated": frozenset({"paid", "denied", "voided"}),
    "paid": frozenset({"voided"}),
    "denied": frozenset({"appealed", "voided"}),
    "appealed": frozenset({"adjudicated", "denied", "voided"}),
    "voided": frozenset(),
}


def _money(value: Any) -> Decimal:
    """Convert to Decimal with ROUND_HALF_UP to 2dp."""
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ClaimService:
    """Handles claim ingestion, CRUD, and status transitions."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create_claim(self, tenant_id: uuid.UUID, data: ClaimCreate) -> ClaimRecord:
        """Persist a new claim record from API input."""
        claim = ClaimRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            claim_number=data.claim_number,
            claim_line_number=data.claim_line_number,
            claim_type=data.claim_type,
            source_file_type=data.source_file_type or "api",
            received_date=date.today(),
            patient_member_id=data.patient_member_id,
            patient_first_name_encrypted=data.patient_first_name,
            patient_last_name_encrypted=data.patient_last_name,
            patient_dob_encrypted=data.patient_dob.isoformat() if data.patient_dob else None,
            patient_gender=data.patient_gender,
            subscriber_id=data.subscriber_id,
            subscriber_relationship=data.subscriber_relationship,
            rendering_provider_npi=data.rendering_provider_npi,
            rendering_provider_name=data.rendering_provider_name,
            rendering_provider_taxonomy=data.rendering_provider_taxonomy,
            billing_provider_npi=data.billing_provider_npi,
            billing_provider_name=data.billing_provider_name,
            billing_provider_tax_id=data.billing_provider_tax_id,
            referring_provider_npi=data.referring_provider_npi,
            facility_npi=data.facility_npi,
            facility_name=data.facility_name,
            date_of_service=data.date_of_service,
            date_of_service_end=data.date_of_service_end,
            place_of_service=data.place_of_service,
            type_of_bill=data.type_of_bill,
            procedure_code=data.procedure_code,
            procedure_code_type=data.procedure_code_type,
            modifier_1=data.modifier_1,
            modifier_2=data.modifier_2,
            modifier_3=data.modifier_3,
            modifier_4=data.modifier_4,
            revenue_code=data.revenue_code,
            ndc=data.ndc,
            ndc_qualifier=data.ndc_qualifier,
            drug_name=data.drug_name,
            drug_quantity=data.drug_quantity,
            drug_unit=data.drug_unit,
            drug_unit_price=data.drug_unit_price,
            diagnosis_code_1=data.diagnosis_code_1,
            diagnosis_code_2=data.diagnosis_code_2,
            diagnosis_code_3=data.diagnosis_code_3,
            diagnosis_code_4=data.diagnosis_code_4,
            diagnosis_code_qualifier=data.diagnosis_code_qualifier or "ABK",
            diagnosis_pointer=data.diagnosis_pointer,
            billed_amount=_money(data.billed_amount),
            allowed_amount=_money(data.allowed_amount) if data.allowed_amount is not None else None,
            paid_amount=_money(data.paid_amount) if data.paid_amount is not None else None,
            patient_responsibility=_money(data.patient_responsibility) if data.patient_responsibility is not None else None,
            copay_amount=_money(data.copay_amount) if data.copay_amount is not None else None,
            coinsurance_amount=_money(data.coinsurance_amount) if data.coinsurance_amount is not None else None,
            deductible_amount=_money(data.deductible_amount) if data.deductible_amount is not None else None,
            payer_sequence=data.payer_sequence,
            other_payer_paid=_money(data.other_payer_paid) if data.other_payer_paid is not None else None,
            prior_auth_number=data.prior_auth_number,
            prior_auth_status=data.prior_auth_status,
            status="received",
        )

        # Auto-classify site of care from POS code
        claim.site_of_care = classify_site_of_care(data.place_of_service)

        self._db.add(claim)
        self._db.commit()
        self._db.refresh(claim)

        logger.info(
            "medical claim created",
            extra={"svc_claim_id": str(claim.id), "svc_tenant_id": str(tenant_id)},
        )
        return claim

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_claim(self, tenant_id: uuid.UUID, claim_id: uuid.UUID) -> ClaimRecord | None:
        return (
            self._db.query(ClaimRecord)
            .filter_by(tenant_id=tenant_id, id=claim_id)
            .first()
        )

    def list_claims(
        self,
        tenant_id: uuid.UUID,
        status: str | None = None,
        procedure_code: str | None = None,
        ndc: str | None = None,
        patient_member_id: str | None = None,
        rendering_provider_npi: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ClaimRecord], int]:
        q = self._db.query(ClaimRecord).filter_by(tenant_id=tenant_id)

        if status:
            q = q.filter(ClaimRecord.status == status)
        if procedure_code:
            q = q.filter(ClaimRecord.procedure_code == procedure_code)
        if ndc:
            q = q.filter(ClaimRecord.ndc == ndc)
        if patient_member_id:
            q = q.filter(ClaimRecord.patient_member_id == patient_member_id)
        if rendering_provider_npi:
            q = q.filter(ClaimRecord.rendering_provider_npi == rendering_provider_npi)
        if date_from:
            q = q.filter(ClaimRecord.date_of_service >= date_from)
        if date_to:
            q = q.filter(ClaimRecord.date_of_service <= date_to)

        total = q.count()
        items = q.order_by(ClaimRecord.date_of_service.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_claim(self, tenant_id: uuid.UUID, claim_id: uuid.UUID, data: ClaimUpdate) -> ClaimRecord | None:
        claim = self.get_claim(tenant_id, claim_id)
        if claim is None:
            return None

        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            # Money fields — enforce ROUND_HALF_UP
            if field in {
                "allowed_amount", "paid_amount", "patient_responsibility",
                "copay_amount", "coinsurance_amount", "deductible_amount",
                "waste_amount", "applied_to_deductible", "applied_to_oop",
            } and value is not None:
                value = _money(value)
            setattr(claim, field, value)

        claim.updated_at = datetime.now(UTC)
        self._db.commit()
        self._db.refresh(claim)
        return claim

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------

    def transition_status(
        self,
        tenant_id: uuid.UUID,
        claim_id: uuid.UUID,
        new_status: str,
        denial_reason_code: str | None = None,
        denial_reason_description: str | None = None,
    ) -> ClaimRecord | None:
        claim = self.get_claim(tenant_id, claim_id)
        if claim is None:
            return None

        allowed = STATUS_TRANSITIONS.get(claim.status, frozenset())
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from '{claim.status}' to '{new_status}'. "
                f"Allowed: {sorted(allowed)}"
            )

        claim.status = new_status
        if new_status == "denied":
            claim.denial_reason_code = denial_reason_code
            claim.denial_reason_description = denial_reason_description
        claim.updated_at = datetime.now(UTC)

        self._db.commit()
        self._db.refresh(claim)

        logger.info(
            "medical claim status transitioned",
            extra={
                "svc_claim_id": str(claim_id),
                "svc_new_status": new_status,
                "svc_tenant_id": str(tenant_id),
            },
        )
        return claim

    # ------------------------------------------------------------------
    # Drug claim filtering
    # ------------------------------------------------------------------

    @staticmethod
    def is_drug_claim(procedure_code: str, ndc: str | None) -> bool:
        """True if the claim line represents a drug claim."""
        return is_drug_hcpcs(procedure_code) or (ndc is not None and ndc.strip() != "")

    # ------------------------------------------------------------------
    # Ingestion from 837 EDI event payload
    # ------------------------------------------------------------------

    def ingest_from_edi_payload(
        self,
        tenant_id: uuid.UUID,
        payload: dict[str, Any],
        source_transaction_id: uuid.UUID | None = None,
    ) -> list[ClaimRecord]:
        """Parse an EDI 837 event payload and create claim records for drug lines only."""
        # TODO: wire to real edi.837_received event schema when EDI module finalizes its contract
        claims_data = payload.get("claim_lines", [])
        created: list[ClaimRecord] = []

        for line in claims_data:
            procedure_code = line.get("procedure_code", "")
            ndc = line.get("ndc")

            if not self.is_drug_claim(procedure_code, ndc):
                continue

            record = ClaimRecord(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                claim_number=line.get("claim_number", ""),
                claim_line_number=line.get("claim_line_number", 1),
                claim_type=line.get("claim_type", "professional"),
                source_file_type=payload.get("transaction_type", "837P"),
                source_transaction_id=source_transaction_id,
                received_date=date.today(),
                patient_member_id=line.get("patient_member_id", ""),
                patient_first_name_encrypted=line.get("patient_first_name"),
                patient_last_name_encrypted=line.get("patient_last_name"),
                patient_dob_encrypted=line.get("patient_dob"),
                rendering_provider_npi=line.get("rendering_provider_npi", "0000000000"),
                billing_provider_npi=line.get("billing_provider_npi"),
                date_of_service=_parse_date(line.get("date_of_service")),
                place_of_service=line.get("place_of_service"),
                procedure_code=procedure_code,
                modifier_1=line.get("modifier_1"),
                modifier_2=line.get("modifier_2"),
                modifier_3=line.get("modifier_3"),
                modifier_4=line.get("modifier_4"),
                ndc=ndc,
                drug_quantity=Decimal(str(line["drug_quantity"])) if line.get("drug_quantity") else None,
                drug_unit=line.get("drug_unit"),
                billed_amount=_money(line.get("billed_amount", "0")),
                status="received",
                site_of_care=classify_site_of_care(line.get("place_of_service")),
            )
            self._db.add(record)
            created.append(record)

        if created:
            self._db.commit()
            for r in created:
                self._db.refresh(r)

        return created


def _parse_date(value: Any) -> date:
    """Parse a date value from various formats."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    return date.today()
