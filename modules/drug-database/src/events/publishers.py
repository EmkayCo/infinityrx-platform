"""Drug database event publishers.

All events use EventEnvelope with:
- ordering_key: ndc_11 or data_source
- idempotency_key: business-level key
- schema_version: "1.0"
- dot-notation event types: drug.price_change, drug.new_product, etc.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from shared.events.bus import EventBus
from shared.events.types import EventEnvelope

logger = logging.getLogger(__name__)

_SOURCE_MODULE = "drug-database"


async def publish_price_change(
    bus: EventBus,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    ndc_11: str,
    drug_name: str,
    price_type: str,
    old_price: Decimal,
    new_price: Decimal,
    change_pct: Decimal,
    effective_date: date,
) -> None:
    envelope = EventEnvelope(
        event_type="drug.price_change",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=_SOURCE_MODULE,
        schema_version="1.0",
        ordering_key=ndc_11,
        idempotency_key=f"drug.price_change:{ndc_11}:{price_type}:{effective_date.isoformat()}",
        payload={
            "ndc_11": ndc_11,
            "drug_name": drug_name,
            "price_type": price_type,
            "old_price": str(old_price),
            "new_price": str(new_price),
            "change_pct": str(change_pct),
            "effective_date": effective_date.isoformat(),
        },
    )
    await bus.publish(envelope)
    logger.info(
        "published drug.price_change",
        extra={"svc_name": "drug_db_publisher", "drug_ndc": ndc_11},
    )


async def publish_new_product(
    bus: EventBus,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    ndc_11: str,
    drug_name: str,
    data_source: str,
) -> None:
    envelope = EventEnvelope(
        event_type="drug.new_product",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=_SOURCE_MODULE,
        schema_version="1.0",
        ordering_key=ndc_11,
        idempotency_key=f"drug.new_product:{ndc_11}:{data_source}",
        payload={
            "ndc_11": ndc_11,
            "drug_name": drug_name,
            "data_source": data_source,
        },
    )
    await bus.publish(envelope)


async def publish_discontinued(
    bus: EventBus,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    ndc_11: str,
    drug_name: str,
) -> None:
    envelope = EventEnvelope(
        event_type="drug.discontinued",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=_SOURCE_MODULE,
        schema_version="1.0",
        ordering_key=ndc_11,
        idempotency_key=f"drug.discontinued:{ndc_11}",
        payload={"ndc_11": ndc_11, "drug_name": drug_name},
    )
    await bus.publish(envelope)


async def publish_refresh_completed(
    bus: EventBus,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    data_source: str,
    stats: dict[str, Any],
) -> None:
    envelope = EventEnvelope(
        event_type="drug.refresh_completed",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=_SOURCE_MODULE,
        schema_version="1.0",
        ordering_key=data_source,
        idempotency_key=f"drug.refresh_completed:{data_source}:{stats.get('started_at', '')}",
        payload={"data_source": data_source, **stats},
    )
    await bus.publish(envelope)


async def publish_generic_available(
    bus: EventBus,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    brand_ndc: str,
    generic_ndc: str,
    te_code: str,
    generic_name: str,
) -> None:
    envelope = EventEnvelope(
        event_type="drug.generic_available",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=_SOURCE_MODULE,
        schema_version="1.0",
        ordering_key=brand_ndc,
        idempotency_key=f"drug.generic_available:{brand_ndc}:{generic_ndc}",
        payload={
            "brand_ndc": brand_ndc,
            "generic_ndc": generic_ndc,
            "te_code": te_code,
            "generic_name": generic_name,
        },
    )
    await bus.publish(envelope)
