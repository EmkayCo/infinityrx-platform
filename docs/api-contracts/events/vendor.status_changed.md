# Event Contract: `vendor.status_changed`

**Schema version:** 1.0
**Status:** Active

---

## Description

A payment vendor adapter's connectivity status has changed (e.g., from
`healthy` to `degraded` or `offline`).

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `str` | yes | Tenant context |
| `vendor_adapter_id` | `str` | yes | Vendor adapter record ID |
| `old_status` | `str` | yes | Previous status |
| `new_status` | `str` | yes | New status (`healthy`, `degraded`, `offline`) |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `payment-processing` | Health check detects status change |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | — | Monitoring / alerting |

---

## Ordering Key Convention

**`ordering_key`:** `vendor_adapter_id`

## Idempotency Key Convention

**`idempotency_key`:** `vendor.status_changed:{vendor_adapter_id}:{new_status}`

---

## Example Payload

```json
{
  "event_type": "vendor.status_changed",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "vendor_adapter_id": "vendor-uuid",
  "old_status": "healthy",
  "new_status": "degraded"
}
```
