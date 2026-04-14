# Event Contract: `fwa.investigation_opened`

**Schema version:** 1.0
**Status:** Active

---

## Description

A new FWA investigation work item has been created and assigned to the
investigation queue.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `investigation_id` | `str` | yes | Internal investigation ID |
| `investigation_number` | `str` | yes | Human-readable reference number |
| `subject_type` | `str` | yes | `pharmacy`, `prescriber`, `member` |
| `subject_entity_id` | `str` | yes | NPI, member ID, or other entity identifier |
| `investigation_type` | `str` | yes | `fraud`, `waste`, `abuse`, `tip` |
| `priority` | `str` | yes | `low`, `medium`, `high`, `critical` |
| `occurred_at` | `str (ISO-8601)` | yes | Investigation creation timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | Investigation work item created |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | `handle_fwa_investigation_opened` | Update investigation count in FWA summary |

---

## Ordering Key Convention

**`ordering_key`:** `investigation_id`

## Idempotency Key Convention

**`idempotency_key`:** `fwa.investigation_opened:{investigation_id}`

---

## Example Payload

```json
{
  "event_type": "fwa.investigation_opened",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "investigation_id": "inv-uuid",
  "investigation_number": "INV-2026-001",
  "subject_type": "pharmacy",
  "subject_entity_id": "1234567890",
  "investigation_type": "fraud",
  "priority": "high",
  "occurred_at": "2026-04-14T10:10:00Z"
}
```
