VERDICT: NO-GO

**BLOCKS**

1. Severity: Critical  
   Reference: `waves/B10/SP-3-design-draft.md` §5.4, §5.5, §6 Plan A  
   Specific fix: Enforce RBAC at the backend API layer, not only BFF + React. Plan A ships direct backend endpoints before UI/BFF, so every mutation endpoint must validate JWT tenant + role server-side. Keep React `RoleGate` as UX only, BFF as perimeter, backend as authority.

2. Severity: Critical  
   Reference: §5.5, §6 Plans C/D, §7.3  
   Specific fix: Complete the backend contract inventory before plan-writing. The design promises Plan C `rule-firings` and `ml-scores` BFFs, Plan D `dashboard-summary`, and §7.3 polling `GET /api/v1/reclaimrx/graph-runs/{run_id}`, but §5.5 does not define those backend endpoints. Add minimum endpoint rows or explicitly bind to existing verified routes.

3. Severity: Critical  
   Reference: §7.2, §3, §11; `.claude/rules/event-bus.md`, `.claude/rules/tenant-isolation.md`  
   Specific fix: Fully specify both new event contracts. `payment.hold_released` and `fwa.graph_run_completed` must include `tenant_id` in the `EventEnvelope`, `ordering_key`, `idempotency_key`, `schema_version`, forward-compatible payload handling, and docs paths under `docs/api-contracts/events/{event_type}.md`. The hold event example currently omits envelope-level `tenant_id`.

4. Severity: Critical  
   Reference: §7.2 hold release path  
   Specific fix: Add idempotency and transaction semantics for hold release. Required minimum: reject/replay duplicate release using a business idempotency key, make repeated release of an already released hold deterministic, publish through an outbox or after-commit mechanism, and test “DB commit succeeds but publish fails” / “publish succeeds then retry” behavior. Current “publish then commit” is unsafe.

5. Severity: Critical  
   Reference: §5.2, §8; `.claude/rules/phi-compliance.md`, `.claude/rules/hipaa-2026.md`  
   Specific fix: Add PHI access-level masking and MFA/ePHI prerequisites to the design. The draft mentions `no-store` and audit but omits response masking by PHI access level and HIPAA 2026 MFA enforcement for ePHI access. Also clarify which fields are PHI: `member_id` alone is not an `EncryptedString` fit if it is a FK UUID, but member name/DOB/address/phone/email rendered in evidence must be encrypted/masked/audited.

6. Severity: High  
   Reference: §8 cross-tenant id lookup; `.claude/rules/tenant-isolation.md`  
   Specific fix: Replace the “Cross-tenant id lookup = 403, NEVER 404” rule with a safe tenant-scoped lookup rule. Do not perform an unscoped existence check just to detect tenant mismatch. Validate request tenant/header mismatch as 403, but entity lookup should query by `{tenant_id, id}` and return a non-enumerating not-found response unless the project has a binding contrary API convention.

7. Severity: High  
   Reference: §5.1, §6 Plan A; `.claude/rules/tenant-isolation.md`, `.claude/rules/performance.md`  
   Specific fix: Add migration requirements for RLS and indexes. Every new tenant-owned table needs `TenantScopedMixin`, PostgreSQL RLS policy, `(tenant_id, foreign_key)` indexes, and `(tenant_id, status)` where status is queried. Plan A acceptance only says Alembic applies/rolls back; that will trip tenant/performance gates.

8. Severity: High  
   Reference: §5.3, §7.3 graph batch design  
   Specific fix: Specify graph job failure/retry/cancellation states and persistence. `GraphRun` needs `status`, `failed_at`, `error_code`, `correlation_id`, retry policy, stale-running timeout, per-tenant lock, and partial-write cleanup behavior. Current flow only handles happy-path and 409 in-flight.

9. Severity: High  
   Reference: §6 Plan A, §9.2; `.claude/rules/testing.md`  
   Specific fix: Align coverage gates with binding rules. Testing rule says 95% on other active code, not 99%. If SP-3 intentionally raises to 99%, say it is stricter than baseline. Also Plan A’s “placeholder portal pages” risks violating the dead-code/stub scanner; define them as real routed pages with tested copy or remove from Plan A.

**CONCERNS**

1. Severity: High  
   Reference: §5.3 accumulator detector wiring  
   Specific fix: Define the `accumulator.updated` source contract: event type, payload fields, tenant field, ordering key, idempotency key, expected consumer name, and which existing module publishes it. Without that, Plan A can invent the consumer boundary.

2. Severity: High  
   Reference: §5.2 `ThresholdConfig`, §7.1, §7.2  
   Specific fix: Add threshold versioning beyond a JSON snapshot. Minimum viable fix: `threshold_config.version`, effective timestamps, per-field audit with hash-chain audit writes, and snapshot copied into investigations/holds at decision time.

3. Severity: High  
   Reference: §5.3 graph job, §9.5 performance  
   Specific fix: Add measured scale assumptions and guardrails for NetworkX: max nodes/edges per tenant run, memory ceiling, query pagination/chunking, indexes needed for 90-day claim/entity extraction, and behavior when the tenant exceeds the bound.

4. Severity: Medium  
   Reference: §7.1 caching vs §8 PHI posture  
   Specific fix: Make cache rules PHI-aware. Investigation list may include PHI-derived fields depending on columns shown; detail/evidence must be `no-store`. If list rows include member names or IDs, remove the 30s cache or cache only non-PHI summaries.

5. Severity: Medium  
   Reference: §4 D5, §5.4  
   Specific fix: Clarify role hierarchy and admin powers. “admin override audits” is dangerous wording because audit entries must never be modified/deleted. Change to “admin can perform audited override actions; audit logs remain append-only.”

6. Severity: Medium  
   Reference: §5.5 transition status  
   Specific fix: Define the state machine table. “Any non-admin transition” is ambiguous and will create inconsistent behavior. Add allowed transitions, terminal states, required fields per transition, and whether hold release is allowed after each terminal state.

7. Severity: Medium  
   Reference: §5.5 release hold  
   Specific fix: Require a hold-to-investigation authorization check. A user should not release an arbitrary `hold_id` outside the investigation/tenant context. Body likely needs `investigation_id` or backend must verify active linked investigation.

8. Severity: Medium  
   Reference: §8 error handling  
   Specific fix: Add rate limiting and abuse controls for graph-run trigger, threshold update, search/list endpoints, and hold release. Security rules require rate-limit middleware on production apps; high-cost graph runs need an explicit per-tenant throttle.

9. Severity: Medium  
   Reference: §9.1 testing  
   Specific fix: Add N+1 query counter tests for investigation detail/evidence fan-out and graph ring detail. Performance rules require this, and these are the most likely endpoints to regress.

10. Severity: Medium  
   Reference: §11 existing code references  
   Specific fix: Verify existing paths and ORM names during spec write. The draft asserts `models/investigation.py`, `models/payment_hold.py`, `wire_consumers()`, and `shared/scheduling/`; plan-writer must not proceed until these are grep-verified like SP-2 did.

**ADVISORIES**

1. Severity: Medium  
   Reference: §6 plan carve  
   Specific fix: Plan A is oversized: graph job, accumulator consumer, five tables, migrations, 13+ endpoints, threshold config, PHI/security/financial coverage. Keep five plans, but move nonessential read endpoints for rule/ML/dashboard into the plans that build their UI, or explicitly expand Plan A acceptance and timeline.

2. Severity: Low  
   Reference: §3 non-goals, §4 D12  
   Specific fix: Reconcile “No new event bus events beyond two” with D12 “every backend gap has UI.” If status transitions, investigation opened, recovery posted, or threshold changed need downstream reactions, either state they remain DB/audit-only or add event contracts now.

3. Severity: Low  
   Reference: §9.4 fixtures  
   Specific fix: Avoid real public drug/code data in synthetic FWA E2E unless already allowed by fixture policy. The draft says no real PHI, but for deterministic tests the safer SP-2 pattern is invented identifiers plus public-format validation.

4. Severity: Low  
   Reference: §7.3 graph visualization  
   Specific fix: Specify graph payload size limits and UI truncation behavior. Fraud rings can be large; the detail endpoint should cap nodes/edges or provide focused neighborhoods.

5. Severity: Low  
   Reference: §10 open questions  
   Specific fix: Promote graph scheduler choice from open question to a plan-time verification item with an existing-path check. The draft recommends APScheduler in `shared/scheduling/` but does not prove that path exists.

END OF REVIEW