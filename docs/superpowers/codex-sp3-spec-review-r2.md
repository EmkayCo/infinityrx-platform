VERDICT: NO-GO

**ABSORPTION TABLE**

| R1 item | Addressed | R2 section | Note |
|---|---:|---|---|
| BLOCK 1: backend RBAC authority | YES | §4 D5, §5.4, §5.5, §6 Plan A | Sufficient. Backend `require_role()` is now explicit on every endpoint, with BFF/UI as secondary layers. |
| BLOCK 2: incomplete backend endpoint inventory | YES | §5.5 | Sufficient. The missing rule/ML/dashboard/graph polling endpoints are now listed. |
| BLOCK 3: event contracts | PARTIAL | §11.5, §7.2 | Contract fields are present, but `payment.hold_released` has a Plan A vs Plan D phasing contradiction; see NEW BLOCK 1. |
| BLOCK 4: unsafe hold release publishing | PARTIAL | §7.2, §6 Plan A | Transactional outbox is now specified, but hold-release idempotency/status behavior is internally contradictory; see NEW CONCERN 1. |
| BLOCK 5: PHI masking + MFA | YES | §4 D6/D6a, §7.1, §8, §9.2 | Sufficient. PHI fields, masking, no-store, audit, and MFA gate are explicit. |
| BLOCK 6: tenant lookup enumeration | YES | §4 D8, §8 | Sufficient. Entity lookup is tenant-scoped and returns non-enumerating 404. |
| BLOCK 7: RLS + indexes | PARTIAL | §4 D8, §6 Plan A, §9.5 | Intent is present, but the exact RLS expression conflicts with the missing-tenant acceptance test; see NEW BLOCK 2. |
| BLOCK 8: graph job failure semantics | PARTIAL | §5.2 GraphRun, §7.3, §8 | Better, but `cancelled` is modeled without a cancellation path, and retry policy is still not defined. |
| BLOCK 9: coverage + placeholder pages | YES | §6 Plan A, §9.2 | Sufficient. 95% baseline restored, and pages are described as routed/tested empty states. |
| CONCERN 1: accumulator.updated contract | YES | §5.3, §11.5 | Sufficient for design stage; publisher verification is explicitly required before plan execution. |
| CONCERN 2: threshold versioning | YES | §5.2, §6 Plan A, §10 | Sufficient. Version rows, effective dates, snapshots, and hash-chained audit are present. |
| CONCERN 3: NetworkX scale guardrails | YES | §7.3, §9.5 | Sufficient. Node/edge bounds, memory ceiling, chunking, indexes, and oversize behavior are specified. |
| CONCERN 4: PHI-aware caching | YES | §7.1, §8 | Sufficient. Lists exclude PHI; detail/evidence are no-store. |
| CONCERN 5: admin override wording | YES | §4 D5, §5.4 | Sufficient. Admin actions are override actions; audit remains immutable. |
| CONCERN 6: state machine | YES | §5.5.1 | Sufficient, though `closed_*` should be expanded during spec write for test matrix clarity. |
| CONCERN 7: hold-to-investigation auth | YES | §5.5 endpoint #9, §7.2 | Sufficient. Same-tenant, linked investigation, and active/non-closed checks are specified. |
| CONCERN 8: rate limiting | YES | §4 D13, §5.5, §6 Plan A, §8 | Sufficient for R1 concern. Broader middleware gaps remain; see NEW BLOCK 3. |
| CONCERN 9: N+1 tests | YES | §9.1 | Sufficient. Query counter tests are explicitly required. |
| CONCERN 10: path/ORM verification | YES | §11, §12 | Sufficient for pre-write. Spec-write is required to grep-verify paths before invoking plans. |

**NEW BLOCKS**

1. **Plan A / Plan D contradiction around hold release and event documentation.**  
   §5.5 says all 18 backend endpoints, including `POST /holds/{hold_id}/release`, are new in Plan A. §6 Plan A acceptance says transactional outbox is tested in Plan A. But §4 D11 and §11.5 say `payment.hold_released` is written/authored in Plan D. This violates `.claude/rules/event-bus.md` because event contracts must exist when the publishing path exists. Fix by either moving hold release publishing/docs fully into Plan A, or moving the release endpoint out of Plan A.

2. **RLS policy expression contradicts the acceptance gate.**  
   §4 D8 specifies policies using `tenant_id = current_setting('app.tenant_id')::uuid`; §6 Plan A acceptance requires a session without `app.tenant_id` to see zero rows. In PostgreSQL, `current_setting('app.tenant_id')` without `missing_ok=true` errors when unset. The design must specify a null-deny policy such as `current_setting('app.tenant_id', true)` with safe UUID handling, or the acceptance gate is not implementable.

3. **Mandatory production middleware/event-bus reliability rules are not bound.**  
   R2 adds rate limiting, but `.claude/rules/security.md` also requires `SecurityHeadersMiddleware` on every production FastAPI app, and `.claude/rules/event-bus.md` requires DLQ router mounting, DLQ depth monitoring, and `processed_events` cleanup. §5.5/§6/§11 mention none of these for the ReclaimRx app even though SP-3 adds HTTP endpoints and event consumers/outbox. Bind these explicitly or verify they already exist in the module app factory.

**NEW CONCERNS**

1. **Hold-release idempotency row has conflicting behavior.**  
   §7.2 step 7b says non-active hold returns `422 HOLD_NOT_ACTIVE`, then says already released returns `200` with prior state. Those are different behaviors for the same released race. Choose one deterministic replay rule and test it.

2. **`cancelled` graph status is modeled but not operationalized.**  
   §5.2 includes `cancelled`; §7.3 never defines who can cancel, endpoint shape, lock release, cleanup, event payload, or audit. Either remove `cancelled` from SP-3 or specify the cancellation path.

3. **`accumulator.updated` payload duplicates tenant ID in envelope and payload.**  
   §11.5 includes envelope-level `tenant_id` and payload `tenant_id`. That is not automatically wrong, but the consumer must reject mismatches explicitly per tenant-isolation rules.

4. **Audit hash-chain requirements are incomplete.**  
   R2 requires hash-chained audit writes, but `.claude/rules/hipaa-2026.md` also requires daily integrity verification and no empty hash writes. §9 tests hash-chain logic, but no daily verification job or acceptance gate is specified.

**NEW ADVISORIES**

1. Plan A is still very large: graph job, accumulator consumer, migrations/RLS, outbox infrastructure, 18 endpoints, threshold versioning, PHI/security coverage, and empty-state pages. This is no longer a R1 blocker because the scope is explicit, but plan-writing should split deliverables carefully.

2. Fraud ring payload cap is only partly locked: §5.5 endpoint #13 says max 500 nodes/2000 edges but also says “final cap in Plan E.” Keep the cap binding in the spec, then let Plan E tune rendering, not payload safety.

3. §10 keeps graph scheduler as an open question while §7.3 recommends APScheduler. That is acceptable for plan-time, but the final spec should require path verification before choosing in-process scheduling.

END OF REVIEW