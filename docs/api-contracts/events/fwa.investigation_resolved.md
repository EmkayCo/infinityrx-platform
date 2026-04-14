# Event Contract: `fwa.investigation_resolved`

**Schema version:** 1.0
**Status:** Active

---

## Description

An FWA investigation has been closed with a resolution decision.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `investigation_id` | `str` | yes | Investigation being resolved |
| `investigation_number` | `str` | yes | Human-readable reference |
| `resolution_type` | `str` | yes | `confirmed_fraud`, `waste`, `abuse`, `unfounded`, `referred_law_enforcement` |
| `actual_recovered` | `str (Decimal)` | yes | Dollar amount actually recovered (0.00 if none) |
| `occurred_at` | `str (ISO-8601)` | yes | Resolution timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | Investigation closed via resolution workflow |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | `handle_fwa_investigation_resolved` | Update resolution metrics, add to FWA summary |

---

## Ordering Key Convention

**`ordering_key`:** `investigation_id`

## Idempotency Key Convention

**`idempotency_key`:** `fwa.investigation_resolved:{investigation_id}`

---

## Example Payload

```json
{
  "event_type": "fwa.investigation_resolved",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "investigation_id": "inv-uuid",
  "investigation_number": "INV-2026-001",
  "resolution_type": "confirmed_fraud",
  "actual_recovered": "12500.00",
  "occurred_at": "2026-04-14T16:00:00Z"
}
```
