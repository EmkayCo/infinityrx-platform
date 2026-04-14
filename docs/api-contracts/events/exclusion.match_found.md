# Event Contract: `exclusion.match_found`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A government exclusion list match has been found for a provider or entity.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `exclusion_list_id` | `int` | yes | ID of the exclusion list record |
| `entity_type` | `str` | yes | provider | member | organization |
| `entity_id` | `str` | yes | ID of the matched entity |
| `match_confidence` | `str` | yes | exact | probable | possible |
| `source` | `str` | yes | OIG | SAM | OFAC |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `core-platform` | Emits on exclusion.match_found |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** None — exclusion matches are independent alerts

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** exclusion:{exclusion_list_id}:{entity_id}

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "319eb985-d5f7-4161-9891-e7a38f6c17e0",
    "event_type": "exclusion.match_found",
    "schema_version": "1.0",
    "tenant_id": "a5235573-3f59-45f4-acf7-79da6e8c1d4c",
    "correlation_id": "7f4af3df-cf5e-4dc3-bd53-f91b2cd4118e",
    "source_module": "core-platform",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "exclusion_list_id": 1,
        "entity_type": "example_entity_type",
        "entity_id": "example_entity_id",
        "match_confidence": "example_match_confidence",
        "source": "example_source"
    }
}
```

---

<!-- populated as modules adopt this event -->
