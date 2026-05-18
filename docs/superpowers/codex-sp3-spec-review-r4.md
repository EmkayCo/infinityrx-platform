VERDICT: GO-WITH-CHANGES

**ABSORPTION TABLE**

| Item | R4 Section | Assessment |
|---|---|---|
| R3 NEW BLOCK 1: graph advisory-lock semantics | §7.3, §5.2, §8 | PARTIAL. §7.3 is now technically sound: `pg_try_advisory_xact_lock`, transaction-scoped run creation, durable `graph_runs.status='running'` as authority, stale timeout, worker crash recovery, and no worker-held lock. However §5.3 and Plan A acceptance still say plain `pg_try_advisory_lock`, which reintroduces the stale ambiguity. Fix those two mentions to match §7.3. |
| R3 NEW BLOCK 2: SP-0 contract-layer obligations | §5.1, §6 Plan A | YES. R4 explicitly scopes `ReclaimRxClient`, zod schemas, RealImpl/MockImpl, cache policy, and contract tests in Plan A. Sufficient. |
| R3 NEW BLOCK 3: invented JWT claims | §4 D6/D6a, §5.1, §5.3/5.4, §8 | YES. R4 removes `mfa_verified` / `phi_access_level` JWT claims and uses core-platform session/user policy lookup. It also requires plan-time verification or a scoped core-platform extension. Sufficient. |
| R3 NEW CONCERN 1: stale R2 metadata | §0 status/header, §11 wave ledger, §12, footer | YES. Metadata now says R4, R4 consult pending, and R4 review pending. Sufficient. |
| R3 NEW CONCERN 2: stale event phasing contradiction | §3, §4 D11, §6 Plan A/D, §11.5 | YES. `payment.hold_released` endpoint, outbox publish, and event docs are consistently Plan A; UI/BFF is Plan D. Sufficient. |
| R3 NEW CONCERN 3: DLQ monitoring | §4 D14, §6 Plan A acceptance | YES. DLQ depth monitoring/alerting is now explicitly mounted and tested through `create_app()`. Sufficient. |
| R3 NEW CONCERN 4: graph completion event failed-run nullability | §11.5 | YES. `completed_at` is nullable and `failed_at` is included. Sufficient. |
| R3 PARTIAL: R1 BLOCK 3 event contracts | §3, §4 D11, §7.2, §11.5 | YES. Event phasing is now consistent, envelope-level `tenant_id` is present, idempotency/ordering keys are defined, and Plan A owns docs. Sufficient. |
| R3 PARTIAL: R1 BLOCK 8 graph failure semantics | §5.2, §5.3, §6 Plan A acceptance, §7.3, §8 | PARTIAL. Failure states, stale timeout, failure cleanup, and worker crash recovery are now present. The remaining issue is stale `pg_try_advisory_lock` wording in §5.3 and Plan A acceptance, conflicting with corrected §7.3. This is not a design-blocker if corrected before formal spec write. |

**NEW BLOCKS**

None.

**NEW CONCERNS**

1. **Stale graph-lock wording remains in two binding places.**  
   §7.3 correctly uses `pg_try_advisory_xact_lock` and durable `running` rows. But §5.3 still says `pg_try_advisory_lock(hash('graph_run', tenant_id))`, and §6 Plan A acceptance says “Per-tenant `pg_try_advisory_lock`.” Replace both with transaction-scoped `pg_try_advisory_xact_lock` for run creation plus durable running-row authority.

2. **Admin emergency hold release conflicts with required reason semantics.**  
   §5.4 says admins can perform “emergency hold release without reason,” but Goals §2, D5, endpoint #9, §7.2, and §8 all require a release reason. Keep the audit invariant: either remove “without reason” or define an explicit emergency reason field/code.

3. **BFF phasing is slightly inconsistent.**  
   §5.5 says BFF routes for all 18 endpoints are “Plan B+,” while §6 assigns BFF slices across Plans B/C/D/E by surface. Not structural, but plan writers need one source of truth. Prefer the §6 sliced ownership.

**Re-evaluation**

R4 has converged. The prior structural blocks are resolved in substance, and the remaining issues are spec-write-time cleanup items, not reasons to stop plan-writing. The only must-fix before formal spec publication is removing the stale lock wording so Plan A does not implement the wrong PostgreSQL primitive.

END OF REVIEW