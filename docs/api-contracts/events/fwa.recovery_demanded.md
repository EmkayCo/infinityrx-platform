# Event Contract: `fwa.recovery_demanded`

**Schema version:** 1.0
**Status:** Active

---

## Description

A financial recovery demand has been issued to a pharmacy or prescriber as
part of an FWA investigation.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `investigation_id` | `str` | yes | Parent investigation |
| `recovery_id` | `str` | yes | Recovery demand ID |
| `amount` | `str (Decimal)` | yes | Demanded recovery amount |
| `confidence_tier` | `str` | yes | `high`, `medium`, `low` — affects legal defensibility |
| `methodology_tag` | `str` | yes | Recovery methodology used |
| `occurred_at` | `str (ISO-8601)` | yes | Demand timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | Recovery demand created in investigation |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `billing` | (planned) | Create AR record for recovery demand |

---

## Ordering Key Convention

**`ordering_key`:** `investigation_id`

## Idempotency Key Convention

**`idempotency_key`:** `fwa.recovery_demanded:{recovery_id}`

---

## Example Payload

```json
{
  "event_type": "fwa.recovery_demanded",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "investigation_id": "inv-uuid",
  "recovery_id": "rec-uuid",
  "amount": "8750.00",
  "confidence_tier": "high",
  "methodology_tag": "STATISTICAL_EXTRAPOLATION",
  "occurred_at": "2026-04-14T14:00:00Z"
}
```
