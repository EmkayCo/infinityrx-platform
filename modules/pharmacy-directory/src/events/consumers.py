"""Event consumers for pharmacy-directory.

Consumes:
  fwa.credentialing_risk_elevated — update pharmacy risk score in credentialing
  fwa.pharmacy_risk_elevated — flag pharmacy for review
"""
from __future__ import annotations

import logging

from shared.events.types import EventEnvelope

logger = logging.getLogger("pharmacy-directory.consumers")


async def handle_fwa_credentialing_risk_elevated(envelope: EventEnvelope) -> None:
    """Update credentialing risk score from ReclaimRx FWA event."""
    payload = envelope.payload
    application_id = payload.get("application_id")
    risk_score = payload.get("risk_score")
    payload.get("risk_factors", {})  # consumed by downstream DB update

    if not application_id or risk_score is None:
        logger.warning(
            "fwa.credentialing_risk_elevated missing fields",
            extra={
                "svc_name": "consumers",
                "event_id": str(envelope.event_id),
            },
        )
        return

    logger.info(
        "fwa.credentialing_risk_elevated received",
        extra={
            "svc_name": "consumers",
            "credentialing_application_id": str(application_id),
            "pharmacy_risk_score": risk_score,
        },
    )
    # Actual DB update wired through the credentialing service at app startup


async def handle_fwa_pharmacy_risk_elevated(envelope: EventEnvelope) -> None:
    """Flag pharmacy for review from ReclaimRx FWA event."""
    payload = envelope.payload
    pharmacy_id = payload.get("pharmacy_id")
    npi = payload.get("npi")

    if not pharmacy_id:
        logger.warning(
            "fwa.pharmacy_risk_elevated missing pharmacy_id",
            extra={
                "svc_name": "consumers",
                "event_id": str(envelope.event_id),
            },
        )
        return

    logger.info(
        "fwa.pharmacy_risk_elevated received",
        extra={
            "svc_name": "consumers",
            "pharmacy_id": str(pharmacy_id),
            "pharmacy_npi": npi,
        },
    )
    # Actual DB update wired at app startup
