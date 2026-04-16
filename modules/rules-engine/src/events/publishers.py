"""Rules-engine event publishers.

Publishes structured domain events via EventEnvelope per event-bus rules.
All amounts serialized as str(Decimal) — never float.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from shared.events.bus import EventBus
from shared.events.types import EventEnvelope


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def publish_rule_evaluated(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    claim_id: str,
    rule_instance_id: str,
    rule_type_code: str,
    action: str,
    reject_code: str = "",
    correlation_id: uuid.UUID | None = None,
) -> None:
    """Publish when a single rule is evaluated against a claim."""
    cid = correlation_id or uuid.uuid4()
    await bus.publish(
        EventEnvelope(
            event_type="rule.evaluated",
            tenant_id=tenant_id,
            correlation_id=cid,
            source_module="rules-engine",
            schema_version="1.0",
            ordering_key=claim_id,
            idempotency_key=f"rule.evaluated:{claim_id}:{rule_instance_id}",
            payload={
                "tenant_id": str(tenant_id),
                "claim_id": claim_id,
                "rule_instance_id": rule_instance_id,
                "rule_type_code": rule_type_code,
                "action": action,
                "reject_code": reject_code,
                "occurred_at": _now(),
            },
        )
    )


async def publish_pipeline_completed(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    claim_id: str,
    plan_id: str,
    final_action: str,
    reject_code: str = "",
    total_rules: int = 0,
    execution_time_ms: int = 0,
    correlation_id: uuid.UUID | None = None,
) -> None:
    """Publish when a full pipeline execution completes."""
    cid = correlation_id or uuid.uuid4()
    await bus.publish(
        EventEnvelope(
            event_type="pipeline.completed",
            tenant_id=tenant_id,
            correlation_id=cid,
            source_module="rules-engine",
            schema_version="1.0",
            ordering_key=claim_id,
            idempotency_key=f"pipeline.completed:{claim_id}:{plan_id}",
            payload={
                "tenant_id": str(tenant_id),
                "claim_id": claim_id,
                "plan_id": plan_id,
                "final_action": final_action,
                "reject_code": reject_code,
                "total_rules": total_rules,
                "execution_time_ms": execution_time_ms,
                "occurred_at": _now(),
            },
        )
    )


async def publish_rule_conflict_detected(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    claim_id: str,
    plan_id: str,
    conflicts: list[str],
    correlation_id: uuid.UUID | None = None,
) -> None:
    """Publish when conflicting rule outcomes are detected in a pipeline."""
    cid = correlation_id or uuid.uuid4()
    await bus.publish(
        EventEnvelope(
            event_type="rule.conflict_detected",
            tenant_id=tenant_id,
            correlation_id=cid,
            source_module="rules-engine",
            schema_version="1.0",
            ordering_key=claim_id,
            idempotency_key=f"rule.conflict_detected:{claim_id}:{plan_id}",
            payload={
                "tenant_id": str(tenant_id),
                "claim_id": claim_id,
                "plan_id": plan_id,
                "conflicts": conflicts,
                "occurred_at": _now(),
            },
        )
    )
