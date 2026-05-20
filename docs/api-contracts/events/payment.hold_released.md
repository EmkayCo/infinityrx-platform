# Event Contract: `payment.hold_released`

**Schema version:** 1.0
**Status:** Active

---

## Description

A payment hold has been released by an investigator or admin, allowing the
associated payment batch to proceed to submission. Published via transactional
outbox by the reclaimrx backend upon successful hold release.

---

## Envelope Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_type` | `string` | yes | `"payment.hold_released"` |
| `schema_version` | `string` | yes | `"1.0"` |
| `tenant_id` | `UUID` | yes | Tenant context — envelope-level |
| `ordering_key` | `string` | yes | `hold_id` — ensures per-hold ordering |
| `idempotency_key` | `string` | yes | `"hold:release:{hold_id}"` |

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `hold_id` | `UUID` | yes | The released hold |
| `amount` | `string` | yes | Decimal amount serialized as `str()` — never float |
| `released_by` | `string` | yes | JWT sub of the releasing user |
| `reason` | `string` | yes | Release reason — always present |
| `investigation_id` | `UUID` | yes | Investigation that placed the hold |
| `released_at` | `string (ISO-8601)` | yes | Release timestamp |
| `emergency_reason_code` | `string \| null` | no | Admin emergency override code only (R5) |
| `emergency_note` | `string \| null` | no | Admin emergency override note only (R5) |

---

## Forward Compatibility

Consumers MUST ignore unknown fields. New fields added in 1.x are non-breaking.
Never reject a message solely because an unrecognized field is present.

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | `DELETE /holds/{id}/release` — transactional outbox publish on commit |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `payment-processing` | `handle_payment_hold_released` | Allow NACHA batch submission for the released hold |

---

## Ordering Key Convention

**`ordering_key`:** `hold_id`

Per-hold ordering guarantees that a second release attempt (idempotency replay)
cannot interleave with the initial release write.

## Idempotency Key Convention

**`idempotency_key`:** `hold:release:{hold_id}`

Consumer wraps handler with `idempotent_handler` decorator. Duplicate deliveries
return 200 OK without re-processing state changes.

---

## Example Payload

```json
{
  "event_type": "payment.hold_released",
  "schema_version": "1.0",
  "tenant_id": "11111111-0000-0000-0000-000000000001",
  "ordering_key": "22222222-0000-0000-0000-000000000010",
  "idempotency_key": "hold:release:22222222-0000-0000-0000-000000000010",
  "hold_id": "22222222-0000-0000-0000-000000000010",
  "amount": "14500.00",
  "released_by": "investigator@plan.com",
  "reason": "Investigation closed — no fraud confirmed after secondary review",
  "investigation_id": "33333333-0000-0000-0000-000000000001",
  "released_at": "2026-05-18T14:30:00Z",
  "emergency_reason_code": null,
  "emergency_note": null
}
```

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-05-18 | Initial contract — SP-3 Plan A (R2 NEW BLOCK 1) |
