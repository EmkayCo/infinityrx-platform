# Event: member.accumulator_updated

**Source module:** member-management  
**Schema version:** 1.0  
**ordering_key:** member_id  
**idempotency_key:** `member_accumulator:{member_id}:{accumulator_type}:{claim_id}`

## Purpose

Emitted after every accumulator balance change (claim applied, claim reversed, manual adjustment).
Consumed by the adjudication engine to update real-time pricing.

## Payload

```json
{
  "member_id": "uuid",
  "coverage_period_id": "uuid",
  "accumulator_type": "individual_deductible",
  "transaction_type": "claim_applied",
  "amount": "25.00",
  "new_accumulated": "275.00",
  "limit_amount": "500.00",
  "remaining_amount": "225.00",
  "claim_id": "uuid",
  "benefit_phase": "initial_coverage"
}
```

## Notes

- All amounts serialized as `str` (Decimal) — never float.
- `accumulator_type` values: `individual_deductible`, `family_deductible`, `individual_oop_max`, `family_oop_max`, `individual_moop`, `family_moop`, `copay_cap`, `benefit_max`, `specialty_accumulator`, `troop`
- `transaction_type` values: `claim_applied`, `claim_reversed`, `manual_adjustment`, `benefit_year_reset`, `copay_assistance_applied`, `copay_assistance_excluded`
