"""Event publishing functions for ReclaimRx module."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from src._shim.events import publish


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def publish_claim_flagged(
    *,
    tenant_id: uuid.UUID,
    flagged_claim_id: str,
    claim_id: str | None,
    rule_code: str,
    severity: str,
    risk_score: int,
    pharmacy_npi: str,
    action_taken: str,
    correlation_id: uuid.UUID | None = None,
) -> None:
    publish(
        "fwa.claim_flagged",
        {
            "tenant_id": str(tenant_id),
            "flagged_claim_id": flagged_claim_id,
            "claim_id": claim_id,
            "rule_code": rule_code,
            "severity": severity,
            "risk_score": risk_score,
            "pharmacy_npi": pharmacy_npi,
            "action_taken": action_taken,
            "occurred_at": _now_iso(),
            "correlation_id": str(correlation_id) if correlation_id else None,
        },
    )


def publish_claim_blocked(
    *,
    tenant_id: uuid.UUID,
    claim_id: str | None,
    auth_number: str,
    rule_code: str,
    reason: str,
) -> None:
    publish(
        "fwa.claim_blocked",
        {
            "tenant_id": str(tenant_id),
            "claim_id": claim_id,
            "auth_number": auth_number,
            "rule_code": rule_code,
            "reason": reason,
            "occurred_at": _now_iso(),
        },
    )


def publish_investigation_opened(
    *,
    tenant_id: uuid.UUID,
    investigation_id: str,
    investigation_number: str,
    subject_type: str,
    subject_entity_id: str,
    investigation_type: str,
    priority: str,
) -> None:
    publish(
        "fwa.investigation_opened",
        {
            "tenant_id": str(tenant_id),
            "investigation_id": investigation_id,
            "investigation_number": investigation_number,
            "subject_type": subject_type,
            "subject_entity_id": subject_entity_id,
            "investigation_type": investigation_type,
            "priority": priority,
            "occurred_at": _now_iso(),
        },
    )


def publish_investigation_resolved(
    *,
    tenant_id: uuid.UUID,
    investigation_id: str,
    investigation_number: str,
    resolution_type: str,
    actual_recovered: Decimal,
) -> None:
    publish(
        "fwa.investigation_resolved",
        {
            "tenant_id": str(tenant_id),
            "investigation_id": investigation_id,
            "investigation_number": investigation_number,
            "resolution_type": resolution_type,
            "actual_recovered": str(actual_recovered),
            "occurred_at": _now_iso(),
        },
    )


def publish_recovery_demanded(
    *,
    tenant_id: uuid.UUID,
    investigation_id: str,
    recovery_id: str,
    amount: Decimal,
    confidence_tier: str,
    methodology_tag: str,
) -> None:
    publish(
        "fwa.recovery_demanded",
        {
            "tenant_id": str(tenant_id),
            "investigation_id": investigation_id,
            "recovery_id": recovery_id,
            "amount": str(amount),
            "confidence_tier": confidence_tier,
            "methodology_tag": methodology_tag,
            "occurred_at": _now_iso(),
        },
    )


def publish_recovery_collected(
    *,
    tenant_id: uuid.UUID,
    investigation_id: str,
    recovery_id: str,
    amount: Decimal,
) -> None:
    publish(
        "fwa.recovery_collected",
        {
            "tenant_id": str(tenant_id),
            "investigation_id": investigation_id,
            "recovery_id": recovery_id,
            "amount": str(amount),
            "occurred_at": _now_iso(),
        },
    )


def publish_pharmacy_risk_elevated(
    *,
    tenant_id: uuid.UUID,
    pharmacy_npi: str,
    previous_score: int,
    new_score: int,
    threshold_crossed: int,
) -> None:
    publish(
        "fwa.pharmacy_risk_elevated",
        {
            "tenant_id": str(tenant_id),
            "pharmacy_npi": pharmacy_npi,
            "previous_score": previous_score,
            "new_score": new_score,
            "threshold_crossed": threshold_crossed,
            "occurred_at": _now_iso(),
        },
    )


def publish_suspicious_community_detected(
    *,
    tenant_id: uuid.UUID,
    community_id: str,
    node_count: int,
    self_referral_rate: float,
    total_amount: float,
) -> None:
    publish(
        "fwa.suspicious_community_detected",
        {
            "tenant_id": str(tenant_id),
            "community_id": community_id,
            "node_count": node_count,
            "self_referral_rate": self_referral_rate,
            "total_amount": total_amount,
            "occurred_at": _now_iso(),
        },
    )


def publish_tip_received(
    *,
    tenant_id: uuid.UUID,
    tip_id: str,
    tip_type: str,
    is_anonymous: bool,
) -> None:
    publish(
        "fwa.tip_received",
        {
            "tenant_id": str(tenant_id),
            "tip_id": tip_id,
            "tip_type": tip_type,
            "is_anonymous": is_anonymous,
            "occurred_at": _now_iso(),
        },
    )


def publish_watchlist_added(
    *,
    tenant_id: uuid.UUID,
    entity_type: str,
    entity_id: str,
    fraud_probability_30d: Decimal,
) -> None:
    publish(
        "fwa.watchlist_added",
        {
            "tenant_id": str(tenant_id),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "fraud_probability_30d": str(fraud_probability_30d),
            "occurred_at": _now_iso(),
        },
    )
