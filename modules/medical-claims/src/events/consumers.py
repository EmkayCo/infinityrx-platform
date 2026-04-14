"""Medical Claims event consumers.

- edi.837_received  → ingest medical drug claims from EDI module
- claim.adjudicated → populate unified_drug_spend from pharmacy claims (Billing)

Handlers are structured for idempotency: callers wrap them with
idempotent_handler(store, consumer_name=...) if needed, per event-bus rules.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date as _date
from decimal import Decimal
from typing import Any

from shared.events import EventEnvelope

logger = logging.getLogger(__name__)

# TODO: wire edi.837_received consumer when EDI module finalizes its event contract
# The EDI side is stubbed — we ingest via payload.claim_lines[] once EDI publishes
# the schema. See claim_service.ingest_from_edi_payload() for the parsing logic.


async def handle_edi_837_received(envelope: EventEnvelope, claim_service: Any, db: Any) -> None:
    """Consume edi.837_received event and create medical claim records for drug lines.

    # TODO: finalize event schema with EDI module team; currently parses generic payload
    """
    payload = envelope.payload
    tenant_id = envelope.tenant_id
    source_transaction_id = payload.get("transaction_record_id")

    try:
        tx_uuid = uuid.UUID(source_transaction_id) if source_transaction_id else None
        created = claim_service.ingest_from_edi_payload(
            tenant_id=tenant_id,
            payload=payload,
            source_transaction_id=tx_uuid,
        )
        logger.info(
            "edi.837_received processed",
            extra={
                "svc_tenant_id": str(tenant_id),
                "svc_claim_count": len(created),
                "svc_correlation_id": str(envelope.correlation_id),
            },
        )
    except Exception as exc:
        logger.error(
            "edi.837_received processing failed",
            extra={
                "svc_tenant_id": str(tenant_id),
                "svc_error": str(exc),
                "svc_correlation_id": str(envelope.correlation_id),
            },
            exc_info=True,
        )
        raise


async def handle_pharmacy_claim_adjudicated(
    envelope: EventEnvelope, unified_spend_service: Any
) -> None:
    """Consume claim.adjudicated event from Billing and populate unified_drug_spend."""
    payload = envelope.payload
    tenant_id = envelope.tenant_id

    try:
        pharmacy_claim_id_str = payload.get("claim_id")
        if not pharmacy_claim_id_str:
            logger.warning(
                "claim.adjudicated payload missing claim_id",
                extra={"svc_tenant_id": str(tenant_id)},
            )
            return

        pharmacy_claim_id = uuid.UUID(pharmacy_claim_id_str)
        member_id_str = payload.get("member_id")
        member_id = uuid.UUID(member_id_str) if member_id_str else None

        dos_str = payload.get("date_of_service", "")
        dos = _date.fromisoformat(dos_str) if dos_str else _date.today()

        unified_spend_service.record_pharmacy_claim(
            tenant_id=tenant_id,
            pharmacy_claim_id=pharmacy_claim_id,
            member_id=member_id,
            member_id_display=payload.get("member_id_display"),
            ndc=payload.get("ndc"),
            drug_name=payload.get("drug_name"),
            dos=dos,
            billed_amount=Decimal(payload["billed_amount"]) if payload.get("billed_amount") else None,
            allowed_amount=Decimal(payload["allowed_amount"]) if payload.get("allowed_amount") else None,
            paid_amount=Decimal(payload["paid_amount"]) if payload.get("paid_amount") else None,
            patient_pay=Decimal(payload["patient_pay"]) if payload.get("patient_pay") else None,
            quantity=Decimal(str(payload["quantity"])) if payload.get("quantity") else None,
            days_supply=payload.get("days_supply"),
            therapeutic_class=payload.get("therapeutic_class"),
        )
    except Exception as exc:
        logger.error(
            "claim.adjudicated processing failed",
            extra={
                "svc_tenant_id": str(tenant_id),
                "svc_error": str(exc),
                "svc_correlation_id": str(envelope.correlation_id),
            },
            exc_info=True,
        )
        raise
