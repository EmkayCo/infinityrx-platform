# Event Contract: `member.cob_changed`

**Schema version:** 1.0
**Status:** Active

## Description

A member's coordination of benefits (COB) information has changed. This affects
claim adjudication priority and reimbursement amounts.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `member_id` | `UUID` | yes | Member with COB change |
| `is_primary` | `bool` | yes | Whether this plan is now primary |
| `other_coverage_id` | `str or null` | no | Other insurer identifier if known |
| `effective_date` | `str (ISO-8601 date)` | yes | COB change effective date |
| `occurred_at` | `str (ISO-8601)` | yes | Event timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `member-management` | COB update received via 834 or manual entry |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(adjudication-engine)* | — | Recalculate claim adjudication for member |

## Ordering Key Convention

**`ordering_key`:** `member_id`

## Idempotency Key Convention

**`idempotency_key`:** `member.cob_changed:{member_id}:{effective_date}`

## Example Payload

```json
{
  "event_type": "member.cob_changed",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "member_id": "uuid",
  "is_primary": false,
  "other_coverage_id": "BCBS-12345",
  "effective_date": "2026-01-01",
  "occurred_at": "2026-04-14T10:00:00Z"
}
```
