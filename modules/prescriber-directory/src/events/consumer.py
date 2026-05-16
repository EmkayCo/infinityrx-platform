"""Event consumers for prescriber-directory module.

Consumes:
  - claim.ingested     → update prescriber-pharmacy relationship volumes
  - exclusion.match_found → mark prescriber as excluded

CR-01 v2 HIPAA fix: handle_claim_ingested now accepts tenant_id and filters
PrescriberPharmacyRelationship queries by it, preventing cross-tenant data mixing.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Optional

logger = logging.getLogger("prescriber-directory.events.consumer")


async def handle_claim_ingested(
    payload: dict,
    db,
    tenant_id: Optional[uuid.UUID] = None,
) -> None:
    """Consume claim.ingested — accumulate prescriber→pharmacy volume per tenant.

    CR-01 v2 HIPAA: tenant_id is required and used to scope the upsert query.
    Rows are now per-tenant (PrescriberPharmacyRelationship.tenant_id column added).

    Args:
        payload: Event payload with prescriber_npi, pharmacy_npi, date_of_service.
        db: SQLAlchemy Session.
        tenant_id: Tenant UUID from EventEnvelope — filters all DB queries.
    """
    prescriber_npi = payload.get("prescriber_npi")
    pharmacy_npi = payload.get("pharmacy_npi")
    date_of_service = payload.get("date_of_service", "")

    if not prescriber_npi or not pharmacy_npi:
        logger.warning(
            "claim_ingested_missing_npi",
            extra={"svc_event": "claim.ingested"},
        )
        return

    if tenant_id is None:
        logger.warning(
            "claim_ingested_missing_tenant_id",
            extra={"svc_event": "claim.ingested"},
        )
        return

    # Extract YYYY-MM period key
    period_month = date_of_service[:7] if date_of_service and len(date_of_service) >= 7 else ""
    if not period_month:
        period_month = datetime.now(UTC).strftime("%Y-%m")

    from sqlalchemy import select
    from src.models.tables import PrescriberPharmacyRelationship

    # CR-01 v2 HIPAA: filter by tenant_id — prevents cross-tenant data mixing
    stmt = select(PrescriberPharmacyRelationship).where(
        PrescriberPharmacyRelationship.tenant_id == tenant_id,
        PrescriberPharmacyRelationship.prescriber_npi == prescriber_npi,
        PrescriberPharmacyRelationship.pharmacy_npi == pharmacy_npi,
        PrescriberPharmacyRelationship.period_month == period_month,
    )
    row = db.execute(stmt).scalar_one_or_none()

    now = datetime.now(UTC)
    if row is None:
        row = PrescriberPharmacyRelationship(
            # CR-01 v2 HIPAA: store tenant_id so rows are isolated per tenant
            tenant_id=tenant_id,
            prescriber_npi=prescriber_npi,
            pharmacy_npi=pharmacy_npi,
            period_month=period_month,
            claim_count=1,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.claim_count += 1
        row.updated_at = now

    db.flush()


async def handle_exclusion_match_found(payload: dict, db) -> None:
    """Consume exclusion.match_found — mark prescriber as excluded.

    Expected payload fields:
      entity_npi: str  (prescriber NPI)
      exclusion_type: str (OIG, SAM, OFAC)
    """
    entity_npi = payload.get("entity_npi")
    if not entity_npi:
        return

    from sqlalchemy import select
    from src.models.tables import Prescriber

    stmt = select(Prescriber).where(Prescriber.npi == entity_npi)
    prescriber = db.execute(stmt).scalar_one_or_none()
    if prescriber is None:
        logger.warning(
            "exclusion_prescriber_not_found",
            extra={"svc_event": "exclusion.match_found"},
        )
        return

    prescriber.status = "excluded"
    prescriber.updated_at = datetime.now(UTC)
    db.flush()

    logger.info(
        "prescriber_marked_excluded",
        extra={"svc_event": "exclusion.match_found"},
    )
