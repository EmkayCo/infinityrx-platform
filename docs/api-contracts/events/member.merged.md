# Event Contract: `member.merged`

**Schema version:** 1.0
**Status:** Active

## Description

Two duplicate member records have been merged. The source member ID is now
archived; all references should point to the target.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `source_member_id` | `UUID` | yes | Archived (duplicate) member ID |
| `target_member_id` | `UUID` | yes | Surviving canonical member ID |
| `occurred_at` | `str (ISO-8601)` | yes | Merge timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `member-management` | Member deduplication merge confirmed |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `billing` | (planned) | Reassign AP records from source to target |
| `reclaimrx` | (planned) | Merge risk profiles |

## Ordering Key Convention

**`ordering_key`:** `source_member_id`

## Idempotency Key Convention

**`idempotency_key`:** `member.merged:{source_member_id}:{target_member_id}`

## Example Payload

```json
{
  "event_type": "member.merged",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "source_member_id": "uuid",
  "target_member_id": "uuid",
  "occurred_at": "2026-04-14T10:00:00Z"
}
```
