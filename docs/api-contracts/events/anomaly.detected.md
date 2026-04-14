# Event Contract: `anomaly.detected`

**Schema version:** 1.0  
**Status:** Active

---

## Description

The FWA engine has detected a potential fraud/waste/abuse anomaly.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `anomaly_id` | `UUID` | yes | Unique anomaly identifier |
| `entity_type` | `str` | yes | provider | member | pharmacy |
| `entity_id` | `str` | yes | ID of the flagged entity |
| `anomaly_type` | `str` | yes | Type of anomaly detected |
| `confidence_score` | `str (Decimal 0-1)` | yes | ML confidence score |
| `claim_ids` | `list[UUID]` | no | Claims contributing to the anomaly |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | Emits on anomaly.detected |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** None — anomalies are independent events

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** anomaly:{anomaly_id}

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "40ad4494-5dd5-4b37-9d11-b2fb92ae8c85",
    "event_type": "anomaly.detected",
    "schema_version": "1.0",
    "tenant_id": "79fce16d-f2f7-4156-91a2-5425156f2ccc",
    "correlation_id": "0e6bde33-498c-44fa-987b-a2db96f8e7f3",
    "source_module": "reclaimrx",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "anomaly_id": "fe3edbd3-8091-4858-947e-61e797d4c50c",
        "entity_type": "example_entity_type",
        "entity_id": "example_entity_id",
        "anomaly_type": "example_anomaly_type",
        "confidence_score": "99.99",
        "claim_ids": "895849dc-83ef-476a-b32b-b803b1b0c454"
    }
}
```

---

<!-- populated as modules adopt this event -->
