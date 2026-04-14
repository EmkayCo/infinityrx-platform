# Event Contract: `member.plan_changed`

**Schema version:** 1.0
**Status:** Active

## Description

A member has moved from one benefit plan to another (e.g., open enrollment
change or mid-year plan switch).

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `member_id` | `UUID` | yes | Member whose plan changed |
| `old_plan_id` | `str` | yes | Previous plan identifier |
| `new_plan_id` | `str` | yes | New plan identifier |
| `effective_date` | `str (ISO-8601 date)` | yes | Plan change effective date |
| `occurred_at` | `str (ISO-8601)` | yes | Event timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `member-management` | 834 transaction or manual plan change |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `billing` | (planned) | Update routing rules for member |

## Ordering Key Convention

**`ordering_key`:** `member_id`

## Idempotency Key Convention

**`idempotency_key`:** `member.plan_changed:{member_id}:{effective_date}`

## Example Payload

```json
{
  "event_type": "member.plan_changed",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "member_id": "uuid",
  "old_plan_id": "PLAN-001",
  "new_plan_id": "PLAN-002",
  "effective_date": "2026-01-01",
  "occurred_at": "2025-11-15T10:00:00Z"
}
```
