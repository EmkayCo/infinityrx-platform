# Event Contract: `payment.returned`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A payment has been returned (e.g., ACH return, bounced check).

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `payment_id` | `UUID` | yes | Payment that was returned |
| `return_code` | `str` | yes | NACHA return code (e.g., R01, R02) |
| `return_reason` | `str` | yes | Human-readable return reason |
| `returned_at` | `str (ISO 8601)` | yes | Return timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `payment-processing` | Emits on payment.returned |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** payment_batch_id

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** payment_return:{payment_id}:{return_code}

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "44d834a4-c41d-499a-b27b-ded9b30d610e",
    "event_type": "payment.returned",
    "schema_version": "1.0",
    "tenant_id": "6670f27d-b683-4513-9821-bbc6c397bb6f",
    "correlation_id": "2d634ad8-2fac-45c7-b125-42c2462f9b6d",
    "source_module": "payment-processing",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "payment_id": "51190365-5c17-4936-a52f-0f688db0c10d",
        "return_code": "example_return_code",
        "return_reason": "example_return_reason",
        "returned_at": "2026-04-12T10:30:00Z"
    }
}
```

---

<!-- populated as modules adopt this event -->
