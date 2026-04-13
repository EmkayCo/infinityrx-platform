"""Event consumers for ReclaimRx module.

Consumes events from other modules and triggers appropriate FWA actions.
"""
from __future__ import annotations

import logging
from typing import Any

_logger = logging.getLogger(__name__)


def handle_claim_adjudicated(payload: dict[str, Any]) -> None:
    """Consume claim.adjudicated — evaluate post-adjudication rules.

    In production: calls detection rule engine on the adjudicated claim,
    queues results for investigation if needed.
    """
    claim_id = payload.get("claim_id")
    tenant_id = payload.get("tenant_id")
    _logger.info(
        "fwa.consume.claim_adjudicated",
        extra={"claim_id": claim_id, "tenant_id": tenant_id},
    )


def handle_claim_reversed(payload: dict[str, Any]) -> None:
    """Consume claim.reversed — update related flags/investigations."""
    claim_id = payload.get("claim_id")
    tenant_id = payload.get("tenant_id")
    _logger.info(
        "fwa.consume.claim_reversed",
        extra={"claim_id": claim_id, "tenant_id": tenant_id},
    )


def handle_ap_created(payload: dict[str, Any]) -> None:
    """Consume ap.created — cross-check claims entering billing."""
    ap_id = payload.get("ap_id")
    tenant_id = payload.get("tenant_id")
    _logger.info(
        "fwa.consume.ap_created",
        extra={"ap_id": ap_id, "tenant_id": tenant_id},
    )


def handle_ap_settled(payload: dict[str, Any]) -> None:
    """Consume ap.settled — payment made, update hold tracking."""
    ap_id = payload.get("ap_id")
    tenant_id = payload.get("tenant_id")
    _logger.info(
        "fwa.consume.ap_settled",
        extra={"ap_id": ap_id, "tenant_id": tenant_id},
    )


def handle_exclusion_match_found(payload: dict[str, Any]) -> None:
    """Consume exclusion.match_found — entity on exclusion list, trigger FWA action."""
    entity_type = payload.get("entity_type")
    entity_id = payload.get("entity_id")
    tenant_id = payload.get("tenant_id")
    _logger.warning(
        "fwa.consume.exclusion_match_found",
        extra={"entity_type": entity_type, "entity_id": entity_id, "tenant_id": tenant_id},
    )


def handle_payment_return_suspicious(payload: dict[str, Any]) -> None:
    """Consume payment.return_suspicious from Payment Processing.

    Indicates a payment return that may indicate fraud — trigger investigation.
    """
    payment_id = payload.get("payment_id")
    tenant_id = payload.get("tenant_id")
    entity_id = payload.get("entity_id")
    amount = payload.get("amount")
    _logger.warning(
        "fwa.consume.payment_return_suspicious",
        extra={
            "payment_id": payment_id,
            "tenant_id": tenant_id,
            "entity_id": entity_id,
            "amount": amount,
        },
    )


def handle_pharmacy_application_submitted(payload: dict[str, Any]) -> None:
    """Consume pharmacy.application_submitted — trigger credentialing risk score."""
    pharmacy_npi = payload.get("pharmacy_npi")
    tenant_id = payload.get("tenant_id")
    _logger.info(
        "fwa.consume.pharmacy_application_submitted",
        extra={"pharmacy_npi": pharmacy_npi, "tenant_id": tenant_id},
    )


def handle_pharmacy_ownership_changed(payload: dict[str, Any]) -> None:
    """Consume pharmacy.ownership_changed — re-evaluate risk and watchlist."""
    pharmacy_npi = payload.get("pharmacy_npi")
    tenant_id = payload.get("tenant_id")
    _logger.info(
        "fwa.consume.pharmacy_ownership_changed",
        extra={"pharmacy_npi": pharmacy_npi, "tenant_id": tenant_id},
    )


# Event routing map for registration with event bus
CONSUMER_ROUTING = {
    "claim.adjudicated": handle_claim_adjudicated,
    "claim.reversed": handle_claim_reversed,
    "ap.created": handle_ap_created,
    "ap.settled": handle_ap_settled,
    "exclusion.match_found": handle_exclusion_match_found,
    "payment.return_suspicious": handle_payment_return_suspicious,
    "pharmacy.application_submitted": handle_pharmacy_application_submitted,
    "pharmacy.ownership_changed": handle_pharmacy_ownership_changed,
}
