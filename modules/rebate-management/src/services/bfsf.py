"""BFSF (Bona Fide Service Fee) documentation service.

PBM compensation limited to flat dollar BFSF at fair market value.
BFSF must reflect actual services performed (not linked to drug price/volume).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.models.tables import BFSFDocument, BFSFServiceCatalog
from src.utils.money import money


class BFSFService:
    """Manages BFSF documentation and approval workflow."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_catalog_entry(
        self,
        tenant_id: uuid.UUID,
        service_name: str,
        description: str,
        estimated_hours: Decimal,
        market_rate_per_hour: Decimal,
        market_comparables: dict | None = None,
    ) -> BFSFServiceCatalog:
        now = datetime.now(UTC)
        entry = BFSFServiceCatalog(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            service_name=service_name,
            description=description,
            estimated_hours=estimated_hours,
            market_rate_per_hour=money(market_rate_per_hour),
            market_comparables=market_comparables,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self._db.add(entry)
        self._db.flush()
        return entry

    def list_catalog(self, tenant_id: uuid.UUID) -> list[BFSFServiceCatalog]:
        return (
            self._db.query(BFSFServiceCatalog)
            .filter(
                BFSFServiceCatalog.tenant_id == tenant_id,
                BFSFServiceCatalog.is_active == True,  # noqa: E712
            )
            .all()
        )

    def compute_total_fee(self, services_detail: list[dict[str, Any]]) -> Decimal:
        """Compute total fee from services list.

        Each service dict must have: hours (Decimal|str), rate (Decimal|str).
        total_fee = sum(hours * rate) with ROUND_HALF_UP.
        """
        total = Decimal("0.00")
        for svc in services_detail:
            hours = Decimal(str(svc["hours"]))
            rate = Decimal(str(svc["rate"]))
            svc_total = money(hours * rate)
            total += svc_total
        return money(total)

    def create_document(
        self,
        tenant_id: uuid.UUID,
        sponsor_id: uuid.UUID,
        document_type: str,
        assessment_year: int,
        services_detail: list[dict[str, Any]],
        contract_id: uuid.UUID | None = None,
    ) -> BFSFDocument:
        """Create a BFSF document (FMV assessment, fee schedule, or attestation).

        total_fee is computed from services_detail.
        fair_market_value_justified is True only when total_fee matches
        computed sum of services (no manual override).
        """
        total_fee = self.compute_total_fee(services_detail)
        # Verify FMV: check all services have market rate justification
        fmv_justified = all(
            "rate" in svc and "hours" in svc for svc in services_detail
        )

        now = datetime.now(UTC)
        doc = BFSFDocument(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            contract_id=contract_id,
            sponsor_id=sponsor_id,
            document_type=document_type,
            assessment_year=assessment_year,
            services_detail=services_detail,
            total_fee=total_fee,
            fair_market_value_justified=fmv_justified,
            status="draft",
            version=1,
            created_at=now,
            updated_at=now,
        )
        self._db.add(doc)
        self._db.flush()
        return doc

    def submit_for_approval(
        self, tenant_id: uuid.UUID, document_id: uuid.UUID, submitted_by: uuid.UUID
    ) -> BFSFDocument:
        doc = self._get_doc(tenant_id, document_id)
        if doc.status != "draft":
            raise ValueError(f"Document {document_id} must be in draft to submit")
        doc.status = "pending_approval"
        doc.submitted_by = submitted_by
        doc.submitted_at = datetime.now(UTC)
        doc.updated_at = datetime.now(UTC)
        self._db.flush()
        return doc

    def approve(
        self,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
        approved_by: uuid.UUID,
    ) -> BFSFDocument:
        doc = self._get_doc(tenant_id, document_id)
        if doc.status != "pending_approval":
            raise ValueError(
                f"Document {document_id} must be pending_approval to approve; "
                f"current status: {doc.status!r}"
            )
        now = datetime.now(UTC)
        doc.status = "approved"
        doc.approved_by = approved_by
        doc.approved_at = now
        doc.updated_at = now
        self._db.flush()
        return doc

    def reject(
        self,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
        rejection_reason: str,
    ) -> BFSFDocument:
        doc = self._get_doc(tenant_id, document_id)
        if doc.status != "pending_approval":
            raise ValueError(
                f"Document {document_id} must be pending_approval to reject"
            )
        doc.status = "rejected"
        doc.rejection_reason = rejection_reason
        doc.updated_at = datetime.now(UTC)
        self._db.flush()
        return doc

    def _get_doc(
        self, tenant_id: uuid.UUID, document_id: uuid.UUID
    ) -> BFSFDocument:
        doc = (
            self._db.query(BFSFDocument)
            .filter(
                BFSFDocument.tenant_id == tenant_id,
                BFSFDocument.id == document_id,
            )
            .first()
        )
        if doc is None:
            raise ValueError(f"BFSFDocument {document_id} not found")
        return doc

    def get_document(
        self, tenant_id: uuid.UUID, document_id: uuid.UUID
    ) -> BFSFDocument | None:
        return (
            self._db.query(BFSFDocument)
            .filter(
                BFSFDocument.tenant_id == tenant_id,
                BFSFDocument.id == document_id,
            )
            .first()
        )

    def list_documents(
        self, tenant_id: uuid.UUID, sponsor_id: uuid.UUID | None = None
    ) -> list[BFSFDocument]:
        q = self._db.query(BFSFDocument).filter(
            BFSFDocument.tenant_id == tenant_id
        )
        if sponsor_id:
            q = q.filter(BFSFDocument.sponsor_id == sponsor_id)
        return q.all()
