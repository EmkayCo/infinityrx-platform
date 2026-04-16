"""Event publishers for program-config module.

Events published:
  - program.created
  - program.activated
  - program.suspended
  - program.terminated
  - onboarding.step_completed
  - onboarding.go_live
  - contract.expiring_soon
  - brd.submitted
  - brd.approved
  - brd.applied

All events use EventEnvelope with:
  - ordering_key = program_id (entity-level ordering)
  - idempotency_key = business-level key (e.g., "program.created:{program_id}")
  - schema_version = "1.0"
  - tenant_id in envelope

Money amounts serialized as str() — never float.
"""
from __future__ import annotations

import uuid
from typing import Any

from shared.events.types import EventEnvelope

SOURCE_MODULE = "program-config"


def _make_envelope(
    event_type: str,
    tenant_id: uuid.UUID,
    payload: dict[str, Any],
    ordering_key: str,
    idempotency_key: str,
    correlation_id: uuid.UUID | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        tenant_id=tenant_id,
        correlation_id=correlation_id or uuid.uuid4(),
        source_module=SOURCE_MODULE,
        schema_version="1.0",
        ordering_key=ordering_key,
        idempotency_key=idempotency_key,
        payload=payload,
    )


def program_created_event(
    program_id: uuid.UUID,
    tenant_id: uuid.UUID,
    program_name: str,
    program_type: str,
    client_id: uuid.UUID,
    correlation_id: uuid.UUID | None = None,
) -> EventEnvelope:
    return _make_envelope(
        event_type="program.created",
        tenant_id=tenant_id,
        payload={
            "program_id": str(program_id),
            "program_name": program_name,
            "program_type": program_type,
            "client_id": str(client_id),
        },
        ordering_key=str(program_id),
        idempotency_key=f"program.created:{program_id}",
        correlation_id=correlation_id,
    )


def program_activated_event(
    program_id: uuid.UUID,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID | None = None,
) -> EventEnvelope:
    return _make_envelope(
        event_type="program.activated",
        tenant_id=tenant_id,
        payload={"program_id": str(program_id)},
        ordering_key=str(program_id),
        idempotency_key=f"program.activated:{program_id}",
        correlation_id=correlation_id,
    )


def program_suspended_event(
    program_id: uuid.UUID,
    tenant_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID | None = None,
) -> EventEnvelope:
    return _make_envelope(
        event_type="program.suspended",
        tenant_id=tenant_id,
        payload={"program_id": str(program_id), "reason": reason},
        ordering_key=str(program_id),
        idempotency_key=f"program.suspended:{program_id}",
        correlation_id=correlation_id,
    )


def program_terminated_event(
    program_id: uuid.UUID,
    tenant_id: uuid.UUID,
    reason: str,
    correlation_id: uuid.UUID | None = None,
) -> EventEnvelope:
    return _make_envelope(
        event_type="program.terminated",
        tenant_id=tenant_id,
        payload={"program_id": str(program_id), "reason": reason},
        ordering_key=str(program_id),
        idempotency_key=f"program.terminated:{program_id}",
        correlation_id=correlation_id,
    )


def onboarding_step_completed_event(
    workflow_id: uuid.UUID,
    program_id: uuid.UUID,
    tenant_id: uuid.UUID,
    step_number: int,
    step_name: str,
    correlation_id: uuid.UUID | None = None,
) -> EventEnvelope:
    return _make_envelope(
        event_type="onboarding.step_completed",
        tenant_id=tenant_id,
        payload={
            "workflow_id": str(workflow_id),
            "program_id": str(program_id),
            "step_number": step_number,
            "step_name": step_name,
        },
        ordering_key=str(program_id),
        idempotency_key=f"onboarding.step_completed:{workflow_id}:{step_number}",
        correlation_id=correlation_id,
    )


def onboarding_go_live_event(
    workflow_id: uuid.UUID,
    program_id: uuid.UUID,
    tenant_id: uuid.UUID,
    go_live_date: str,
    correlation_id: uuid.UUID | None = None,
) -> EventEnvelope:
    return _make_envelope(
        event_type="onboarding.go_live",
        tenant_id=tenant_id,
        payload={
            "workflow_id": str(workflow_id),
            "program_id": str(program_id),
            "go_live_date": go_live_date,
        },
        ordering_key=str(program_id),
        idempotency_key=f"onboarding.go_live:{workflow_id}",
        correlation_id=correlation_id,
    )


def contract_expiring_soon_event(
    contract_id: uuid.UUID,
    program_id: uuid.UUID,
    tenant_id: uuid.UUID,
    renewal_date: str,
    days_until_renewal: int,
    correlation_id: uuid.UUID | None = None,
) -> EventEnvelope:
    return _make_envelope(
        event_type="contract.expiring_soon",
        tenant_id=tenant_id,
        payload={
            "contract_id": str(contract_id),
            "program_id": str(program_id),
            "renewal_date": renewal_date,
            "days_until_renewal": days_until_renewal,
        },
        ordering_key=str(program_id),
        idempotency_key=f"contract.expiring_soon:{contract_id}",
        correlation_id=correlation_id,
    )


def brd_submitted_event(
    submission_id: uuid.UUID,
    program_id: uuid.UUID | None,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID | None = None,
) -> EventEnvelope:
    return _make_envelope(
        event_type="brd.submitted",
        tenant_id=tenant_id,
        payload={
            "submission_id": str(submission_id),
            "program_id": str(program_id) if program_id else None,
        },
        ordering_key=str(submission_id),
        idempotency_key=f"brd.submitted:{submission_id}",
        correlation_id=correlation_id,
    )


def brd_approved_event(
    submission_id: uuid.UUID,
    program_id: uuid.UUID | None,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID | None = None,
) -> EventEnvelope:
    return _make_envelope(
        event_type="brd.approved",
        tenant_id=tenant_id,
        payload={
            "submission_id": str(submission_id),
            "program_id": str(program_id) if program_id else None,
        },
        ordering_key=str(submission_id),
        idempotency_key=f"brd.approved:{submission_id}",
        correlation_id=correlation_id,
    )


def brd_applied_event(
    submission_id: uuid.UUID,
    program_id: uuid.UUID,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID | None = None,
) -> EventEnvelope:
    return _make_envelope(
        event_type="brd.applied",
        tenant_id=tenant_id,
        payload={
            "submission_id": str(submission_id),
            "program_id": str(program_id),
        },
        ordering_key=str(program_id),
        idempotency_key=f"brd.applied:{submission_id}:{program_id}",
        correlation_id=correlation_id,
    )
