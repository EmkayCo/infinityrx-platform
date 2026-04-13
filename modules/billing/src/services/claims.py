"""Claims ingestion service.

Handles: claim validation, ingestion, duplicate detection, and classification.
All money uses Decimal with ROUND_HALF_UP via money() helper.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from src.services.routing import ClassifiedClaim
from src.utils.constants import (
    CLAIM_STATUS_CLASSIFIED,
    CLAIM_STATUS_INGESTED,
)
from src.utils.money import money


@dataclass
class ClaimIngestRequest:
    tenant_id: uuid.UUID
    source_type: str
    auth_number: str
    claim_type: str
    pharmacy_npi: str
    date_of_service: Any  # date
    net_amount: Decimal
    client_id: uuid.UUID
    program_id: uuid.UUID
    reversal_of_auth: str | None = None
    member_id: str | None = None
    pharmacy_name: str | None = None
    prescriber_npi: str | None = None
    ndc: str | None = None
    drug_name: str | None = None
    quantity: Decimal | None = None
    days_supply: int | None = None
    ingredient_cost: Decimal = field(default_factory=lambda: Decimal("0"))
    dispensing_fee: Decimal = field(default_factory=lambda: Decimal("0"))
    patient_pay: Decimal = field(default_factory=lambda: Decimal("0"))
    plan_pay: Decimal = field(default_factory=lambda: Decimal("0"))
    other_payer_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    under_reimbursement: Decimal = field(default_factory=lambda: Decimal("0"))
    network_reimbursement_id: str | None = None
    client_name: str | None = None
    program_name: str | None = None
    source_file_id: uuid.UUID | None = None
    source_claim_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        if len(self.pharmacy_npi) != 10 or not self.pharmacy_npi.isdigit():
            raise ValueError(f"Invalid pharmacy NPI: {self.pharmacy_npi!r} — must be 10 digits")
        # Enforce Decimal on all money fields
        self.net_amount = money(self.net_amount)
        self.ingredient_cost = money(self.ingredient_cost)
        self.dispensing_fee = money(self.dispensing_fee)
        self.patient_pay = money(self.patient_pay)
        self.plan_pay = money(self.plan_pay)
        self.other_payer_amount = money(self.other_payer_amount)
        self.under_reimbursement = money(self.under_reimbursement)


@dataclass
class IngestedClaim:
    """In-memory representation of a claim after ingestion (before DB flush)."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    source_type: str
    auth_number: str
    reversal_of_auth: str | None
    claim_type: str
    pharmacy_npi: str
    date_of_service: Any
    date_received: datetime
    net_amount: Decimal
    ingredient_cost: Decimal
    dispensing_fee: Decimal
    patient_pay: Decimal
    plan_pay: Decimal
    other_payer_amount: Decimal
    under_reimbursement: Decimal
    client_id: uuid.UUID
    program_id: uuid.UUID
    status: str
    # Routing results (set after classification)
    payment_route: str | None = None
    payment_vendor_config_id: uuid.UUID | None = None
    payment_schedule: str | None = None
    pay_to_entity_id: uuid.UUID | None = None
    pay_to_entity_name: str | None = None
    is_excluded: bool = False
    is_statement: bool = False
    # Optional claim data
    member_id: str | None = None
    pharmacy_name: str | None = None
    prescriber_npi: str | None = None
    ndc: str | None = None
    drug_name: str | None = None
    quantity: Decimal | None = None
    days_supply: int | None = None
    network_reimbursement_id: str | None = None
    client_name: str | None = None
    program_name: str | None = None
    source_file_id: uuid.UUID | None = None
    source_claim_id: uuid.UUID | None = None


class ClaimsService:
    def __init__(self, db: Any, events: Any) -> None:
        self._db = db
        self._events = events

    def ingest(self, req: ClaimIngestRequest) -> IngestedClaim:
        """Create an ingested claim record. Does NOT persist to DB (caller handles session)."""
        now = datetime.now(UTC)
        claim = IngestedClaim(
            id=uuid.uuid4(),
            tenant_id=req.tenant_id,
            source_type=req.source_type,
            auth_number=req.auth_number,
            reversal_of_auth=req.reversal_of_auth,
            claim_type=req.claim_type,
            pharmacy_npi=req.pharmacy_npi,
            date_of_service=req.date_of_service,
            date_received=now,
            net_amount=money(req.net_amount),
            ingredient_cost=money(req.ingredient_cost),
            dispensing_fee=money(req.dispensing_fee),
            patient_pay=money(req.patient_pay),
            plan_pay=money(req.plan_pay),
            other_payer_amount=money(req.other_payer_amount),
            under_reimbursement=money(req.under_reimbursement),
            client_id=req.client_id,
            program_id=req.program_id,
            status=CLAIM_STATUS_INGESTED,
            member_id=req.member_id,
            pharmacy_name=req.pharmacy_name,
            prescriber_npi=req.prescriber_npi,
            ndc=req.ndc,
            drug_name=req.drug_name,
            quantity=req.quantity,
            days_supply=req.days_supply,
            network_reimbursement_id=req.network_reimbursement_id,
            client_name=req.client_name,
            program_name=req.program_name,
            source_file_id=req.source_file_id,
            source_claim_id=req.source_claim_id,
        )
        self._events.publish(
            "claim.ingested",
            {
                "tenant_id": str(claim.tenant_id),
                "claim_id": str(claim.id),
                "auth_number": claim.auth_number,
                "claim_type": claim.claim_type,
            },
        )
        return claim

    def apply_classification(self, claim: IngestedClaim, result: ClassifiedClaim) -> None:
        """Apply routing classification result to a claim in-place."""
        if not result.classified:
            return
        claim.payment_route = result.payment_route
        claim.payment_vendor_config_id = result.payment_vendor_config_id
        claim.payment_schedule = result.payment_schedule
        claim.is_excluded = result.is_excluded
        claim.is_statement = result.is_statement
        claim.status = CLAIM_STATUS_CLASSIFIED
        self._events.publish(
            "claim.classified",
            {
                "tenant_id": str(claim.tenant_id),
                "claim_id": str(claim.id),
                "payment_route": claim.payment_route,
                "is_excluded": claim.is_excluded,
                "is_statement": claim.is_statement,
            },
        )

    def check_duplicate(
        self,
        auth_number: str,
        existing_auths: set[str],
        reversal_of: str | None,
    ) -> None:
        """Raise ValueError if auth_number is a duplicate (not a valid reversal)."""
        if auth_number in existing_auths:
            raise ValueError(
                f"duplicate auth_number {auth_number!r}: already ingested for this tenant"
            )
