# Event: member.retroactive_enrollment

**Source module:** member-management  
**Schema version:** 1.0  
**ordering_key:** member_id  
**idempotency_key:** `member_retro:{member_id}:{effective_date}`

## Purpose

Emitted when a member is enrolled with an effective_date in the past (retroactive enrollment).
Consumed by adjudication engine to re-adjudicate previously rejected claims.

## Payload

```json
{
  "member_id": "uuid",
  "coverage_period_id": "uuid",
  "effective_date": "2025-12-01",
  "retroactive_days": 45,
  "enrollment_file_id": "uuid",
  "source": "edi_834"
}
```

## Notes

- Maximum retroactive period configurable per tenant (default: 90 days).
- Adjudication engine queries billing for rejected claims in the retroactive window.
- No PHI in payload.
