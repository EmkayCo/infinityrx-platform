# Event Contract: `fwa.watchlist_added`

**Schema version:** 1.0
**Status:** Active

---

## Description

An entity (pharmacy, prescriber, or member) has been added to the FWA watchlist
for ongoing enhanced monitoring.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `entity_type` | `str` | yes | `pharmacy`, `prescriber`, `member` |
| `entity_id` | `str` | yes | NPI, member ID, or other identifier |
| `fraud_probability_30d` | `str (Decimal)` | yes | 30-day fraud probability from ML model (0.00–1.00) |
| `occurred_at` | `str (ISO-8601)` | yes | Watchlist addition timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | ML model score or manual action adds entity to watchlist |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `pharmacy-directory` | (planned) | Flag pharmacy for enhanced network review |

---

## Ordering Key Convention

**`ordering_key`:** `entity_id`

## Idempotency Key Convention

**`idempotency_key`:** `fwa.watchlist_added:{entity_type}:{entity_id}`

---

## Example Payload

```json
{
  "event_type": "fwa.watchlist_added",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "entity_type": "pharmacy",
  "entity_id": "1234567890",
  "fraud_probability_30d": "0.84",
  "occurred_at": "2026-04-14T12:00:00Z"
}
```
