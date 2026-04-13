# Event Contract: `claim.adjudicated`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A claim has completed adjudication with a final disposition.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `claim_id` | `UUID` | yes | Claim that was adjudicated |
| `disposition` | `str` | yes | paid | rejected | suspended |
| `copay_amount` | `str (Decimal)` | no | Member copay amount if paid |
| `plan_paid_amount` | `str (Decimal)` | no | Plan payment amount if paid |
| `rejection_codes` | `list[str]` | no | NCPDP reject codes if rejected |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `adjudication-engine` | Emits on claim.adjudicated |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** claim_id — ensures disposition events are ordered per claim

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** str(event_id) — default

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "5cbbd2c0-fa48-4b3e-a25f-34998401a6a0",
    "event_type": "claim.adjudicated",
    "schema_version": "1.0",
    "tenant_id": "c5b08737-d3ea-489b-bdcf-7473729a84b1",
    "correlation_id": "eb2ef9f3-c59d-48d3-8d92-59fc40feebb6",
    "source_module": "adjudication-engine",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "claim_id": "a4d8ddf3-c4d5-4294-84fa-5e2c9fcfff79",
        "disposition": "example_disposition",
        "copay_amount": "99.99",
        "plan_paid_amount": "99.99",
        "rejection_codes": []
    }
}
```

---

<!-- populated as modules adopt this event -->
