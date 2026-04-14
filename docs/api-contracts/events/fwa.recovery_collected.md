# Event Contract: `fwa.recovery_collected`

**Schema version:** 1.0
**Status:** Active

---

## Description

A recovery payment has been received against an outstanding FWA recovery demand.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `investigation_id` | `str` | yes | Parent investigation |
| `recovery_id` | `str` | yes | Recovery demand that was collected against |
| `amount` | `str (Decimal)` | yes | Amount collected |
| `occurred_at` | `str (ISO-8601)` | yes | Collection timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | Recovery payment recorded |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `billing` | (planned) | Close or reduce AR recovery record |
| `reporting` | metrics | Update recovered amount in FWA dashboard |

---

## Ordering Key Convention

**`ordering_key`:** `recovery_id`

## Idempotency Key Convention

**`idempotency_key`:** `fwa.recovery_collected:{recovery_id}:{occurred_at}`

---

## Example Payload

```json
{
  "event_type": "fwa.recovery_collected",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "investigation_id": "inv-uuid",
  "recovery_id": "rec-uuid",
  "amount": "8750.00",
  "occurred_at": "2026-04-14T17:00:00Z"
}
```
