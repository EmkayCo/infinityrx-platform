# Event Contract: `drug.generic_available`

**Schema version:** 1.0
**Status:** Active

## Description

A generic equivalent has become available for a brand-name drug, enabling
step-therapy and formulary update opportunities.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `brand_ndc11` | `str` | yes | Brand drug NDC |
| `generic_ndc11` | `str` | yes | First generic NDC |
| `drug_name` | `str` | yes | Generic drug name |
| `effective_date` | `str (ISO-8601 date)` | yes | Generic availability date |
| `occurred_at` | `str (ISO-8601)` | yes | Event timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `drug-database` | Generic entry detected in data feed |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(plan-design)* | — | Trigger formulary review workflow |

## Ordering Key Convention

**`ordering_key`:** `brand_ndc11`

## Idempotency Key Convention

**`idempotency_key`:** `drug.generic_available:{brand_ndc11}:{effective_date}`

## Example Payload

```json
{
  "event_type": "drug.generic_available",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "brand_ndc11": "12345678901",
  "generic_ndc11": "98765432100",
  "drug_name": "Metformin HCl",
  "effective_date": "2026-05-01",
  "occurred_at": "2026-04-14T00:00:00Z"
}
```
