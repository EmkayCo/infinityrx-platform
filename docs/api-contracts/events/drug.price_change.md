# Event Contract: `drug.price_change`

**Schema version:** 1.0
**Status:** Active

## Description

A drug's reimbursement price (AWP, WAC, or MAC) has changed in the drug
database, potentially affecting claim adjudication amounts.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `ndc11` | `str` | yes | 11-digit NDC |
| `price_type` | `str` | yes | `AWP`, `WAC`, `MAC` |
| `old_price` | `str (Decimal)` | yes | Previous price per unit |
| `new_price` | `str (Decimal)` | yes | New price per unit |
| `effective_date` | `str (ISO-8601 date)` | yes | Price effective date |
| `occurred_at` | `str (ISO-8601)` | yes | Event timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `drug-database` | Price update received from data vendor |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(adjudication-engine)* | — | Invalidate pricing cache for NDC |
| `reporting` | — | Update drug cost trend reports |

## Ordering Key Convention

**`ordering_key`:** `ndc11`

## Idempotency Key Convention

**`idempotency_key`:** `drug.price_change:{ndc11}:{price_type}:{effective_date}`

## Example Payload

```json
{
  "event_type": "drug.price_change",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "ndc11": "12345678901",
  "price_type": "AWP",
  "old_price": "2.45",
  "new_price": "2.62",
  "effective_date": "2026-04-15",
  "occurred_at": "2026-04-14T00:00:00Z"
}
```
