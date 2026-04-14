# Event Contract: `member.enrolled`

**Schema version:** 1.0
**Status:** Active

## Description

A new member has been enrolled in a health benefit plan. Published by
member-management after 834 or CSV ingestion creates a new member record.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `member_id` | `UUID` | yes | Internal member identifier |
| `plan_id` | `str` | yes | Benefit plan identifier |
| `effective_date` | `str (ISO-8601 date)` | yes | Enrollment effective date |
| `occurred_at` | `str (ISO-8601)` | yes | Event timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `member-management` | New member record created via 834/CSV ingestion |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `billing` | `handle_member_enrolled` | Seed billing record for member |
| `reporting` | dashboard | Increment enrollment count |

## Ordering Key Convention

**`ordering_key`:** `member_id`

## Idempotency Key Convention

**`idempotency_key`:** `member.enrolled:{member_id}:{effective_date}`

## Example Payload

```json
{
  "event_type": "member.enrolled",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "member_id": "uuid",
  "plan_id": "PLAN-001",
  "effective_date": "2026-01-01",
  "occurred_at": "2025-11-01T10:00:00Z"
}
```
