"""Pharmacy event publisher — dot-notation event types per event-bus rules."""
from __future__ import annotations

from uuid import UUID

from shared.events.bus import EventBus
from shared.events.types import EventEnvelope

_SOURCE = "pharmacy-directory"


async def publish_pharmacy_created(
    bus: EventBus,
    tenant_id: UUID,
    correlation_id: UUID,
    pharmacy_id: str,
    npi: str,
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="pharmacy.created",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module=_SOURCE,
            schema_version="1.0",
            ordering_key=pharmacy_id,
            idempotency_key=f"pharmacy.created:{pharmacy_id}",
            payload={"pharmacy_id": pharmacy_id, "npi": npi},
        )
    )


async def publish_pharmacy_updated(
    bus: EventBus,
    tenant_id: UUID,
    correlation_id: UUID,
    pharmacy_id: str,
    npi: str,
    changed_fields: list[str],
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="pharmacy.updated",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module=_SOURCE,
            schema_version="1.0",
            ordering_key=pharmacy_id,
            idempotency_key=f"pharmacy.updated:{pharmacy_id}:{','.join(sorted(changed_fields))}",
            payload={
                "pharmacy_id": pharmacy_id,
                "npi": npi,
                "changed_fields": changed_fields,
            },
        )
    )


async def publish_pharmacy_ownership_changed(
    bus: EventBus,
    tenant_id: UUID,
    correlation_id: UUID,
    pharmacy_id: str,
    npi: str,
    previous_owner: str | None,
    new_owner: str | None,
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="pharmacy.ownership_changed",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module=_SOURCE,
            schema_version="1.0",
            ordering_key=pharmacy_id,
            idempotency_key=f"pharmacy.ownership_changed:{pharmacy_id}",
            payload={
                "pharmacy_id": pharmacy_id,
                "npi": npi,
                "previous_owner": previous_owner,
                "new_owner": new_owner,
            },
        )
    )


async def publish_pharmacy_deactivated(
    bus: EventBus,
    tenant_id: UUID,
    correlation_id: UUID,
    pharmacy_id: str,
    npi: str,
    reason: str | None = None,
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="pharmacy.deactivated",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module=_SOURCE,
            schema_version="1.0",
            ordering_key=pharmacy_id,
            idempotency_key=f"pharmacy.deactivated:{pharmacy_id}",
            payload={"pharmacy_id": pharmacy_id, "npi": npi, "reason": reason},
        )
    )


async def publish_network_added(
    bus: EventBus,
    tenant_id: UUID,
    correlation_id: UUID,
    pharmacy_id: str,
    network_id: str,
    membership_id: str,
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="pharmacy.network_added",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module=_SOURCE,
            schema_version="1.0",
            ordering_key=membership_id,
            idempotency_key=f"pharmacy.network_added:{membership_id}",
            payload={
                "pharmacy_id": pharmacy_id,
                "network_id": network_id,
                "membership_id": membership_id,
            },
        )
    )


async def publish_network_removed(
    bus: EventBus,
    tenant_id: UUID,
    correlation_id: UUID,
    pharmacy_id: str,
    network_id: str,
    membership_id: str,
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="pharmacy.network_removed",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module=_SOURCE,
            schema_version="1.0",
            ordering_key=membership_id,
            idempotency_key=f"pharmacy.network_removed:{membership_id}",
            payload={
                "pharmacy_id": pharmacy_id,
                "network_id": network_id,
                "membership_id": membership_id,
            },
        )
    )


async def publish_credential_expiring(
    bus: EventBus,
    tenant_id: UUID,
    correlation_id: UUID,
    pharmacy_id: str,
    npi: str,
    credential_type: str,
    days_until_expiry: int,
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="pharmacy.credential_expiring",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module=_SOURCE,
            schema_version="1.0",
            ordering_key=pharmacy_id,
            idempotency_key=f"pharmacy.credential_expiring:{pharmacy_id}:{credential_type}:{days_until_expiry}",
            payload={
                "pharmacy_id": pharmacy_id,
                "npi": npi,
                "credential_type": credential_type,
                "days_until_expiry": days_until_expiry,
            },
        )
    )


async def publish_credentialing_completed(
    bus: EventBus,
    tenant_id: UUID,
    correlation_id: UUID,
    application_id: str,
    pharmacy_id: str,
    npi: str,
    decision: str,
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="pharmacy.credentialing_completed",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module=_SOURCE,
            schema_version="1.0",
            ordering_key=application_id,
            idempotency_key=f"pharmacy.credentialing_completed:{application_id}",
            payload={
                "application_id": application_id,
                "pharmacy_id": pharmacy_id,
                "npi": npi,
                "decision": decision,
            },
        )
    )


async def publish_application_submitted(
    bus: EventBus,
    tenant_id: UUID,
    correlation_id: UUID,
    application_id: str,
    npi: str,
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="pharmacy.application_submitted",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module=_SOURCE,
            schema_version="1.0",
            ordering_key=application_id,
            idempotency_key=f"pharmacy.application_submitted:{application_id}",
            payload={"application_id": application_id, "npi": npi},
        )
    )
