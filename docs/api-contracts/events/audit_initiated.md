# Event Contract: `audit.initiated`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A formal audit has been initiated for an entity.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `audit_id` | `UUID` | yes | Unique audit identifier |
| `entity_type` | `str` | yes | Entity type under audit |
| `entity_id` | `str` | yes | Entity being audited |
| `initiated_by` | `UUID` | yes | User who initiated the audit |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | Emits on audit.initiated |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** audit_id

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** audit:{audit_id}

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "6cec8d54-e9e0-4ba9-9ddd-1bae7c9dba81",
    "event_type": "audit.initiated",
    "schema_version": "1.0",
    "tenant_id": "c42bf6ba-8f71-43b5-bbcb-916d350e89c5",
    "correlation_id": "fc49ff6e-7d64-4351-ab10-40e624fbcd50",
    "source_module": "reclaimrx",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "audit_id": "8ff26826-6645-431d-9bf8-5e58d31f0efa",
        "entity_type": "example_entity_type",
        "entity_id": "example_entity_id",
        "initiated_by": "57d224b1-091b-491b-a941-62089addf948"
    }
}
```

---

<!-- populated as modules adopt this event -->
