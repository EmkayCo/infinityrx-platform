VERDICT: NO-GO

**ABSORPTION TABLE**

| Item | Addressed in R3 | R3 section | Sufficiency |
|---|---:|---|---|
| R2 NEW BLOCK 1: Plan A/Plan D hold-release/event-doc contradiction | PARTIAL | §4 D11, §6 Plan A, §11.5 | Mostly fixed: release endpoint, outbox publish, and docs are Plan A. But §3 still says `payment.hold_released` is “Plan D”, so the contradiction remains in one binding non-goal line. |
| R2 NEW BLOCK 2: RLS unset-tenant policy | YES | §4 D8, §6 Plan A acceptance | Sufficient. Uses `current_setting('app.tenant_id', true)` + null-deny acceptance test. |
| R2 NEW BLOCK 3: production app factory bindings | YES | §4 D14, §6 Plan A acceptance | Sufficient. Binds `SecurityHeadersMiddleware`, `RateLimitMiddleware`, DLQ router, `processed_events` cleanup, and audit verification through `create_app()` tests. |
| R2 NEW CONCERN 1: hold release idempotency | YES | §7.2, §8 | Sufficient. Released replay/conflict/non-active cases are deterministic and tested. |
| R2 NEW CONCERN 2: cancelled graph status | YES | §3, §5.2, §7.3 | Sufficient. `cancelled` removed from `GraphRun`; no cancel endpoint in SP-3. |
| R2 NEW CONCERN 3: duplicate tenant in accumulator event | YES | §5.3, §11.5 | Sufficient. Consumer rejects envelope/payload mismatch with no state change + audit/DLQ. |
| R2 NEW CONCERN 4: audit hash-chain daily verification | YES | §4 D14, §6 Plan A acceptance | Sufficient. Daily verification and empty-hash rejection are explicit. |
| R1 BLOCK 3: event contracts | PARTIAL | §7.2, §11.5 | Fields are sufficient, but stale §3 “Plan D” phasing prevents full closure. |
| R1 BLOCK 4: hold release transaction/outbox | YES | §7.2, §9.1 | Sufficient. Atomic DB/audit/outbox write and publish-failure tests are specified. |
| R1 BLOCK 7: RLS + indexes | YES | §4 D8, §6, §9.5 | Sufficient. Tenant mixin, RLS, unset-tenant test, Redis prefixing, endpoint isolation, and indexes are bound. |
| R1 BLOCK 8: graph failure semantics | PARTIAL | §5.2, §7.3, §8 | Failure states are present, but the advisory-lock design is internally incorrect; see NEW BLOCK 1. |

**NEW BLOCKS**

1. **Graph advisory-lock semantics are wrong enough to break the concurrency guarantee.**  
   §7.3 says `pg_try_advisory_lock(hash('graph_run', tenant_id))`, then says the advisory lock auto-releases on transaction end, and later says `graph_analysis_service.run()` calls `pg_advisory_unlock`. PostgreSQL session advisory locks do not auto-release on transaction end, and a spawned APScheduler job will not own the request session lock. Fix by using one coherent pattern: durable DB `running` row + transaction-scoped `pg_try_advisory_xact_lock` for run creation, or keep the whole job in the same DB session that owns a session lock and explicitly releases it. Add tests for concurrent trigger, worker crash, stale timeout, and retrigger after stale failure.

2. **SP-0 contract-layer obligations are under-specified.**  
   SP-0/SP-1/SP-2 require typed clients in `packages/contract`, zod request/response schemas, cache policy, RealImpl/MockImpl, and BFF handlers consuming the contract layer. R3 mentions `packages/contract` only as reuse (§5.1) and defines raw BFF proxies (§5.5), but Plan A-E never assigns ReclaimRx contract client/schema/mock/cache-policy work. This risks bypassing the integration spine. Add explicit Plan A or B scope for `ReclaimRxClient`, schemas for all 18 endpoints, mock impls, cache/invalidation tags, and contract tests.

3. **R3 invents JWT claims that conflict with SP-0’s canonical auth contract.**  
   §4 D6a, §5.1, and §5.4 require `mfa_verified` and `phi_access_level` JWT claims. SP-0 SD-1 explicitly says `mfa_verified` is not in v1 and token existence implies post-MFA unless route-level fresh MFA is added. If SP-3 needs fresh MFA/ePHI access levels, the design must either scope an auth-contract extension or use existing core-platform/session/audit primitives without claiming those fields already exist in `packages/auth`.

**NEW CONCERNS**

1. **Stale R2 metadata remains in binding control text.**  
   §11.5 says this draft is R2, R2 review is pending, §12 says “Codex R2 spec consult,” and the footer says R2. This is not implementation-structural, but it is plan-writing hostile and should be fixed before formal spec.

2. **Event phasing still has one stale contradiction.**  
   §3 says `payment.hold_released` is Plan D; §4 D11, §6, and §11.5 correctly say Plan A. This should be a quick fix, but it blocks full absorption of R2 NEW BLOCK 1/R1 BLOCK 3.

3. **DLQ monitoring is only partially absorbed.**  
   §4 D14 binds DLQ router and cleanup, but `.claude/rules/event-bus.md` also requires DLQ depth monitoring/alerting. Add it to D14 or Plan A acceptance.

4. **Graph run completion event lacks `completed_at` nullability for failed runs.**  
   §11.5 declares `completed_at: ISO8601`, but payload `status` includes `failed`. Either require `completed_at` on all terminal states or make it nullable and include `failed_at`.

**END OF REVIEW**