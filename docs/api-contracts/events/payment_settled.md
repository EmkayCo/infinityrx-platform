# Event Contract: `payment.settled`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A payment has been confirmed as settled by the financial institution.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `payment_id` | `UUID` | yes | Payment that settled |
| `settled_at` | `str (ISO 8601)` | yes | Settlement timestamp |
| `bank_reference` | `str` | no | Bank transaction reference number |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `payment-processing` | Emits on payment.settled |

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

**`idempotency_key`:** payment_settle:{payment_id}

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "6200c3f0-c908-42d8-8b1c-1bbfff601db9",
    "event_type": "payment.settled",
    "schema_version": "1.0",
    "tenant_id": "3fb891e8-3e27-4194-907a-449cb17ce18c",
    "correlation_id": "3441a128-d20a-4540-8a52-424f5c5aa88a",
    "source_module": "payment-processing",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "payment_id": "c664a813-97d3-413c-a845-386e51f0a982",
        "settled_at": "2026-04-12T10:30:00Z",
        "bank_reference": "example_bank_reference"
    }
}
```

---

<!-- populated as modules adopt this event -->
