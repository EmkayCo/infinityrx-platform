# Event Contract: `fwa.pharmacy_risk_elevated`

**Schema version:** 1.0
**Status:** Active

---

## Description

A pharmacy's composite risk score has crossed a threshold, escalating it
to a higher monitoring tier.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `pharmacy_npi` | `str` | yes | NPI of the pharmacy |
| `previous_score` | `int` | yes | Risk score before this event (0–100) |
| `new_score` | `int` | yes | Risk score after this event (0–100) |
| `threshold_crossed` | `int` | yes | Threshold that was crossed |
| `occurred_at` | `str (ISO-8601)` | yes | Score update timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | Pharmacy risk profile score update crosses a configured threshold |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `pharmacy-directory` | (planned) | Flag pharmacy for enhanced credentialing review |

---

## Ordering Key Convention

**`ordering_key`:** `pharmacy_npi`

## Idempotency Key Convention

**`idempotency_key`:** `fwa.pharmacy_risk_elevated:{pharmacy_npi}:{threshold_crossed}`

---

## Example Payload

```json
{
  "event_type": "fwa.pharmacy_risk_elevated",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "pharmacy_npi": "1234567890",
  "previous_score": 45,
  "new_score": 72,
  "threshold_crossed": 70,
  "occurred_at": "2026-04-14T11:00:00Z"
}
```
