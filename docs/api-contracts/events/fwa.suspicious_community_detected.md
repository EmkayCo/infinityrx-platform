# Event Contract: `fwa.suspicious_community_detected`

**Schema version:** 1.0
**Status:** Active

---

## Description

Graph analysis has identified a cluster of pharmacies and prescribers exhibiting
suspicious referral patterns consistent with a fraud community.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `community_id` | `str` | yes | Graph community identifier |
| `node_count` | `int` | yes | Number of entities in the community |
| `self_referral_rate` | `float` | yes | Fraction of claims within community (0.0–1.0) |
| `total_amount` | `str (Decimal)` | yes | Total claim value passing through community |
| `occurred_at` | `str (ISO-8601)` | yes | Detection timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | NetworkX community detection run identifies suspicious cluster |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | FWA summary | Add community to fraud network report |

---

## Ordering Key Convention

**`ordering_key`:** `community_id`

## Idempotency Key Convention

**`idempotency_key`:** `fwa.suspicious_community_detected:{community_id}`

---

## Example Payload

```json
{
  "event_type": "fwa.suspicious_community_detected",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "community_id": "com-uuid",
  "node_count": 12,
  "self_referral_rate": 0.87,
  "total_amount": "1250000.00",
  "occurred_at": "2026-04-14T08:00:00Z"
}
```

**Note (audit H-01):** `self_referral_rate` is published as `float` rather than
`Decimal` — this is intentional as it represents a ratio (0.0–1.0), not a
monetary amount. Financial fields (`total_amount`) use `str(Decimal)` per
financial-precision rules.
