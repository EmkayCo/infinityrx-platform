# SP-3 — ReclaimRx Operator Portal + Backend Closure

**Status:** Spec — codex-converged (R1 NO-GO → R2 NO-GO → R3 NO-GO → R4 GO-WITH-CHANGES → R5 GO-WITH-CHANGES; final cleanup wired inline; zero NEW BLOCKS in R5). Ready for plan-writing after user review gate.
**Date:** 2026-05-18
**Owner:** Mike
**Sub-project of:** Operator Portal & Platform Frontend milestone
**Builds on:** SP-0 (`2026-05-14-sp0-integration-foundation-design.md`), SP-2 (`2026-05-16-sp2-directories-portal-design.md`)
**Codex review trail (5 rounds):**
- R1: `docs/superpowers/codex-sp3-spec-review-r1.md` — NO-GO (9 BLOCKS, 10 CONCERNS, 5 ADVISORIES)
- R2: `docs/superpowers/codex-sp3-spec-review-r2.md` — NO-GO (absorbed 14/18 R1 items; 3 NEW BLOCKS, 4 NEW CONCERNS, 3 NEW ADVISORIES)
- R3: `docs/superpowers/codex-sp3-spec-review-r3.md` — NO-GO (absorbed 12/13 R2 items; 3 NEW BLOCKS, 4 NEW CONCERNS)
- R4: `docs/superpowers/codex-sp3-spec-review-r4.md` — GO-WITH-CHANGES (absorbed 7/7 R3 NEW + R3 PARTIALs; 0 NEW BLOCKS, 3 NEW CONCERNS)
- R5: `docs/superpowers/codex-sp3-spec-review-r5.md` — GO-WITH-CHANGES (absorbed 2/3 R4 + 1 PARTIAL contract-wiring resolved inline; 0 NEW BLOCKS)
Total deferred: 5 R1 ADVISORIES + 3 R2 ADVISORIES (cosmetic / plan-time)
**Decomposition note:** SP-2 spec §11 originally had SP-3=Billing/Analytics, SP-4=ReclaimRx. This spec reorders ReclaimRx forward to SP-3 (user decision 2026-05-18); Billing/Analytics becomes SP-4; Claims/Adjudication SP-5; downstream order unchanged.

---

## 1. Problem statement

The InfinityRx ReclaimRx module runs a live FWA (Fraud, Waste, Abuse) detection backend: 8 event consumers fire a deterministic rule engine + XGBoost ML scoring on every claim, apply payment holds when scores cross thresholds, and auto-open investigations. **Zero of this is visible to a human operator.** Today:

- **No triage surface.** Investigations open automatically and accumulate. There is no UI to list them, filter by severity/recency/program, or transition status. Operators discover them by querying the database directly.
- **Rule firings are opaque.** A claim flagged by a rule produces a row, but operators cannot see "which rules fired on which claims this week, with what score and which evidence."
- **ML scores are a black box.** XGBoost produces per-claim scores but the operator cannot inspect feature importance, score distribution, or per-tenant threshold configuration.
- **Payment holds have no release flow.** Holds apply automatically; operators have no audited UI to release a hold other than direct DB writes.
- **Recovery is untracked.** No surface ties recovered dollars to the investigations that produced them.
- **Graph analysis is a documented gap.** CLAUDE.md: "Graph analysis batch job ... still gap."
- **Accumulator detection is a documented gap.** CLAUDE.md: "accumulator detection ... still gap."

SP-3 closes both backend gaps AND delivers the operator surface that turns the pipeline into a usable tool.

---

## 2. Goals

1. **Backend gap closure.** Land the graph-analysis batch job and the accumulator-detection consumer.
2. **Investigation triage loop.** Investigator can find any open investigation, see evidence, transition status with full audit.
3. **Rule + ML transparency.** Inspect rule firings + XGBoost feature importance + underlying claim evidence.
4. **Audited hold release.** Investigator (with proper role) can release a hold with required reason; every release audited and triggers downstream PaySync resume event.
5. **Recovery + dashboard.** Total recovered, open investigations, hold $ volume, false-positive rate. Recovery attributable to source investigation.
6. **Graph exploration.** Visualize fraud rings detected by the new batch job — drill from flagged claim into connected entities.
7. **Shippable E2E round trip** on synthetic FWA fixtures (5 fraud archetypes).

---

## 3. Non-goals (explicitly out of SP-3)

- **No ML retraining UI.** Outcome labels persist; no retraining dashboard.
- **No new rule authoring UI.** Threshold tuning IS in scope; rule logic authoring is NOT.
- **No external reporting integrations.** Recovery exports deferred.
- **No fraud-network external data enrichment.**
- **No appeals workflow.**
- **No real-time graph re-computation.** Batch (daily or on-demand). Streaming deferred.
- **No manual graph-run cancellation (R2 NEW CONCERN 2).** Stale-running detection auto-fails abandoned runs after `stale_timeout_at`. Operator cannot manually cancel a run in SP-3. (`cancelled` status removed from `GraphRun.status` enum in R3.)
- **No new event bus events beyond two.** Only `payment.hold_released` (Plan A — endpoint, outbox publish, and event-contract doc per D11) and `fwa.graph_run_completed` (Plan A) are added. All other SP-3 reactions (status transitions, investigation opens by humans, recovery posts, threshold changes) are **DB + append-only audit ONLY** — no event topics. Downstream consumers (ML retraining feed, finance ledger) read via audit-log scan or are deferred entirely. This resolves the D12-vs-event-bus tension flagged in R1 ADVISORY 2.

---

## 4. Locked decisions

| # | Decision | Choice | Source |
|---|---|---|---|
| D1 | Vertical | ReclaimRx operator portal + backend closure | user 2026-05-18 |
| D2 | Build approach | **Approach B — backend-completeness first.** Plan A delivers backend before any UI. | user 2026-05-18 |
| D3 | Plan count | 5 plans (A-E) matching SP-1/SP-2 cadence | user 2026-05-18 |
| D4 | Decomposition order | SP-3 = ReclaimRx. SP-4 = Billing/Analytics. SP-5 = Claims/Adjudication. | user 2026-05-18 |
| D5 | RBAC | **Required, 3-layer dual-gate enforcement (R1 BLOCK 1).** Three roles: `reclaimrx.viewer` (read), `reclaimrx.investigator` (transition, release w/ reason), `reclaimrx.admin` (tune thresholds, audited override actions). Enforcement layers: backend route handler (authority — `require_role()` on every mutation; returns 403 if missing), BFF (perimeter — re-validates), React `<RoleGate>` (UX only — hides/disables actions). **Admin can perform audited override actions; audit entries remain append-only and immutable (R1 CONCERN 5)** — admin cannot edit/delete audit history. | derived; R1 BLOCK 1 + CONCERN 5 |
| D6 | PHI posture | **PHI in scope. PHI access level enforced via core-platform session lookup (R3 NEW BLOCK 3 — not via JWT claim, which SP-0 SD-1 does not include).** Investigations + evidence panels render member PHI. Required (per `phi-compliance.md`): `PHIMixin` + `EncryptedString` on PHI columns; `Cache-Control: no-store` on every PHI-bearing response; `action="phi_access"` audit per detail read with `user_id`/`tenant_id`/`entity_type`/`entity_id`; **response masking by user PHI access level** (`full`/`partial`/`redacted`) resolved via core-platform session/user policy lookup at request time, NOT via JWT claim. **Clarification (R1 BLOCK 5):** `member_id` (UUID FK) is NOT PHI — it does not need EncryptedString. PHI columns are: `member_name`, `dob`, `ssn`, `address`, `phone`, `email` (rendered in evidence panel only when user PHI access level permits). | R1 BLOCK 5 + R3 NEW BLOCK 3 |
| D6a | HIPAA 2026 MFA | **MFA-elevated session required for ePHI access via core-platform session check (R3 NEW BLOCK 3 — not via JWT claim).** Backend detail endpoints call `core-platform/auth/session_lookup(user_id) → session.mfa_elevated_until > now()`; reject 403 `MFA_REQUIRED` if not elevated or expired. Re-elevation flow handled by core-platform existing auth surface (per CLAUDE.md core-platform notes "MFA gate ... mounted"). **Plan A must grep-verify the session lookup path and MFA elevation API exist in `modules/core-platform/`; if not, scope a core-platform extension (smaller than inventing JWT claims).** | R1 BLOCK 5 (HIPAA 2026) + R3 NEW BLOCK 3 |
| D7 | Financial posture | **100% coverage required** on recovery, hold, threshold math. `Decimal` + `ROUND_HALF_UP` for all $ amounts. | `.claude/rules/financial-precision.md` |
| D8 | Tenant isolation | **Per-tenant scoping + PG RLS (R1 BLOCK 7, refined R2 NEW BLOCK 2).** All new tables `TenantScopedMixin` + PG RLS policy enabling SELECT/INSERT/UPDATE/DELETE WHERE `tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid`. The `missing_ok=true` flag returns null when GUC unset (not error); `nullif(..., '')` handles empty-string case; `tenant_id = NULL` evaluates false → zero rows visible. **Acceptance test:** open a session WITHOUT setting `app.tenant_id` → query each tenant-owned table → assert zero rows AND no exception. Cross-tenant isolation test per endpoint. Redis keys prefixed `tenant:{tenant_id}:reclaimrx:`. Lookups always query WHERE `{tenant_id, id}` — never unscoped existence check (R1 BLOCK 6). | `.claude/rules/tenant-isolation.md` + R1 BLOCKS 6, 7 + R2 NEW BLOCK 2 |
| D9 | Deployable shape | Module inside `portal/operator`. Standalone deferred. | continuity with SP-1/SP-2 |
| D10 | SP-2 integration | ReclaimRx Cmd+K palette registers into SP-2 federated search spine. Cross-clickthrough SP-2 → ReclaimRx. | leverages SP-2 |
| D11 | SP-1 integration | Hold release emits `payment.hold_released` event via **transactional outbox (R1 BLOCK 4)**. SP-1's unmerged state does NOT block SP-3 — contract locked here; PaySync consumer is SP-1's work. **Plan A owns the backend release endpoint + outbox publishing + event-contract doc (R2 NEW BLOCK 1 — backend authors the contract co-located with the publish path). Plan D owns the UI + BFF wiring.** Tests mock subscriber. | derived; R1 BLOCK 4 + R2 NEW BLOCK 1 |
| D12 | UI completeness | **No backend capability is operator-accessible only via DB/curl.** Every gap closure (graph runs, accumulator anomalies, threshold tuning, hold release, status transitions, recovery, FP feedback) has a UI control with role-gated visibility per D5. | user 2026-05-18 |
| D13 | Rate limiting | **All SP-3 endpoints rate-limited (R1 CONCERN 8)** via existing `RateLimitMiddleware` from core-platform. Default limits: graph-run trigger 1/hr/tenant, threshold update 10/hr/tenant, search/list 60/min/user, hold release 30/min/tenant. Per-endpoint override in Plan A. | R1 CONCERN 8 + `.claude/rules/security.md` |
| D14 | Production app factory bindings (R2 NEW BLOCK 3) | ReclaimRx FastAPI `create_app()` MUST mount: `SecurityHeadersMiddleware` (security.md), `RateLimitMiddleware` (D13), DLQ router (event-bus.md), `processed_events` cleanup scheduler (event-bus.md: `DELETE WHERE processed_at < NOW() - INTERVAL '7 days'`), **DLQ depth monitoring + alerting (R3 NEW CONCERN 3 — event-bus.md "MUST monitor DLQ depth — alert when > 0 for > 15 minutes"; metric exported to existing core-platform observability)**, audit hash-chain daily integrity verification job at 03:00 UTC (hipaa-2026.md). **Plan A integration test through `create_app()` confirms all 6 mounted per LESSON-006.** Plan-writer must verify existing app factory state and add what's missing. | R2 NEW BLOCK 3 + R2 NEW CONCERN 4 + R3 NEW CONCERN 3 + `.claude/rules/security.md` + `event-bus.md` + `hipaa-2026.md` + LESSON-006 |

---

## 5. Architecture

### 5.1 Layering

```
packages/modules/reclaimrx/              ← NEW: the SP-3 frontend deliverable
  src/
    investigations/                       ← list / detail / status workflow / evidence panels
    rules/                                ← rule firing browser / explainer / threshold tuning admin UI
    ml/                                   ← XGBoost score detail / feature importance / score distribution
    holds/                                ← hold list / release flow with audit
    recovery/                             ← recovery $ tracker / dashboard tiles
    graph/                                ← graph runs page / fraud-ring viz (force-directed)
    bff/                                  ← Next.js handlers per surface, mounted at /api/reclaimrx/
    components/                           ← module primitives
    rbac/                                 ← RoleGate hook + button wrappers (UX-layer enforcement)
    module.config.ts                      ← composition entry
  fixtures/                               ← synthetic non-PHI FWA fixtures (5 archetypes)
  tests/

modules/reclaimrx/                        ← EXISTING — backend extended in Plan A
  src/
    services/
      graph_analysis_service.py           ← NEW (Plan A)
      accumulator_anomaly_detector.py     ← NEW (Plan A) — 4 pattern detectors
    consumers/
      accumulator_consumer.py             ← NEW (Plan A) — subscribes accumulator.updated
    outbox/
      event_outbox.py                     ← NEW (Plan A) — transactional outbox (R1 BLOCK 4)
      outbox_dispatcher.py                ← NEW (Plan A) — background publisher with retry
    models/
      fraud_ring.py                       ← NEW (Plan A)
      graph_run.py                        ← NEW (Plan A) — status enum + failure fields (R1 BLOCK 8)
      accumulator_anomaly.py              ← NEW (Plan A) — member_id is UUID FK (NOT PHI per D6)
      investigation_outcome.py            ← NEW (Plan B)
      threshold_config.py                 ← NEW (Plan A) — versioned + effective dates (R1 CONCERN 2)
      threshold_config_audit.py           ← NEW (Plan A) — per-field hash-chained audit (R1 CONCERN 2)
      outbox_event.py                     ← NEW (Plan A) — outbox row schema
    jobs/
      graph_analysis_job.py               ← NEW (Plan A)
    api/
      router.py                           ← EXTENDED — backend RBAC via require_role() on every endpoint (R1 BLOCK 1)
```

**SP-0 reuse**: `packages/contract` (extended in Plan A with reclaimrx client+schemas+impls+cache-policy per R3 NEW BLOCK 2), `packages/auth` (existing JWT validation — no new claims; MFA + PHI-access via core-platform session lookup per D6/D6a, R3 NEW BLOCK 3), `packages/ui`, `packages/qa-harness`, `packages/shell`.

**SP-2 reuse**: federated search registration + cross-clickthrough.

### 5.2 Domain model

```ts
type InvestigationStatus = 'open' | 'in_progress' | 'pending_review'
  | 'closed_confirmed' | 'closed_false_positive' | 'closed_no_action' | 'escalated';

interface Investigation {
  id: UUID;
  tenant_id: UUID;                       // TenantScopedMixin + RLS
  status: InvestigationStatus;
  severity: 'low' | 'medium' | 'high' | 'critical';
  source: 'rule_firing' | 'ml_score' | 'graph_ring' | 'accumulator_anomaly' | 'manual';
  source_ref_id: UUID;                   // FK; null for manual
  member_id: UUID | null;                // UUID FK — NOT PHI per D6
  opened_at: timestamp;
  opened_by: 'system' | UserSub;
  assigned_to: UserSub | null;
  closed_at: timestamp | null;
  closed_by: UserSub | null;
  outcome_label: 'confirmed' | 'false_positive' | 'no_action' | null;
  recovered_amount: Decimal | null;      // 100% coverage gate
  hold_amount: Decimal | null;           // 100% coverage gate
  threshold_config_version: int;         // FK to ThresholdConfig version at open time (R1 CONCERN 2)
  threshold_snapshot: JSONB;             // immutable copy of relevant threshold values at open (defense-in-depth)
  evidence: EvidenceLink[];
  notes: AuditedNote[];                  // append-only
  status_transitions: AuditedTransition[]; // append-only
}

interface FraudRing {
  id: UUID; tenant_id: UUID; graph_run_id: UUID;
  detected_at: timestamp;
  density_score: Decimal;
  node_count: int; edge_count: int;
  entity_refs: EntityRef[];
  spawned_investigation_id: UUID | null;
}

interface AccumulatorAnomaly {
  id: UUID; tenant_id: UUID;
  member_id: UUID;                       // UUID FK — NOT PHI (D6)
  pattern_type: 'sudden_spike' | 'multi_payer_convergence' | 'reset_evasion' | 'threshold_oscillation';
  detected_at: timestamp;
  evidence_window_start: timestamp; evidence_window_end: timestamp;
  triggering_event_ids: UUID[];          // accumulator.updated event_ids
  spawned_investigation_id: UUID | null;
}

interface GraphRun {                     // R1 BLOCK 8 — full failure semantics; cancelled removed per R2 NEW CONCERN 2
  id: UUID; tenant_id: UUID;
  status: 'running' | 'completed' | 'completed_partial' | 'failed';
  trigger: 'cron' | 'on_demand';
  started_at: timestamp;
  completed_at: timestamp | null;
  failed_at: timestamp | null;
  error_code: string | null;
  error_message: string | null;          // sanitized — no PHI
  correlation_id: string;
  stale_timeout_at: timestamp;           // auto-fail after N hours of running with no progress
  rings_detected: int;
  investigations_opened: int;
  records_scanned: int;
  lookback_window_days: int;             // default 90
}

interface ThresholdConfig {              // R1 CONCERN 2 — versioned
  tenant_id: UUID;
  version: int;                          // monotonic per tenant
  effective_at: timestamp;
  superseded_at: timestamp | null;       // null = current
  rule_thresholds: Map<RuleId, Decimal>;
  ml_score_thresholds: { open: Decimal; auto_hold: Decimal; escalate: Decimal };
  graph_density_threshold: Decimal;
  accumulator_anomaly_sensitivity: Decimal;
  updated_by: UserSub;
}

interface ThresholdConfigAudit {         // R1 CONCERN 2 — per-field audit, hash-chained
  id: UUID; tenant_id: UUID;
  threshold_config_id: UUID;
  field: string;                         // dot-path e.g. 'ml_score_thresholds.open'
  old_value: string;                     // serialized
  new_value: string;
  changed_at: timestamp;
  changed_by: UserSub;
  reason: string | null;
  entry_hash: string;                    // chains to prev entry per HIPAA 2026 + .claude/rules/hipaa-2026.md
  prev_entry_hash: string | null;
}

interface OutboxEvent {                  // R1 BLOCK 4 — transactional outbox
  id: UUID; tenant_id: UUID;
  event_type: string;                    // dot-notation
  envelope_json: JSONB;                  // full EventEnvelope
  status: 'pending' | 'published' | 'failed';
  created_at: timestamp;
  published_at: timestamp | null;
  attempt_count: int;
  last_error: string | null;             // sanitized — no PHI
  idempotency_key: string;               // unique constraint
}
```

### 5.3 Detection pipeline — existing + SP-3 additions

```
EXISTING (unchanged except wire-in points)
  Claim ingested → 8 consumers → rule_engine + ml_score → optional PaymentHold + auto-Investigation

NEW IN SP-3 PLAN A

  graph_analysis_job (cron 02:00 UTC + on-demand POST trigger)
    per-tenant fan-out
    pg_try_advisory_xact_lock(hash('graph_run', tenant_id))  ← transaction-scoped lock per §7.3 (R4 NEW CONCERN 1)
    durable graph_runs.status='running' row is the cross-process authority (R3 NEW BLOCK 1)
    build entity graph (NetworkX) from last 90d claims + entities — scoped by tenant_id
    connected-component + density scoring
    FraudRing rows + auto-Investigation (source='graph_ring') if density > threshold
    GraphRun row updated to status='completed' OR 'failed' OR 'completed_partial'
    on failure: cleanup partial fraud_rings rows (atomic per-run cleanup)
    publish fwa.graph_run_completed via outbox (R1 BLOCK 3)

  accumulator_consumer
    subscribes: accumulator.updated event (publisher: member-management module — R1 CONCERN 1)
    EventEnvelope contract for accumulator.updated (R1 CONCERN 1):
      type = 'accumulator.updated'
      tenant_id = UUID                  ← envelope-level
      ordering_key = member_id
      idempotency_key = f'accumulator:{member_id}:{accumulator_period}:{updated_at_epoch}'
      schema_version = '1.0'
      payload = {member_id, tenant_id, accumulator_type, period, amounts: {oop, deductible, ...}, source_payer_id?}
    **Envelope/payload tenant_id consistency check (R2 NEW CONCERN 3):**
      consumer MUST verify envelope.tenant_id == payload.tenant_id BEFORE processing
      mismatch → 200 OK with audit warning "ACCUMULATOR_TENANT_MISMATCH" + correlation_id + no state change + DLQ entry
      (200 returned to prevent retry storm; investigated via audit + DLQ)
    wrap with idempotent_handler
    detector(payload, window=last_7d): 4 pattern detectors
    AccumulatorAnomaly row + auto-Investigation if severity >= medium
    NO outbound event — anomaly detection is DB+audit only per §3
```

### 5.4 RBAC — 3-layer dual-gate (R1 BLOCK 1)

JWT claims (per SP-0 SD-1, unchanged): `roles: string[]`. MFA elevation and PHI access level are NOT JWT claims — they are checked at request-time via core-platform session lookup (D6/D6a, R3 NEW BLOCK 3): `session.mfa_elevated_until > now()` for ePHI; `user.phi_access_level` for response masking.

| Role | Read | Status transition | Release hold | Tune thresholds | Trigger graph run |
|---|---|---|---|---|---|
| `reclaimrx.viewer` | yes | no | no | no | no |
| `reclaimrx.investigator` | yes | yes (per state machine §5.5.1) | yes (w/ reason; audited) | no | yes |
| `reclaimrx.admin` | yes | yes (incl. override-locked transitions, audited) | yes (incl. emergency-override release with mandatory `emergency_reason_code` enum, audited) | yes (per-field audited) | yes |

**Three enforcement layers (all required — defense-in-depth):**

1. **Backend (authority — R1 BLOCK 1).** Every backend endpoint decorated with `require_role(...)` that validates JWT roles before any DB read/write. 403 `INSUFFICIENT_ROLE` if missing. Backend never trusts BFF or React role checks.
2. **BFF (perimeter).** BFF re-validates the role from JWT before proxying. Allows defense-in-depth and prevents the backend from being exposed unmediated.
3. **React `<RoleGate>` (UX).** Hides/disables actions the user can't perform. Improves UX; security-irrelevant on its own.

**Admin override semantics (R1 CONCERN 5 + R4 NEW CONCERN 2):** Admins can perform actions other roles cannot (override-locked transitions, emergency hold release with mandatory `emergency_reason_code` enum value such as `LEGAL_HOLD`, `REGULATORY_DIRECTIVE`, `IRRECOVERABLE_HARM`, `OTHER_WITH_NOTE`). **Every release still requires a reason — the audit invariant never weakens. Emergency override means structured reason codes + admin role, NOT reason-free.** All admin actions are audited; audit entries remain **append-only and immutable**. Admin cannot edit/delete audit history.

### 5.5 Backend endpoints (new, Plan A — complete inventory per R1 BLOCK 2)

| # | Endpoint | Path | RBAC | Rate limit (D13) | Notes |
|---|---|---|---|---|---|
| 1 | List investigations | `GET /api/v1/reclaimrx/investigations` | viewer+ | 60/min/user | Paginated, filterable; tenant-scoped |
| 2 | Investigation detail | `GET /api/v1/reclaimrx/investigations/{id}` | viewer+ + MFA-elevated session (D6a) | 60/min/user | PHI audit + no-store; mask by user PHI access level via core-platform session/user policy lookup |
| 3 | Transition status | `POST /api/v1/reclaimrx/investigations/{id}/transitions` | investigator+ | 30/min/user | State machine validated (§5.5.1) |
| 4 | Add note | `POST /api/v1/reclaimrx/investigations/{id}/notes` | investigator+ | 30/min/user | Append-only |
| 5 | List rule firings | `GET /api/v1/reclaimrx/rule-firings` | viewer+ | 60/min/user | Plan C UI consumer (R1 BLOCK 2) |
| 6 | List ML scores | `GET /api/v1/reclaimrx/ml-scores` | viewer+ | 60/min/user | Plan C UI consumer (R1 BLOCK 2) |
| 7 | ML score features | `GET /api/v1/reclaimrx/ml-scores/{id}/features` | viewer+ | 60/min/user | XGBoost feature importance (R1 BLOCK 2) |
| 8 | List holds | `GET /api/v1/reclaimrx/holds` | viewer+ | 60/min/user | Tenant-scoped |
| 9 | Release hold | `POST /api/v1/reclaimrx/holds/{hold_id}/release` | investigator+ (admin for emergency override) | 30/min/tenant | Body `{reason, investigation_id, emergency_reason_code?, emergency_note?}`. `reason` always required (any role). `emergency_reason_code` enum (`LEGAL_HOLD`/`REGULATORY_DIRECTIVE`/`IRRECOVERABLE_HARM`/`OTHER_WITH_NOTE`) + `emergency_note` (required iff code = `OTHER_WITH_NOTE`) accepted ONLY when caller has `reclaimrx.admin` role AND the release would otherwise be blocked (e.g., investigation already closed; hold in unusual state). Backend verifies `investigation_id` belongs to same tenant AND active per R1 CONCERN 7 (admin emergency override skips active check but requires emergency_reason_code). 100% coverage; transactional outbox. (R4 NEW CONCERN 2 + R5 wiring) |
| 10 | Trigger graph run | `POST /api/v1/reclaimrx/graph-runs/trigger` | investigator+ | 1/hr/tenant | 409 if run in-flight per tenant |
| 11 | List graph runs | `GET /api/v1/reclaimrx/graph-runs` | viewer+ | 60/min/user | History; tenant-scoped |
| 12 | Graph run detail | `GET /api/v1/reclaimrx/graph-runs/{run_id}` | viewer+ | 60/min/user | Polling endpoint (R1 BLOCK 2) |
| 13 | Fraud ring detail | `GET /api/v1/reclaimrx/fraud-rings/{id}` | viewer+ | 60/min/user | Node/edge graph payload capped **at max 500 nodes / 2000 edges (binding — R2 ADVISORY 2). Plan E may tune rendering but cannot relax the payload cap.** Larger rings return neighborhood subgraph with `truncated: true` flag. |
| 14 | Recovery aggregations | `GET /api/v1/reclaimrx/recovery?period=mtd&group_by=program` | viewer+ | 60/min/user | Decimal sums; tenant-scoped |
| 15 | Dashboard summary | `GET /api/v1/reclaimrx/dashboard-summary` | viewer+ | 60/min/user | 6 tile metrics aggregated (R1 BLOCK 2) |
| 16 | Get thresholds | `GET /api/v1/reclaimrx/thresholds` | viewer+ | 60/min/user | Per-tenant current config |
| 17 | Update thresholds | `PUT /api/v1/reclaimrx/thresholds` | admin only | 10/hr/tenant | Per-field hash-chained audit; new version row |
| 18 | List accumulator anomalies | `GET /api/v1/reclaimrx/accumulator-anomalies` | viewer+ | 60/min/user | Paginated; PHI mask + audit |

**BFF routes (sliced per §6 Plan ownership, R4 NEW CONCERN 3 — one source of truth):** 1:1 proxies of backend endpoints #1-18 at `/api/reclaimrx/*`, each landing in the plan that needs them (Plan B: investigations/transitions/notes/search; Plan C: rule-firings/ml-scores/thresholds; Plan D: holds/recovery/dashboard-summary; Plan E: graph-runs/fraud-rings + accumulator-anomalies surfaced). Each BFF route does JWT auth + role re-validation + MFA session check for PHI endpoints + correlation-id minting + structured error envelope. Plus `GET /api/reclaimrx/search` for cmdk palette scope (Plan B). **§6 is the binding plan-ownership map for BFF routes; this section is a quick reference.**

#### 5.5.1 Investigation state machine (R1 CONCERN 6)

| From | To (allowed) | Required role | Required fields |
|---|---|---|---|
| open | in_progress | investigator+ | reason |
| open | pending_review | investigator+ | reason |
| open | escalated | investigator+ | reason |
| in_progress | pending_review | investigator+ | reason |
| in_progress | closed_confirmed | investigator+ | reason, outcome_label='confirmed', recovered_amount (Decimal) |
| in_progress | closed_false_positive | investigator+ | reason, outcome_label='false_positive' |
| in_progress | closed_no_action | investigator+ | reason, outcome_label='no_action' |
| in_progress | escalated | investigator+ | reason |
| pending_review | in_progress | investigator+ | reason |
| pending_review | closed_* | investigator+ | reason + outcome_label (+ recovered for confirmed) |
| pending_review | escalated | investigator+ | reason |
| escalated | in_progress | admin only | reason (override) |
| escalated | closed_* | admin only | reason (override) + outcome_label |
| closed_* | open | **admin only** | reason (override-locked) — re-opens audit-trail visibly |

Terminal states: `closed_confirmed`, `closed_false_positive`, `closed_no_action`. Hold release allowed in any non-closed state; in closed_confirmed if recovered_amount needs adjustment (admin only).

---

## 6. 5-plan carve

| Plan | Scope | Visible to operator? |
|---|---|---|
| **A — Backend + Contract Layer + Production Bindings** | Module scaffold, graph_analysis_service + job, accumulator_consumer + detector, 5 new tables + threshold_config_audit + outbox_event + alembic migration **with PG RLS policies (null-deny via `current_setting('app.tenant_id', true)` per D8) + indexes (R1 BLOCK 7)**, 18 API endpoints with backend `require_role()` (R1 BLOCK 1), transactional outbox + dispatcher (R1 BLOCK 4), state machine validator, **2 event-contract docs authored (`payment.hold_released`, `fwa.graph_run_completed`) — R2 NEW BLOCK 1**, **production app factory bindings per D14**, **SP-0 contract layer (R3 NEW BLOCK 2): `packages/contract/src/clients/reclaimrx.ts` typed `ReclaimRxClient` for all 18 endpoints + `packages/contract/src/schemas/reclaimrx.ts` zod request/response schemas + `packages/contract/src/impls/reclaimrx-real.ts` + `reclaimrx-mock.ts` (RealImpl/MockImpl per SP-0) + `packages/contract/src/cache/reclaimrx-policy.ts` (cache-tag invalidation map per surface) + contract tests asserting real impl matches mock shape**. **Real routed pages with `<EmptyState cta="Plan B will populate">` (R1 BLOCK 9 — not placeholder dead code).** | Empty-state pages (no functional UI) |
| **B — Investigation Spine UI** | InvestigationListPage + DetailPage + StatusTransitionDialog + EvidencePanel + cross-link to SP-2; module.config routes/navEntry/commandPaletteScope; BFF for investigations/transitions/notes/search | Yes |
| **C — Rule Firings + ML Scores + Threshold Tuning UI** | RuleFiringBrowser + RuleExplainer + MLScoreDetailPage + feature-importance chart + ScoreDistributionChart + admin-only ThresholdTuningPage with sliders + numeric inputs; BFF for rule-firings/ml-scores/thresholds | Yes |
| **D — Payment Holds + Recovery + Dashboard** | HoldListPage + HoldReleaseDialog (UI consumes Plan A's existing release endpoint; outbox publish is backend's job per D11/R2 NEW BLOCK 1) + RecoveryTrackerPage + DashboardTiles (6 tiles); BFF for holds/recovery/dashboard-summary | Yes |
| **E — Graph Viz + E2E + Synthetic FWA Fixtures + Acceptance** | GraphRunsPage + FraudRingDetailPage (force-directed viz, clickthrough to SP-2, capped payload) + TriggerGraphRunButton + 5 fraud-archetype fixtures + Playwright E2E lifecycle + cross-tenant isolation tests + `docs/sp-3-acceptance.md` | Yes — closes the round trip |

### Plan A acceptance (no functional UI; backend airtight)

Required gates:
- All 18 endpoints return correct shapes under unit + integration tests, with backend `require_role()` validated against the 3-role matrix
- Graph job runs end-to-end on synthetic fixtures producing N rings; failure modes (stale_timeout, completed_partial, failed) tested per `GraphRun.status` enum (no manual cancel — R2 NEW CONCERN 2)
- Accumulator consumer processes synthetic events and opens investigations; idempotent_handler verified by replay
- Transactional outbox tested: DB commit succeeds + publish fails → outbox retries; publish succeeds + consumer replay → idempotent (R1 BLOCK 4)
- **PG RLS policies enforced** per new tenant-owned table; cross-tenant isolation test passes from a session WITHOUT `current_setting('app.tenant_id')` set → zero rows visible (R1 BLOCK 7)
- **Indexes present** on `(tenant_id, status)`, `(tenant_id, severity)`, `(tenant_id, detected_at DESC)`, `(tenant_id, source_ref_id)`, `(tenant_id, member_id)`, `(idempotency_key)` UNIQUE on outbox (R1 BLOCK 7)
- **State machine validator** rejects every invalid transition (R1 CONCERN 6); tested matrix
- **Per-tenant `pg_try_advisory_xact_lock(hash('graph_run', tenant_id))` for run-creation critical section** (transaction-scoped — releases at COMMIT) + **durable `graph_runs.status='running'` row as cross-process concurrency authority** (R3 NEW BLOCK 1 + R4 NEW CONCERN 1); APScheduler worker does NOT hold a cross-process lock
- **Threshold config versioning** — every UPDATE creates new version row + per-field hash-chained audit entries (R1 CONCERN 2)
- **Rate limit middleware** mounted with per-endpoint config (R1 CONCERN 8 / D13)
- **Production app factory integration test through `create_app()` (R2 NEW BLOCK 3 / D14 / LESSON-006):** asserts SecurityHeadersMiddleware, RateLimitMiddleware, DLQ router, processed_events cleanup scheduler, DLQ depth monitoring (R3 NEW CONCERN 3), and daily audit verification job are all mounted/registered (6 bindings)
- **Daily audit hash-chain verification job (R2 NEW CONCERN 4):** 03:00 UTC cron; walks audit table; verifies each entry's `prev_entry_hash` matches the prior entry's `entry_hash`; alerts on break; **rejects writes with empty `entry_hash` per `.claude/rules/hipaa-2026.md`** ("MUST compute `entry_hash` on EVERY audit log write — never write with empty hash")
- **2 event-contract docs authored (R2 NEW BLOCK 1):** `docs/api-contracts/events/payment.hold_released.md` + `docs/api-contracts/events/fwa.graph_run_completed.md` — contracts in §11.5 of this spec; doc files instantiate them
- 100% coverage on financial + PHI + security + auth/role paths; 95% baseline on other active code (R1 BLOCK 9 — aligns with `.claude/rules/testing.md`)
- Alembic migration applies + rolls back cleanly
- **RLS acceptance test (R2 NEW BLOCK 2):** SQL test opens a session WITHOUT setting `app.tenant_id` → queries each new tenant-owned table → asserts zero rows AND no exception (verifies null-deny via `missing_ok=true`)
- **Real routed pages with `<EmptyState>` content** — tested for render, not dead code (R1 BLOCK 9)

---

## 7. Data flow

### 7.1 Canonical investigator triage path (Plan B)

```
1. Investigator → /reclaimrx/investigations
2. BFF: GET /api/reclaimrx/investigations?status=open&severity=high&page=1
   → JWT auth + role re-validate (any reclaimrx.*) + tenant header check
   → Cache: 30s TTL, tag: reclaimrx:investigations:{tid}
   → **List payload is PHI-AWARE (R1 CONCERN 4):** includes id/status/severity/source/opened_at/severity counts only;
     NO member name/dob/ssn in list rows. PHI-derived fields excluded from cache.
3. Click row → /reclaimrx/investigations/{id}
4. BFF: GET /api/reclaimrx/investigations/{id}
   → core-platform session_lookup(user_id): require session.mfa_elevated_until > now() (D6a); 403 MFA_REQUIRED if not → re-elevation prompt
   → backend require_role('reclaimrx.viewer'); 403 INSUFFICIENT_ROLE if missing
   → backend mask by user.phi_access_level (full/partial/redacted) via core-platform session/user policy lookup
   → audit entry action="phi_access" entity_id={id}
   → Cache-Control: no-store
5. EvidencePanel renders linked claims/members/prescribers (cross-link into SP-2)
6. Click "Mark in_progress" → StatusTransitionDialog (required reason)
   → POST /api/reclaimrx/investigations/{id}/transitions {to_status:'in_progress', reason}
   → BFF role re-validate (investigator+) → backend require_role
   → backend state machine validator checks transition allowed (§5.5.1)
   → audited transition row (append-only)
   → TanStack Query invalidates tag → list refreshes
```

### 7.2 Hold release path — transactional outbox (R1 BLOCK 4)

```
1. Investigator on InvestigationDetailPage sees active hold ($X.XX)
2. Click "Release hold" → HoldReleaseDialog → required reason
3. POST /api/reclaimrx/holds/{hold_id}/release {reason, investigation_id, emergency_reason_code?, emergency_note?}
   (emergency_reason_code + emergency_note only accepted when caller is reclaimrx.admin per R4 NEW CONCERN 2 + R5)
4. BFF: role re-validate (investigator+) → backend
5. Backend require_role('reclaimrx.investigator')
6. Backend authorization check (R1 CONCERN 7):
   - Verify hold exists with tenant_id=current_tenant
   - Verify hold.investigation_id == body.investigation_id (must match exactly)
   - Verify investigation is non-closed OR caller is admin
   - 403 HOLD_INVESTIGATION_MISMATCH if any fail
7. Backend opens DB transaction:
   a. Lock hold row FOR UPDATE
   b. **Idempotency rules (R2 NEW CONCERN 1 — three deterministic cases):**
      - `status == 'released'` AND `released_by == JWT.sub` AND `release_reason == body.reason` AND `investigation_id == body.investigation_id`
        → **200 OK** with prior release state (true idempotent replay)
      - `status == 'released'` AND any of (released_by, reason, investigation_id) differs
        → **409 ALREADY_RELEASED** with prior release info `{released_at, released_by, reason}` (conflict — different actor or context)
      - `status == 'active'`
        → proceed to step c (normal release path)
      - `status` in (`expired`, `cancelled`, any other)
        → **422 HOLD_NOT_ACTIVE** with current status in `error.field`
   c. UPDATE payment_holds SET status='released', released_at, released_by, release_reason
   d. INSERT audit_entry with before/after $ amount (Decimal, ROUND_HALF_UP) + hash chain
   e. INSERT outbox_event with idempotency_key=f'hold:release:{hold_id}' UNIQUE
      envelope_json = {
        type: 'payment.hold_released',
        tenant_id,                              ← R1 BLOCK 3: envelope-level tenant_id
        ordering_key: hold_id,
        idempotency_key: f'hold:release:{hold_id}',
        schema_version: '1.0',
        payload: {hold_id, amount:str(decimal), released_by, reason, investigation_id}
      }
   f. COMMIT transaction (DB + audit + outbox row all atomic)
8. Background outbox_dispatcher (poll every 1s):
   - SELECT pending outbox rows ORDER BY created_at LIMIT N
   - For each: publish to event bus → on success UPDATE status='published', published_at
   - On failure: UPDATE attempt_count++, last_error; retry with exponential backoff
   - After 10 failed attempts: status='failed' + alert
9. PaySync consumer (SP-1) wraps with idempotent_handler — replays are safe
```

**Tested cases (Plan A integration tests):**
- DB commit succeeds + publish fails → outbox row remains pending; dispatcher retries; eventually published
- Publish succeeds + consumer receives twice → idempotent_handler dedupes
- Hold already released by same actor/reason/investigation (true replay) → 200 with prior release info
- Hold already released by different actor or different reason → 409 ALREADY_RELEASED
- Hold in non-active non-released state → 422 HOLD_NOT_ACTIVE
- Hold from different investigation → 403 HOLD_INVESTIGATION_MISMATCH

### 7.3 Graph run trigger path (Plan A backend + Plan E UI)

```
1. Admin (or investigator) on GraphRunsPage clicks "Run now"
2. POST /api/reclaimrx/graph-runs/trigger
3. BFF role re-validate (investigator+) → backend require_role
4. Backend rate-limit check (D13: 1/hr/tenant) → 429 if exceeded
5. Backend run-creation critical section (R3 NEW BLOCK 1 — corrected advisory-lock semantics):
   - BEGIN TXN
   - `SELECT pg_try_advisory_xact_lock(hash('graph_run', tenant_id))` — **transaction-scoped** lock auto-released at COMMIT/ROLLBACK; prevents two simultaneous trigger requests racing the INSERT
   - If false → ROLLBACK → 409 RUN_IN_PROGRESS with existing run_id
   - `SELECT 1 FROM graph_runs WHERE tenant_id={tid} AND status='running' LIMIT 1` — durable in-flight check
   - If exists → ROLLBACK → 409 RUN_IN_PROGRESS with that run_id
   - INSERT graph_runs (status='running', trigger='on_demand', correlation_id, stale_timeout_at=now+6h)
   - COMMIT (advisory lock auto-released; durable `running` row is now the authority)
6. **The `graph_runs.status='running'` row is the durable concurrency authority** — APScheduler worker does NOT hold any cross-process lock. Stale-running sweeper marks abandoned rows `failed` after `stale_timeout_at`.
7. Backend: spawn APScheduler oneshot (recommend; verify `shared/scheduling/` path at plan-write per R1 ADVISORY 5)
   On exception in worker: UPDATE graph_runs SET status='failed', error_code, error_message (sanitized)
8. **Note: no manual cancellation in SP-3 (R2 NEW CONCERN 2).** Stale-running sweeper auto-fails runs that exceed `stale_timeout_at` (default 6h) with `error_code='STALE_TIMEOUT'`. No cancel endpoint. Worker crash recovery: the durable `running` row is detected stale → set to `failed` → next trigger succeeds (R3 NEW BLOCK 1 testing requirement).

9. graph_analysis_service.run(tenant_id, graph_run_id):
   a. Load last 90d claims + entities WHERE tenant_id={tid} (RLS-enforced via worker session setting `app.tenant_id`)
   b. Check size bounds (R1 CONCERN 3): if nodes > 50000 OR edges > 200000 → completed_partial + per-program splitting OR fail with operational alert
   c. Build NetworkX graph
   d. Connected-component + density scoring
   e. For each high-density: INSERT fraud_rings; if severity high: auto-Investigation
   f. UPDATE graph_runs status='completed' OR 'completed_partial', completed_at=now, rings_detected, investigations_opened (no advisory unlock needed — TXN-scoped lock from step 5 long-released)
   g. INSERT outbox_event for fwa.graph_run_completed (envelope per R1 BLOCK 3)
   On failure path: UPDATE graph_runs status='failed', failed_at=now, error_code, error_message; DELETE fraud_rings WHERE graph_run_id={graph_run_id} (atomic cleanup R1 BLOCK 8)
10. UI polls GET /api/reclaimrx/graph-runs/{run_id} every 5s (endpoint #12)
11. On completion: GraphRunsPage refreshes; new investigations appear in list
```

**Stale-running detection:** background sweeper job marks runs with `started_at + 6h < now() AND status='running'` as `failed` with `error_code='STALE_TIMEOUT'`.

---

## 8. Error handling

Inherits SP-0 error envelope. SP-3-specific:

| Failure mode | Behavior |
|---|---|
| Invalid status transition (state machine) | 422 `INVALID_TRANSITION` with allowed-next-states in `error.field` |
| Hold release without reason | 422 `REASON_REQUIRED` |
| Hold release by viewer role | 403 `INSUFFICIENT_ROLE` (backend authority — R1 BLOCK 1) |
| Hold release with mismatched investigation_id | 403 `HOLD_INVESTIGATION_MISMATCH` (R1 CONCERN 7) |
| Hold release replay — same actor/reason/investigation | 200 with prior release info (true idempotent — R2 NEW CONCERN 1) |
| Hold release conflict — already released by different actor or reason | 409 `ALREADY_RELEASED` with prior release info (R2 NEW CONCERN 1) |
| Hold in non-active non-released state | 422 `HOLD_NOT_ACTIVE` with current status in `error.field` (R2 NEW CONCERN 1) |
| Graph run trigger while in-flight | 409 `RUN_IN_PROGRESS` with existing `run_id` |
| Graph run trigger rate-limit | 429 `RATE_LIMITED` Retry-After (D13) |
| Threshold update out-of-range | 422 `THRESHOLD_OUT_OF_RANGE` with allowed min/max |
| **Tenant-scoped not-found (R1 BLOCK 6)** | Lookups always WHERE `{tenant_id, id}`; if no row → 404 with non-enumerating body `{error.code:'NOT_FOUND'}`; mismatched tenant HEADER → 403 `TENANT_MISMATCH`. **No unscoped existence check.** |
| MFA not present (PHI endpoint per D6a) | 403 `MFA_REQUIRED` |
| PHI access level too low | 200 with masked payload + `X-Phi-Access-Masked: true` header |
| Backend down — list reads | SP-0 `stale-ok` 60s cache + "data may be outdated" banner |
| Backend down — hold release | NO fallback — fail closed; toast `SERVICE_UNAVAILABLE` |
| Backend down — graph run trigger | NO fallback — fail closed |
| Backend down — threshold update | NO fallback — fail closed |
| ML feature importance missing | 200 with `features:[]` + warning banner (degraded view) |

**PHI posture (binding):** see D6 + D6a. **PHI-aware caching:** list endpoints cache only non-PHI summary fields; detail/evidence stays no-store (R1 CONCERN 4).

---

## 9. Testing

### 9.1 Test layers

| Layer | What | Where | When |
|---|---|---|---|
| Unit (backend) | graph density math, 4 accumulator pattern detectors, threshold validation, state machine validator, $ allocation, audit hash chain, outbox dispatcher logic | `modules/reclaimrx/tests/unit/` | Every PR |
| Unit (frontend) | RoleGate hook, transition dialog validation, threshold slider clamping, feature-importance chart, primitives | `packages/modules/reclaimrx/tests/unit/` | Every PR |
| Integration (backend) | 18 endpoints × role matrix; outbox transactional pattern (commit+publish-fail; replay); idempotent consumer wire-up; graph-job E2E on fixtures; state machine matrix; threshold versioning + hash-chained audit; PG RLS isolation | `modules/reclaimrx/tests/integration/` | Every PR |
| Integration (BFF↔backend) | Each BFF route via docker-compose; 401/403/409/422/429 cases; PHI no-store; MFA gate; cache-tag invalidation | `packages/modules/reclaimrx/tests/integration/` | Every PR |
| Cross-tenant isolation | Per endpoint: 2 tenants, populate both, query as A, verify zero B data. **Plus PG RLS test** (session without `app.tenant_id` set → zero rows) | `tests/integration/cross-tenant-isolation.test.ts` | Every PR |
| **N+1 detection (R1 CONCERN 9)** | Query counter fixture wraps: investigation detail + evidence fan-out, fraud ring detail, recovery aggregation, dashboard summary. Assert query count constant regardless of result-set size. | `modules/reclaimrx/tests/integration/n_plus_one.py` | Every PR |
| E2E (Plan E) | Playwright lifecycle: upcoding-ring seeded → graph job runs → ring detected → investigation auto-opened → investigator MFA-elevates → opens → reviews evidence → releases hold w/ reason → closes confirmed → recovery $ posts | `portal/operator/tests/e2e/reclaimrx/` | PR + pre-merge |

### 9.2 Coverage gates (R1 BLOCK 9 — aligned to `.claude/rules/testing.md`)

- **100%** on financial logic (recovery sums, hold math, threshold $ validation, Decimal precision in event payloads)
- **100%** on PHI paths (encryption, decryption, audit emission, no-store header, masking, MFA gate)
- **100%** on security paths (auth, role gate at all 3 layers, tenant scoping, RLS, input validation, idempotency keys, outbox dispatcher)
- **95% baseline** on all other active SP-3 code (per `.claude/rules/testing.md`). Project Auto-Gate may tighten to 99% but spec binds to 95%.
- Excluded: NetworkX internals, fixture loaders

### 9.3 SQLAlchemy fixture pattern

Per LESSON-001 + LESSON-007: SAVEPOINT-based isolation; `_UUIDString` TypeDecorator if any PG_UUID columns hit SQLite test path. **Plan-writer applies both patterns from the start.**

### 9.4 Synthetic FWA fixtures (Plan E)

5 archetypes; all NPIs Luhn-valid (prefix 80840); all NDCs 11-digit; no real PHI. SAM cross-link to NPI `8084009009` (consistent with SP-2 fixtures). See R1 ADVISORY 3 — plan-writer to confirm invented identifiers vs limited public data per SP-2 fixture policy.

| File | Archetype | Triggers |
|---|---|---|
| `upcoding-ring.json` | 1 prescriber, 3 pharmacies, 12 claims w/ elevated J-codes | graph density + rule_firing |
| `doctor-shopping.json` | 1 member, 5 prescribers, 8 CII opioid claims in 30d | rule_firing + graph |
| `ghost-prescriber.json` | NPI inactive in NPPES with 4 active claims | rule_firing |
| `ndc-switching.json` | Pharmacy submitting NDC-A while prescribed NDC-B | ml_score |
| `accumulator-manipulation.json` | Member, 3 payers, accumulator resets crossing month boundary | accumulator_anomaly |

### 9.5 Performance + scale guardrails (R1 CONCERN 3)

- Investigation list (50/page): <150ms p95
- Investigation detail (w/ evidence fan-out): <300ms p95
- Hold release end-to-end (incl. outbox write): <500ms p95
- Graph job per tenant (90d window): <5min wall time at 50K nodes / 200K edges
- Dashboard tiles: <200ms p95 via 60s-cached aggregations

**NetworkX scale guardrails (R1 CONCERN 3):**
- Max nodes per tenant run: 50,000
- Max edges per tenant run: 200,000
- Memory ceiling: 4GB per run (monitored via psutil)
- Claim extraction paginated 10K-row chunks
- Indexes required: `claims(tenant_id, created_at DESC)`, `claims(tenant_id, member_id)`, `claims(tenant_id, prescriber_npi)`, `claims(tenant_id, pharmacy_nabp)` — Plan A migration adds any missing
- **Bound exceeded behavior:** split into per-program subgraphs and run sequentially; if still over → `completed_partial` with operational alert; investigations still opened for rings within the processed subset

---

## 10. Open questions / plan-time decisions

1. **Graph library** — NetworkX (recommended; pure-Python; sub-100K-node graphs).
2. **Graph viz library** — D3 vs visx vs react-force-graph. Plan E locks based on SP-0 inventory.
3. **Threshold tuning UX** — sliders + numeric inputs (recommended).
4. **"Create new rule" UI** — NO per non-goal §3. Confirm at plan-write.
5. **PaySync consumer** — SP-1's work; SP-3 publishes via outbox regardless.
6. **ML retraining** — `outcome_label` persists; retraining out of scope.
7. **Graph scheduler** — APScheduler in-process (verify `shared/scheduling/` path at plan-write per R1 ADVISORY 5).
8. **Threshold versioning** — RESOLVED YES via ThresholdConfig.version + ThresholdConfigAudit + Investigation.threshold_config_version FK + threshold_snapshot defense-in-depth (R1 CONCERN 2).
9. **`reclaimrx.viewer` role distribution** — tenant-admin decision; tenant-onboarding docs.
10. **Plan A oversize check (R1 ADVISORY 1)** — plan-writer evaluates whether to move read-only endpoints for rule-firings/ml-scores/dashboard-summary into Plans C/D. Spec acceptance retains all 18 endpoints in Plan A; plan-writer may rebalance.

---

## 11. Cross-references

**Founding specs (binding):**
- SP-0: `docs/superpowers/specs/2026-05-14-sp0-integration-foundation-design.md`
- SP-0 auth (SD-1): `docs/superpowers/specs/2026-05-15-sp0-decision-spike-auth-interface.md`
- SP-0 composition (SD-4): `docs/superpowers/specs/2026-05-15-sp0-decision-spike-composition.md`
- SP-1: `docs/superpowers/specs/2026-05-16-sp1-paysync-operator-portal-design.md`
- SP-2: `docs/superpowers/specs/2026-05-16-sp2-directories-portal-design.md`

**Decomposition shift (binding):** SP-3=ReclaimRx, SP-4=Billing/Analytics, SP-5=Claims/Adjudication.

**Project rules (binding):**
- `CLAUDE.md` (project) + `.claude/rules/architecture.md` + `code-standards.md` + `error-handling.md` + `event-bus.md` + `financial-precision.md` + `hipaa-2026.md` + `performance.md` + `phi-compliance.md` + `security.md` + `tenant-isolation.md` + `testing.md`

**R1 codex review (addressed):** `docs/superpowers/codex-sp3-spec-review-r1.md`

**Existing code SP-3 extends (plan-writer MUST grep-verify before invoking — R1 CONCERN 10):**
- `modules/reclaimrx/src/consumers/*.py` — verify 8 existing consumers + `wire_consumers()` location
- `modules/reclaimrx/src/services/rule_engine.py` — verify exists
- `modules/reclaimrx/src/services/ml_scorer.py` — verify exists
- `modules/reclaimrx/src/models/investigation.py` — verify; extend with new columns if missing OR verify present
- `modules/reclaimrx/src/models/payment_hold.py` — verify; extend with `released_*` columns
- `shared/events/bus.py` — verify `EventEnvelope` shape
- `shared/db/models/phi_mixin.py` + `shared/crypto/sqlalchemy_types.py` — verify PHI infrastructure
- `shared/scheduling/` — verify APScheduler integration (R1 ADVISORY 5)
- `core-platform` `RateLimitMiddleware` — verify mount pattern (D13)
- `packages/modules/directories/` (SP-2) — federated search registration point
- `portal/operator/app/api/` — BFF mount location

Plan-writer must fail-fast if any path missing (SP-2 discipline).

### 11.5 Event contracts (R1 BLOCK 3)

#### `payment.hold_released` (Plan A — release endpoint + outbox publish + event-contract doc all in Plan A per R2 NEW BLOCK 1; Plan D wires UI + BFF)

```yaml
event_type: payment.hold_released
schema_version: "1.0"
tenant_id: UUID                          # envelope-level (R1 BLOCK 3)
ordering_key: hold_id                    # ensures per-hold ordering
idempotency_key: "hold:release:{hold_id}"  # consumer dedupes
payload:
  hold_id: UUID
  amount: string                         # Decimal serialized as str()
  released_by: string                    # JWT sub
  reason: string                         # always present
  investigation_id: UUID
  released_at: ISO8601
  emergency_reason_code: string | null   # admin emergency override only (R5)
  emergency_note: string | null          # admin emergency override only (R5)
forward_compatibility: consumers MUST ignore unknown fields; new fields added in 1.x are non-breaking
docs_path: docs/api-contracts/events/payment.hold_released.md (authored in Plan A per R2 NEW BLOCK 1 — co-located with publish path; Plan D consumes via UI)
```

#### `fwa.graph_run_completed` (Plan A — written via outbox in Plan A)

```yaml
event_type: fwa.graph_run_completed
schema_version: "1.0"
tenant_id: UUID                          # envelope-level (R1 BLOCK 3)
ordering_key: graph_run_id
idempotency_key: "graph_run:{graph_run_id}:completed"
payload:
  graph_run_id: UUID
  status: "completed" | "completed_partial" | "failed"
  rings_detected: int                    # 0 if status=failed
  investigations_opened: int             # 0 if status=failed
  records_scanned: int                   # 0 if status=failed before scan
  lookback_window_days: int
  started_at: ISO8601
  completed_at: ISO8601 | null           # null if status=failed (R3 NEW CONCERN 4)
  failed_at: ISO8601 | null              # set if status=failed (R3 NEW CONCERN 4)
  error_code: string | null              # set if status=failed
  error_message: string | null           # sanitized; set if status=failed
forward_compatibility: same rule as above
docs_path: docs/api-contracts/events/fwa.graph_run_completed.md (authored in Plan A)
```

**`accumulator.updated` (consumed; published by member-management — R1 CONCERN 1):**

```yaml
event_type: accumulator.updated
schema_version: "1.0"
tenant_id: UUID                          # envelope-level
ordering_key: member_id
idempotency_key: "accumulator:{member_id}:{accumulator_period}:{updated_at_epoch}"
payload:
  member_id: UUID
  tenant_id: UUID
  accumulator_type: string
  period: string                         # e.g., "2026-Q2"
  amounts:
    oop: string                          # Decimal as str
    deductible: string
    [...]
  source_payer_id: UUID | null
publisher: modules/member-management
consumer (this spec): modules/reclaimrx/src/consumers/accumulator_consumer.py
plan-writer action: confirm member-management actually publishes this event with the above shape; if not, scope a separate publisher-side fix
```

**Wave control ledger:**
- Pre-write draft (history): `waves/B10/SP-3-design-draft.md` (R5)
- This spec: `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md`
- R1 review: `docs/superpowers/codex-sp3-spec-review-r1.md` (NO-GO)
- R2 review: `docs/superpowers/codex-sp3-spec-review-r2.md` (NO-GO)
- R3 review: `docs/superpowers/codex-sp3-spec-review-r3.md` (NO-GO)
- R4 review: `docs/superpowers/codex-sp3-spec-review-r4.md` (GO-WITH-CHANGES)
- R5 review: `docs/superpowers/codex-sp3-spec-review-r5.md` (GO-WITH-CHANGES, cleanup wired inline)
- Acceptance (Plan E): `docs/sp-3-acceptance.md` (new at Plan E close)

---

## 12. Next steps

1. ~~Codex spec consult.~~ **DONE — 5 rounds; converged GO-WITH-CHANGES with all cleanup wired inline.**
2. **Spec self-review** (placeholder scan, internal consistency, scope, ambiguity) — see §12.1 below.
3. **User review gate** — Mike reads this spec; redirects or approves.
4. On user approval: invoke `superpowers:writing-plans` for SP-3 plans A-E.
5. **Path verification at plan-write (per R1 CONCERN 10):** plan-writer MUST grep-verify every asserted existing path before invoking any plan:
   - `modules/reclaimrx/src/consumers/*.py` (8 existing consumers + `wire_consumers()`)
   - `modules/reclaimrx/src/services/rule_engine.py`, `ml_scorer.py`
   - `modules/reclaimrx/src/models/investigation.py`, `payment_hold.py` (extend with new columns)
   - `shared/events/bus.py` (`EventEnvelope` shape)
   - `shared/db/models/phi_mixin.py`, `shared/crypto/sqlalchemy_types.py`
   - `shared/scheduling/` (APScheduler integration — R1 ADVISORY 5)
   - `modules/core-platform/` MFA elevation API + session lookup (D6/D6a — R3 NEW BLOCK 3)
   - `core-platform` `RateLimitMiddleware`, `SecurityHeadersMiddleware`, DLQ router (D14)
   - `packages/contract/` extension pattern for new module client (R3 NEW BLOCK 2)
   - `packages/modules/directories/` (SP-2 federated search registration point — D10)
   - `portal/operator/app/api/` (BFF mount location)
   - Fail-fast if any path missing (SP-2 discipline).
6. Plans must not repeat known failure modes: invented paths, wrong ORM names, insufficient coverage gates, missing `EventEnvelope` tenant_id, missing cross-tenant tests, missing PG RLS, `page.request.*` in Playwright (use `fetchViaPage` + `page.route` per SP-2 R3 lesson).

### 12.1 Spec self-review checklist (to run after this commit)

- [ ] Placeholder scan: no TBD / TODO / vague requirements remain
- [ ] Internal consistency: §5.5 endpoint table matches §6 plan ownership matches §11.5 event contracts
- [ ] Lock-decision conflicts: no D1-D14 contradiction
- [ ] State machine §5.5.1 covers every status transition referenced elsewhere
- [ ] Event envelope schema in §11.5 matches §7.2 hold-release flow exactly (incl. emergency fields)
- [ ] PG RLS expression in D8 matches §6 Plan A acceptance test
- [ ] BFF phasing per §5.5 ("§6 is binding") agrees with §6 row contents
- [ ] Coverage gates §9.2 match `.claude/rules/testing.md` (95% baseline; 100% on financial/PHI/security/auth)
- [ ] No real PHI in §9.4 fixture descriptions
- [ ] No real PBM vendor names anywhere

---

*End of spec.*
