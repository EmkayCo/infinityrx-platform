# Event Contract: `member.updated`

**Schema version:** 1.0
**Status:** Active

## Description

A member's demographic or contact information has been updated.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `member_id` | `UUID` | yes | Member being updated |
| `changed_fields` | `list[str]` | yes | Field names that changed |
| `occurred_at` | `str (ISO-8601)` | yes | Update timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `member-management` | Member record updated |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | — | Downstream cache invalidation |

## Ordering Key Convention

**`ordering_key`:** `member_id`

## Idempotency Key Convention

**`idempotency_key`:** `member.updated:{member_id}:{occurred_at}`

## Example Payload

```json
{
  "event_type": "member.updated",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "member_id": "uuid",
  "changed_fields": ["address", "phone"],
  "occurred_at": "2026-04-14T09:00:00Z"
}
```
