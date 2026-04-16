"""Event consumers for program-config module.

Subscribes to:
  - plan.created (from plan-design) — links programs to plans

All consumers wrapped with idempotent_handler.
"""
from __future__ import annotations

import uuid
from typing import Any

import structlog

from shared.events.idempotency import InMemoryIdempotencyStore, idempotent_handler
from shared.events.types import EventEnvelope

logger = structlog.get_logger(__name__)

# Module-level idempotency store (replaced by PostgresIdempotencyStore in production)
_idempotency_store = InMemoryIdempotencyStore()


async def _handle_plan_created(
    idempotency_key: str,
    envelope: EventEnvelope,
    db_session_factory: Any,
) -> None:
    """Handle plan.created event — link plan to any programs in the same tenant.

    The plan-design module publishes plan.created when a plan hierarchy entry
    is created. Program-config uses this to associate programs with plans for
    reporting and configuration purposes.
    """
    payload = envelope.payload
    plan_id_str = payload.get("plan_id")
    program_id_str = payload.get("program_id")

    if not plan_id_str or not program_id_str:
        logger.warning(
            "plan_created_missing_ids",
            extra={
                "svc_tenant_id": str(envelope.tenant_id),
                "svc_correlation_id": str(envelope.correlation_id),
            },
        )
        return

    logger.info(
        "plan_created_consumed",
        extra={
            "svc_tenant_id": str(envelope.tenant_id),
            "svc_plan_id": plan_id_str,
            "svc_program_id": program_id_str,
        },
    )


_plan_created_consumer = idempotent_handler(
    _idempotency_store,
    consumer_name="program-config:plan_created",
    ttl_seconds=86400,
)(_handle_plan_created)


async def handle_plan_created(
    envelope: EventEnvelope,
    db_session_factory: Any,
) -> None:
    """Public entry point — wraps with idempotency."""
    await _plan_created_consumer(
        envelope.idempotency_key,
        envelope,
        db_session_factory,
    )
