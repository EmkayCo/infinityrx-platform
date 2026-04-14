# Event Contract: `fwa.tip_received`

**Schema version:** 1.0
**Status:** Active

---

## Description

A fraud tip has been submitted by an internal user or external reporter.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `tip_id` | `str` | yes | Internal tip identifier |
| `tip_type` | `str` | yes | `anonymous`, `member`, `employee`, `regulatory` |
| `is_anonymous` | `bool` | yes | Whether the submitter requested anonymity |
| `occurred_at` | `str (ISO-8601)` | yes | Submission timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | `POST /tips` accepted |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | — | Tip triggers manual investigation creation |

---

## Ordering Key Convention

**`ordering_key`:** `tip_id`

## Idempotency Key Convention

**`idempotency_key`:** `fwa.tip_received:{tip_id}`

---

## Example Payload

```json
{
  "event_type": "fwa.tip_received",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "tip_id": "tip-uuid",
  "tip_type": "employee",
  "is_anonymous": false,
  "occurred_at": "2026-04-14T13:00:00Z"
}
```
