"""Event publisher for prescriber-directory module.

All events use EventEnvelope per event-bus rules:
  - ordering_key: prescriber NPI
  - idempotency_key: prescriber:{npi}:{action}
  - schema_version: "1.0"
  - source_module: "prescriber-directory"

Events published:
  prescriber.created
  prescriber.updated
  prescriber.deactivated
  prescriber.dea_expired
  prescriber.license_expired
  prescriber.excluded
  prescriber.credential_expiring
  prescriber.relationship_updated
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any


def _make_envelope(
    event_type: str,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    npi: str,
    payload: dict[str, Any],
    action: str,
):
    """Build an EventEnvelope — not importing shared directly to avoid circular deps in tests."""
    try:
        from shared.events.types import EventEnvelope
        return EventEnvelope(  # pragma: no cover
            event_type=event_type,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="prescriber-directory",
            payload=payload,
            ordering_key=npi,
            idempotency_key=f"prescriber:{npi}:{action}",
            schema_version="1.0",
        )
    except ImportError:
        return {
            "event_type": event_type,
            "tenant_id": str(tenant_id),
            "correlation_id": str(correlation_id),
            "source_module": "prescriber-directory",
            "payload": payload,
            "ordering_key": npi,
            "idempotency_key": f"prescriber:{npi}:{action}",
            "schema_version": "1.0",
            "timestamp": datetime.now(UTC).isoformat(),
        }


def build_prescriber_created_event(npi: str, tenant_id: uuid.UUID, correlation_id: uuid.UUID, prescriber_data: dict) -> Any:
    return _make_envelope(
        event_type="prescriber.created",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        npi=npi,
        payload={"npi": npi, **prescriber_data},
        action="created",
    )


def build_prescriber_updated_event(npi: str, tenant_id: uuid.UUID, correlation_id: uuid.UUID, changes: dict) -> Any:
    return _make_envelope(
        event_type="prescriber.updated",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        npi=npi,
        payload={"npi": npi, "changes": changes},
        action="updated",
    )


def build_prescriber_deactivated_event(npi: str, tenant_id: uuid.UUID, correlation_id: uuid.UUID, reason: str) -> Any:
    return _make_envelope(
        event_type="prescriber.deactivated",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        npi=npi,
        payload={"npi": npi, "reason": reason},
        action="deactivated",
    )


def build_dea_expired_event(npi: str, tenant_id: uuid.UUID, correlation_id: uuid.UUID, expiry_date: str) -> Any:
    return _make_envelope(
        event_type="prescriber.dea_expired",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        npi=npi,
        payload={"npi": npi, "expiry_date": expiry_date},
        action="dea_expired",
    )


def build_excluded_event(npi: str, tenant_id: uuid.UUID, correlation_id: uuid.UUID, exclusion_type: str) -> Any:
    return _make_envelope(
        event_type="prescriber.excluded",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        npi=npi,
        payload={"npi": npi, "exclusion_type": exclusion_type},
        action="excluded",
    )


def build_relationship_updated_event(
    npi: str, tenant_id: uuid.UUID, correlation_id: uuid.UUID,
    pharmacy_npi: str, period_month: str, claim_count: int
) -> Any:
    return _make_envelope(
        event_type="prescriber.relationship_updated",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        npi=npi,
        payload={
            "prescriber_npi": npi,
            "pharmacy_npi": pharmacy_npi,
            "period_month": period_month,
            "claim_count": claim_count,
        },
        action=f"relationship_updated:{pharmacy_npi}:{period_month}",
    )
