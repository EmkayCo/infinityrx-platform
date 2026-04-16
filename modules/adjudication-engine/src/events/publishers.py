"""Event publishers for the adjudication engine.

Events follow dot-notation and use EventEnvelope with idempotency_key
and ordering_key per event-bus rules. Decimal amounts serialized as
strings for precision fidelity.

Published events:
- claim.adjudicated — claim successfully paid
- claim.reversed — claim reversal processed
- claim.rejected — claim rejected during adjudication
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from shared.events.types import EventEnvelope

logger = logging.getLogger("adjudication_engine.events")

SOURCE_MODULE = "adjudication-engine"


def build_claim_adjudicated_event(
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    claim_id: str,
    member_id: str,
    drug_ndc: str,
    status: str,
    ingredient_cost: str,
    dispensing_fee: str,
    patient_pay: str,
    plan_pay: str,
    total_amount: str,
    pricing_model_used: str,
    accumulator_detected: bool,
    override_applied: bool,
) -> EventEnvelope:
    """Build a claim.adjudicated event envelope.

    Published when a claim is successfully paid (status='paid').
    """
    return EventEnvelope(
        event_type="claim.adjudicated",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        schema_version="1.0",
        idempotency_key=f"claim.adjudicated:{claim_id}",
        ordering_key=claim_id,
        payload={
            "claim_id": claim_id,
            "member_id": member_id,
            "drug_ndc": drug_ndc,
            "status": status,
            "ingredient_cost": ingredient_cost,
            "dispensing_fee": dispensing_fee,
            "patient_pay": patient_pay,
            "plan_pay": plan_pay,
            "total_amount": total_amount,
            "pricing_model_used": pricing_model_used,
            "accumulator_detected": accumulator_detected,
            "override_applied": override_applied,
        },
    )


def build_claim_reversed_event(
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    claim_id: str,
    original_claim_id: str,
    member_id: str,
    ingredient_cost: str,
    total_amount: str,
) -> EventEnvelope:
    """Build a claim.reversed event envelope.

    Published when a B2 reversal is processed. Amounts are negative.
    """
    return EventEnvelope(
        event_type="claim.reversed",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        schema_version="1.0",
        idempotency_key=f"claim.reversed:{claim_id}",
        ordering_key=claim_id,
        payload={
            "claim_id": claim_id,
            "original_claim_id": original_claim_id,
            "member_id": member_id,
            "ingredient_cost": ingredient_cost,
            "total_amount": total_amount,
        },
    )


def build_claim_rejected_event(
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    claim_id: str,
    member_id: str,
    drug_ndc: str,
    reject_code: str,
    reject_reason: str,
    dur_alerts: list[dict[str, Any]] | None = None,
) -> EventEnvelope:
    """Build a claim.rejected event envelope.

    Published when a claim is rejected during adjudication.
    """
    return EventEnvelope(
        event_type="claim.rejected",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        schema_version="1.0",
        idempotency_key=f"claim.rejected:{claim_id}",
        ordering_key=claim_id,
        payload={
            "claim_id": claim_id,
            "member_id": member_id,
            "drug_ndc": drug_ndc,
            "reject_code": reject_code,
            "reject_reason": reject_reason,
            "dur_alerts": dur_alerts or [],
        },
    )
