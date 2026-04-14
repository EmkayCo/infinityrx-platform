# Event: member.benefit_phase_changed

**Source module:** member-management  
**Schema version:** 1.0  
**ordering_key:** member_id  
**idempotency_key:** `member_phase:{member_id}:{new_phase}:{coverage_period_id}`

## Purpose

Emitted when a Part D member transitions between benefit phases.
Consumed by adjudication engine to apply correct cost-sharing rules.

## Payload

```json
{
  "member_id": "uuid",
  "coverage_period_id": "uuid",
  "previous_phase": "deductible",
  "new_phase": "initial_coverage",
  "troop": "590.00",
  "effective_date": "2026-03-15"
}
```

## Notes

- `phase` values: `deductible`, `initial_coverage`, `coverage_gap`, `catastrophic`
- No PHI in payload.
