# Event Contract: `drug.new_product`

**Schema version:** 1.0
**Status:** Active

## Description

A new drug product has been added to the drug database (new NDC, new
approval, or new formulation).

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `ndc11` | `str` | yes | 11-digit NDC of new product |
| `drug_name` | `str` | yes | Drug name |
| `dosage_form` | `str` | yes | Dosage form code |
| `strength` | `str` | no | Drug strength string |
| `requires_pa` | `bool` | yes | Whether PA is required by default |
| `occurred_at` | `str (ISO-8601)` | yes | Event timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `drug-database` | New NDC added to product catalog |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(plan-design)* | — | Add to formulary review queue |

## Ordering Key Convention

**`ordering_key`:** `ndc11`

## Idempotency Key Convention

**`idempotency_key`:** `drug.new_product:{ndc11}`

## Example Payload

```json
{
  "event_type": "drug.new_product",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "ndc11": "12345678901",
  "drug_name": "Ozempic",
  "dosage_form": "SYR",
  "strength": "0.5 mg/dose",
  "requires_pa": true,
  "occurred_at": "2026-04-14T00:00:00Z"
}
```
