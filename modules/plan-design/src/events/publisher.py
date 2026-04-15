"""Plan Design event publisher — PRD §13.

Publishes:
  plan.created, plan.updated, plan.terminated, plan.promoted_to_production,
  formulary.updated, formulary.drug_tier_changed, formulary.fb60_published,
  network.pharmacy_added, network.pharmacy_removed, network.awp_application_received
"""

from __future__ import annotations

import uuid
from typing import Any

from shared.events.bus import EventBus
from shared.events.types import EventEnvelope

_SOURCE_MODULE = "plan-design"


def _make_envelope(
    event_type: str,
    tenant_id: uuid.UUID,
    payload: dict[str, Any],
    entity_id: str,
) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        tenant_id=tenant_id,
        correlation_id=uuid.uuid4(),
        source_module=_SOURCE_MODULE,
        schema_version="1.0",
        ordering_key=entity_id,
        idempotency_key=f"{event_type}:{entity_id}:{uuid.uuid4()}",
        payload=payload,
    )


async def publish_plan_created(
    bus: EventBus, tenant_id: uuid.UUID, plan_id: uuid.UUID, plan_name: str
) -> None:
    envelope = _make_envelope(
        "plan.created",
        tenant_id,
        {"plan_id": str(plan_id), "plan_name": plan_name},
        str(plan_id),
    )
    await bus.publish(envelope)


async def publish_plan_updated(
    bus: EventBus, tenant_id: uuid.UUID, plan_id: uuid.UUID, changes: dict[str, Any]
) -> None:
    envelope = _make_envelope(
        "plan.updated",
        tenant_id,
        {"plan_id": str(plan_id), "changes": changes},
        str(plan_id),
    )
    await bus.publish(envelope)


async def publish_plan_terminated(
    bus: EventBus, tenant_id: uuid.UUID, plan_id: uuid.UUID
) -> None:
    envelope = _make_envelope(
        "plan.terminated",
        tenant_id,
        {"plan_id": str(plan_id)},
        str(plan_id),
    )
    await bus.publish(envelope)


async def publish_plan_promoted(
    bus: EventBus, tenant_id: uuid.UUID, plan_id: uuid.UUID
) -> None:
    envelope = _make_envelope(
        "plan.promoted_to_production",
        tenant_id,
        {"plan_id": str(plan_id)},
        str(plan_id),
    )
    await bus.publish(envelope)


async def publish_formulary_updated(
    bus: EventBus, tenant_id: uuid.UUID, formulary_id: uuid.UUID
) -> None:
    envelope = _make_envelope(
        "formulary.updated",
        tenant_id,
        {"formulary_id": str(formulary_id)},
        str(formulary_id),
    )
    await bus.publish(envelope)


async def publish_drug_tier_changed(
    bus: EventBus,
    tenant_id: uuid.UUID,
    formulary_id: uuid.UUID,
    ndc: str,
    old_tier: str,
    new_tier: str,
) -> None:
    envelope = _make_envelope(
        "formulary.drug_tier_changed",
        tenant_id,
        {
            "formulary_id": str(formulary_id),
            "ndc": ndc,
            "old_tier": old_tier,
            "new_tier": new_tier,
        },
        str(formulary_id),
    )
    await bus.publish(envelope)


async def publish_fb60_published(
    bus: EventBus,
    tenant_id: uuid.UUID,
    formulary_id: uuid.UUID,
    publication_id: uuid.UUID,
) -> None:
    envelope = _make_envelope(
        "formulary.fb60_published",
        tenant_id,
        {
            "formulary_id": str(formulary_id),
            "publication_id": str(publication_id),
        },
        str(formulary_id),
    )
    await bus.publish(envelope)


async def publish_pharmacy_added(
    bus: EventBus, tenant_id: uuid.UUID, network_id: uuid.UUID, npi: str
) -> None:
    envelope = _make_envelope(
        "network.pharmacy_added",
        tenant_id,
        {"network_id": str(network_id), "npi": npi},
        str(network_id),
    )
    await bus.publish(envelope)


async def publish_pharmacy_removed(
    bus: EventBus, tenant_id: uuid.UUID, network_id: uuid.UUID, npi: str
) -> None:
    envelope = _make_envelope(
        "network.pharmacy_removed",
        tenant_id,
        {"network_id": str(network_id), "npi": npi},
        str(network_id),
    )
    await bus.publish(envelope)


async def publish_awp_application_received(
    bus: EventBus,
    tenant_id: uuid.UUID,
    network_id: uuid.UUID,
    application_id: uuid.UUID,
    pharmacy_npi: str,
) -> None:
    envelope = _make_envelope(
        "network.awp_application_received",
        tenant_id,
        {
            "network_id": str(network_id),
            "application_id": str(application_id),
            "pharmacy_npi": pharmacy_npi,
        },
        str(network_id),
    )
    await bus.publish(envelope)
