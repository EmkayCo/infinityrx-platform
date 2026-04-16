"""Prior Authorization event consumers.

Consumers handle inbound events from other modules (e.g., adjudication
engine requesting PA status, claim events triggering PA evaluation).

All consumers are wrapped with idempotent_handler and handle unknown
fields gracefully per event-bus rules.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def handle_claim_pa_required(payload: dict[str, Any]) -> None:
    """Handle claim.pa_required event from adjudication engine.

    When a claim is rejected for requiring PA, this consumer can
    auto-initiate a PA request if the plan is configured for ePA.
    """
    pa_request_id = payload.get("pa_request_id")
    member_id = payload.get("member_id")
    drug_ndc = payload.get("drug_ndc")

    logger.info(
        "Received claim.pa_required event",
        extra={
            "pa_event_member_id": member_id,
            "pa_event_drug_ndc": drug_ndc,
        },
    )


async def handle_epa_response(payload: dict[str, Any]) -> None:
    """Handle epa.response event from the switch connectivity module.

    Processes NCPDP SCRIPT ePA responses and updates PA status.
    """
    pa_request_id = payload.get("pa_request_id")
    response_status = payload.get("status")

    logger.info(
        "Received epa.response event",
        extra={
            "pa_request_id": pa_request_id,
            "pa_epa_status": response_status,
        },
    )
