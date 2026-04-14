# Event Contract: `drug.discontinued`

**Schema version:** 1.0
**Status:** Active

## Description

A drug product has been discontinued and removed from the active formulary.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `ndc11` | `str` | yes | Discontinued drug NDC |
| `drug_name` | `str` | yes | Drug name |
| `discontinuation_date` | `str (ISO-8601 date)` | yes | Effective discontinuation date |
| `occurred_at` | `str (ISO-8601)` | yes | Event timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `drug-database` | Drug marked discontinued in product catalog |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(plan-design)* | — | Remove from formulary, trigger member notification |

## Ordering Key Convention

**`ordering_key`:** `ndc11`

## Idempotency Key Convention

**`idempotency_key`:** `drug.discontinued:{ndc11}:{discontinuation_date}`

## Example Payload

```json
{
  "event_type": "drug.discontinued",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "ndc11": "12345678901",
  "drug_name": "Brand Medication",
  "discontinuation_date": "2026-06-01",
  "occurred_at": "2026-04-14T00:00:00Z"
}
```
