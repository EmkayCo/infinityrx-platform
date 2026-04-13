# Event Contract: `payment.generated`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A payment record has been generated for disbursement.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `payment_id` | `UUID` | yes | Unique payment identifier |
| `payment_batch_id` | `UUID` | yes | Batch this payment belongs to |
| `payee_npi` | `str` | yes | NPI of the receiving pharmacy |
| `amount` | `str (Decimal)` | yes | Payment amount |
| `payment_method` | `str` | yes | ach | check | wire |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `payment-processing` | Emits on payment.generated |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** payment_batch_id — all payment events for same batch ordered together

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** payment:{payment_id} — business-level dedup prevents duplicate payments

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "48dfa77d-dae9-4525-8b52-9d2c3919315a",
    "event_type": "payment.generated",
    "schema_version": "1.0",
    "tenant_id": "6d45e813-cfa0-4c51-9002-9d87d9f7a6e4",
    "correlation_id": "c4d1c0e9-53ff-49b5-92df-764dacad6872",
    "source_module": "payment-processing",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "payment_id": "ffffd3a9-94e0-425c-a963-8c8d78ad8465",
        "payment_batch_id": "a03866e7-cc92-46ee-93af-b6b00f17d268",
        "payee_npi": "example_payee_npi",
        "amount": "99.99",
        "payment_method": "example_payment_method"
    }
}
```

---

<!-- populated as modules adopt this event -->
