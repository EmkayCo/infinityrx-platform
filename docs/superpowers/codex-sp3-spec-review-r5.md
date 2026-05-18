VERDICT: GO-WITH-CHANGES

**ABSORPTION TABLE**

| R4 NEW CONCERN | R5 Status | Evidence |
|---|---:|---|
| 1. Stale `pg_try_advisory_lock` wording in §5.3 + §6 Plan A acceptance | YES | §5.3 now uses `pg_try_advisory_xact_lock(...)` and explicitly says transaction-scoped. Plan A acceptance and §7.3 both clarify the durable `graph_runs.status='running'` row is the cross-process authority and APScheduler does not hold a lock. |
| 2. Admin emergency hold release without reason contradicted required-reason invariant | PARTIAL | §5.4 now says emergency override is not reason-free and requires structured reason codes. However, the concrete endpoint/data-flow/event contract still only defines `{reason, investigation_id}` and `payload.reason`, with no `emergency_reason_code` field or mapping rule. |
| 3. BFF phasing inconsistency between §5.5 and §6 | YES | §5.5 now says BFF routes are sliced per §6, names §6 as the binding ownership map, and §6 assigns BFF work to Plans B/C/D/E by surface. Plan A owns backend + contract layer, not functional BFF routes. |

**NEW BLOCKS**

None.

**NEW CONCERNS**

1. Admin emergency release contract is still underspecified.

R5 fixed the dangerous “reason-free admin release” concept, but it introduced a smaller contract mismatch: §5.4 requires a mandatory `emergency_reason_code`, while endpoint #9, §7.2, idempotency comparison, audit update, and `payment.hold_released` payload only carry `reason`.

Before plan-writing, make one of these explicit:

- Add `emergency_reason_code?: enum` plus `emergency_note?: string` to the release request/audit/outbox contract, required only for admin emergency override.
- Or state that `reason` is the structured emergency enum value for admin emergency releases, with `OTHER_WITH_NOTE` requiring note text, and remove the separate `emergency_reason_code` field name.

This is spec-write-time cleanup, not an architecture blocker.

END OF REVIEW