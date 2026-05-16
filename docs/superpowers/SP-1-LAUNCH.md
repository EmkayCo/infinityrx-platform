# SP-1 Launch Packet — PaySync Operator Portal

**Purpose:** self-contained handoff for a fresh Claude Code session window to execute SP-1.
**Branch:** `wave/B10-w5`
**Status:** ✅ **GO** — Codex r2 (`docs/superpowers/codex-sp1-review-r2.md`) returned GO-WITH-CHANGES; the last B11 wording change landed in commit `f2fc9626`. All 12 BLOCKs from r1 fixed, all 4 CONCERNs addressed. Plans rewritten on the actual-paths inventory at `docs/superpowers/sp1-actual-paths-inventory.md`. The originating session believes this is ready to execute — verify Codex r2 verdict yourself before starting.
**Created:** 2026-05-16 by the SP-0 → SP-1 brainstorm session.

---

## ✅ Ready to execute (Codex r2 GO)

**History:** Codex r1 returned NO-GO with 12 BLOCK + 4 CONCERN items because the original plan-writer drafted against imagined paths. The plans were rewritten using a verified-from-HEAD path inventory (`docs/superpowers/sp1-actual-paths-inventory.md`) and re-reviewed by Codex r2 (`docs/superpowers/codex-sp1-review-r2.md`) — verdict: GO-WITH-CHANGES, with the last B11 wording fix landed in commit `f2fc9626`.

**Fresh session must:**
1. Open this file (you already did).
2. Re-read `docs/superpowers/codex-sp1-review-r2.md` and confirm the GO verdict yourself.
3. Read `docs/superpowers/sp1-actual-paths-inventory.md` — the verified path/class/function reference. Trust it for paths the plans cite, but verify additions before extending.
4. Start with Plan A. Before any code, fire pre-execute Codex on Plan A (per Wave Control Ledger): `codex exec "Pre-execute review of SP-1 Plan A at docs/superpowers/plans/2026-05-16-sp1-plan-a-module-scaffold-inbox-spine.md. Identify any task that lacks an atomic commit unit or measurable gate criterion. Output GO/NO-GO."`

## Original NO-GO history (for context)

**Plans A-D were drafted against imagined code paths.** Executing as written will:
- Break alembic migrations against wrong model paths (`models/claims.py` does not exist; actual is `models/tables.py`)
- Audit non-existent backend routes (`/billing/batches`, `/billing/payment-runs`, etc.) and miss the real ones (`/api/v1/billing/payment-batches/*`, `/invoices/*`, `/settlement/record`)
- Reference non-existent ORM classes (`Batch`, `PaymentRun`, `Carryover`, `BankSettlement` — actual classes are `PaymentBatch`, `Payment`, `Invoice`, `InvoiceLineItem`)
- Call invented backend functions (`generate_nacha_file` — actual is `NACHAGenerator.generate(payments)`)
- Generate broken hash verification (Plan D's algorithm mismatches existing `compute_entry_hash` over tenant/action/entity/created_at/previous_hash)
- Skip mandatory project rules: PHI compliance (Plan B exposes `member_id` without `PHIMixin`), per-endpoint cross-tenant tests, `EventEnvelope` for `paysync.upload.parsed`, 99% branch coverage (plans say 95%)

**The fresh session should NOT execute Plan A.** Either:
1. **Re-dispatch the plan-writer** with strict drafter discipline (read every cited file with `git show HEAD:<path>` BEFORE writing; verify every class name; verify every route path; verify every function signature). The originating session left a re-dispatch prompt template at the bottom of this file (§8).
2. **Manually rewrite Plans A-D** against actual repo paths.
3. **Defer SP-1** until the originating session can re-shape the plans with the user.

The spec itself is broadly fine (broadly-covered intent). The 12 BLOCK items are almost entirely plan-level fabrications, not spec-level scope errors.

---

## 1. Artifacts

### Spec
- `docs/superpowers/specs/2026-05-16-sp1-paysync-operator-portal-design.md` (commit `5e8abf88`)

### Plans (5 sequential, A → E) — REWRITTEN against verified paths

The original plan commits (`e3ff11a1` Plan A, `ff8af128` Plan B, `0476fdd1` Plan C, `dea5fa57` Plan D, `25c70bd0` Plan E) had imagined paths and triggered Codex r1 NO-GO. They were rewritten as:

| Commit | Plan | Codex BLOCKs fixed |
|---|---|---|
| `e397e782` | `2026-05-16-sp1-plan-b-uploads-cycles.md` | B2 (`models/tables.py`), B7 (PHI on member_id), B8 (per-endpoint cross-tenant), B9 (EventEnvelope), B10 (99% coverage) |
| `365b94b0` | `2026-05-16-sp1-plan-c-batches-ar-ap.md` | B3 (real ORM names), B4 (real routes), B8, B10 |
| `a99b83bf` | `2026-05-16-sp1-plan-d-files-journal.md` | B5 (NACHA in payment-processing), B6 (`compute_entry_hash` kwargs), B8, B10 |
| `587724b1` | `2026-05-16-sp1-plan-a-module-scaffold-inbox-spine.md` | B1 (real shell paths), B10, B11 (no stub-as-done) |
| `dc861fbc` | `2026-05-16-sp1-plan-e-reports-setup-e2e.md` | B12 (echo/ wrap not delete), C4 (RoleSwitcherChip CI), B10 |
| `f2fc9626` | _r2 follow-up: B11 wording tightening + codex r2 review_ | B11 final |

### Codex reviews
- `docs/superpowers/codex-sp1-review-r1.md` — r1 NO-GO (12 BLOCK + 4 CONCERN). Historical.
- `docs/superpowers/codex-sp1-review-r2.md` — r2 GO-WITH-CHANGES. Effective verdict after `f2fc9626`: **GO**.
- `docs/superpowers/sp1-actual-paths-inventory.md` — verified inventory used in the rewrites. Trust it; verify additions before extending.

---

## 2. The 9 locked scope decisions (S1–S9)

| # | Decision | Choice |
|---|---|---|
| S1 | Vertical | PaySync operator portal |
| S2 | Workflow scope | Full (uploads → cycles → batches → AR/AP → NACHA/835 → settlement → journal → reports → setup) |
| S3 | Persona | All-in-one shared UI with RBAC gates |
| S4 | Integration depth | Portal/UI only — no external partner delivery, no 50-state backend gap-fill, `Upload` resource counts as wiring |
| S5 | Shippable bar | End-to-end round trip on synthetic non-PHI data against real backend |
| S6 | RBAC | 3 roles — Operator / Approver / Auditor with segregation-of-duties |
| S7 | IA | Inbox-first (queue + History + Journal + Reports + Setup) |
| S8 | Deployable shape | Module inside `portal/operator` only; standalone deferred |
| S9 | Upload provenance | NEW backend resource; immutable file artifact; claims permanently scoped to their upload |

---

## 3. Plan-time decisions resolved (spec §10)

| # | Answer (from plan-writer) |
|---|---|
| §10.1 | 5 plans A–E exactly as listed above |
| §10.2 | Upload storage: local disk `{PAYSYNC_UPLOAD_DIR}/{tenant_id}/{upload_id}/{filename}`; 90-day retention via nightly job; atomic write (.tmp rename) |
| §10.3 | CSV schema 8 mandatory cols: `ndc, npi, claim_id, date_of_service, quantity, days_supply, amount_billed, member_id`; `source_platform` optional; per-row errors never abort other rows |
| §10.4 | Hash-chain perf: ≤10k entries sync (<5s); above threshold returns `{verified: null, too_large: true}`; threshold via `PAYSYNC_HASH_CHAIN_SYNC_LIMIT` |
| §10.5 | Inbox cache: 10s polling + revalidate-on-focus + TanStack Query `staleTime: 10_000`; mutations `invalidateQueries` immediately; no WebSocket in SP-1 |
| §10.6 | Per-surface extraction as wired (Plans B/C/D/E); Plan A creates folder stubs only; original portal pages deleted in Plan E after E2E passes |

---

## 4. Open items the fresh session must address

1. **`echo/` route decision (user input needed).** `portal/operator/app/admin/paysync/echo/` is in the existing scaffolding but not mapped to any surface in spec §6.5. Plan E task 6 marks it "evaluate before deleting." Ask the user: debug route to remove, keep, or surface as dev tool?
2. **Codex review outcome.** `docs/superpowers/codex-sp1-review-r1.md` — read first; resolve every BLOCK before Plan A; address CONCERN items in-plan; NITs are optional.
3. **Backend Upload resource location.** Plan B places the new `Upload` table + router in `modules/billing/`. Confirm this is the right module (vs spinning a new ingestion module). Plan B notes this is a judgment call — verify before running alembic 0011.

---

## 5. Werkbench / project rules (non-negotiable)

- **Codex at every gate.** Spec consult ✓ (in flight). Pre-execute consult: required before Plan A starts. Gate-close consult: required at each plan completion. Per `framework/disciplines/wave-control-ledger.md` + `framework/disciplines/two-tool-layering.md`.
- **Co-Authored-By trailer on every commit:** `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
- **Decimal-only money.** Never `float`/`Float` in services, models, schemas, events that touch money. Per `.claude/rules/financial-precision.md`. Pre-commit hook enforces.
- **Zero PHI in test data.** Synthetic fixtures only. Per `.claude/rules/phi-compliance.md`.
- **JWT_SECRET ≥32 chars.** Per security rules.
- **TenantScopedMixin on every tenant-owned model.** `install_tenant_loader` on every session factory. Per `.claude/rules/tenant-isolation.md`.
- **EventEnvelope for all events.** Never raw `(topic, dict)`. Dot-notation event types. Per `.claude/rules/event-bus.md`.
- **Drafter discipline.** Before writing any code sample in a plan or commit message, run `git show HEAD:<file>` or read the actual file. SP-0 had multiple BLOCKED specs from imagined code.
- **Token discipline.** Use Write for skeletons + Edit for per-task additions. SP-0 hit the 32k output cap multiple times on mono-blocks.
- **Sync def + threadpool for FastAPI handlers** until full async migration lands. Per project status table in CLAUDE.md.
- **Test-first.** TDD for all core business logic (CLAUDE.md principle 11).
- **Coverage gates.** 100% on financial/PHI/security/auth paths; ≥99% branch elsewhere. Per `.claude/rules/testing.md`.

---

## 6. Handoff prompt for fresh session (copy-paste)

```
You are continuing work on the InfinityRx PBM platform, branch wave/B10-w5.
Your job is to execute SP-1 (PaySync Operator Portal) from the existing
spec + 5 plans.

START HERE — in this exact order:

1. Read docs/superpowers/SP-1-LAUNCH.md (this file). It is your single
   source of truth for what SP-1 is, what's locked, and what rules apply.

2. Read docs/superpowers/codex-sp1-review-r1.md (Codex's gate review of
   the spec + plans). If it does not exist yet, the codex review is still
   in flight from the originating session — wait or re-fire it via:
   codex exec "<re-fire prompt from this file's §1>"

3. Read the spec: docs/superpowers/specs/2026-05-16-sp1-paysync-operator-portal-design.md

4. Read CLAUDE.md (project root) + the .claude/rules/*.md files referenced
   in SP-1-LAUNCH.md §5. These are non-negotiable.

5. Confirm with the user: (a) the `echo/` route decision, (b) the
   Upload-resource-module placement (modules/billing/ vs new module),
   (c) any BLOCK items from the Codex review.

6. Read Plan A: docs/superpowers/plans/2026-05-16-sp1-plan-a-module-scaffold-inbox-spine.md

7. Re-fire Codex consult on Plan A specifically before any execution —
   Werkbench Wave Control Ledger requires pre-execute consult at the plan
   level too. Example: codex exec "Review Plan A for executability — is
   every task atomic, are gate criteria measurable, are referenced paths
   real? Output BLOCK/CONCERN/NIT."

8. Execute Plan A task-by-task, atomic commits, with the Co-Authored-By
   trailer. Run tests before each commit. Do not skip pre-commit hooks.

9. At Plan A completion: codex gate-close consult, then proceed to Plan B.

You have authorization to make decisions that best fit the InfinityRx PBM
business model. When in doubt, pick the option that respects the Werkbench
rules and the project rules in CLAUDE.md. If you must escalate, do so in
one sentence with the choices.

The originating session is brainstorming SP-2 (Directories Portal) in
parallel. Do not touch docs/superpowers/specs/*sp2* or
docs/superpowers/plans/*sp2* — those are owned by the other session.
```

---

## 8. Re-dispatch prompt for plan-writer (if rewriting plans)

If you choose to re-run the plan-writer to fix the BLOCK items, dispatch a general-purpose subagent with the prompt below. Stricter than the original — it MANDATES verifying every cited path before writing.

```
You are re-writing SP-1 plans A-D (B/C/D for sure; A possibly) to fix
Codex BLOCK findings in docs/superpowers/codex-sp1-review-r1.md.

HARD RULES — violation = restart:
1. Before writing ANY code sample, ORM class name, function call, route
   path, file path, or migration target, run ONE of:
     - git show HEAD:<path>
     - cat <path>
     - grep -n <symbol> <path>
   Confirm what's actually there. Do NOT trust the original plans —
   they hallucinated.
2. Before referencing any backend module name, class, or function, run
   the grep first. Example: `grep -n "class Payment" modules/billing/src/models/tables.py`.
3. Before referencing any route, run: `grep -rn "@router\.(get|post|put|delete)" modules/billing/src/api/`.
4. Before referencing the SP-0 shell contract, run: `ls packages/shell/src/` and read what's actually there. Plan A claimed `packages/shell/src/types/module-config.ts` exists — it does not.

Required corrections per Codex BLOCKs:
- B1: Verify or stub `packages/shell/src/types/module-config.ts` properly. Either build it or import what actually exists.
- B2: Replace `models/claims.py` references with actual path (`models/tables.py`).
- B3: Replace invented class names with actual: `PaymentBatch`, `Payment`, `Invoice`, `InvoiceLineItem`. Find what corresponds to "Carryover"/"BankSettlement"/"Reconciliation" or document that they need to be added.
- B4: Replace invented route paths with actual ones from grepping `modules/billing/src/api/`.
- B5: Replace `generate_nacha_file(batch_id)` with `NACHAGenerator.generate(payments)` (or whatever the real signature is — verify).
- B6: Plan D hash verifier must use `compute_entry_hash` over tenant/action/entity/created_at/previous_hash. Read `modules/core-platform/src/audit/hash_chain.py`.
- B7: PHI fields (member_id, etc.) must use PHIMixin + PHI access audit + masking. Per .claude/rules/phi-compliance.md. Add explicit route-level tests.
- B8: Tenant-isolation cross-tenant tests for EVERY API endpoint, not just uploads list. Per .claude/rules/tenant-isolation.md.
- B9: Every event needs EventEnvelope, ordering_key, idempotency_key, schema_version, idempotent_handler decorator, event-type docs. Per .claude/rules/event-bus.md.
- B10: Coverage gates: 100% financial/PHI/security/auth; 99% branch elsewhere (not 95%). Per .claude/rules/testing.md.
- B11: No stub files at gate; remove "create stub, count as done" tasks from Plan A.
- B12: Real disposition for portal/operator/app/admin/paysync/echo/ — what does it do? (Read its page.tsx + the Echo functions in paysync-api.ts.) Decide: keep, move, or remove. Document the choice in Plan E.

Output: Write each corrected plan to docs/superpowers/plans/2026-05-16-sp1-plan-{a,b,c,d,e}.md. Use Edit on existing files (preserve git history) where possible; full rewrite where the diff is too large. One commit per plan with message: "fix(sp-1): Plan X rewrite — address codex BLOCK items {N,M,...}".

After all rewrites: re-fire codex review:
codex exec "Re-review SP-1 plans against commits <new-shas>. Verify all 12 BLOCK items addressed. Output GO / NO-GO / GO-WITH-CHANGES."

Return a report listing every BLOCK addressed + which commit fixed it.
```

---

## 7. Cross-references

- SP-0 spec (foundation): `docs/superpowers/specs/2026-05-14-sp0-integration-foundation-design.md`
- SP-0 plans: `docs/superpowers/plans/2026-05-15-sp0-plan-*.md`
- Werkbench discipline: `~/Documents/Code Projects/Werkbench/framework/disciplines/wave-control-ledger.md`
- Werkbench tool layering: `~/Documents/Code Projects/Werkbench/framework/disciplines/two-tool-layering.md`
- Project rules: `.claude/rules/*.md`
- Existing PaySync scaffolding: `portal/operator/app/admin/paysync/`, `portal/operator/app/accounting/`, `portal/operator/app/billing/`, `portal/operator/app/payments/`, `portal/operator/components/paysync/`, `portal/shared/lib/paysync-api.ts`
- Existing backend: `modules/billing/src/services/{nacha,ap,ar,journal,remittance_835,claims}.py`, `modules/payment-processing/src/services/nacha_generator.py`, `modules/edi-compliance/src/x12/generators/gen_835.py`, `modules/core-platform/src/jobs/verify_audit_chain_job.py`
