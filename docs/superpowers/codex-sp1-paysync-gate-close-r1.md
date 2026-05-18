<!-- Trimmed from raw codex output (9238 lines, 652K) to the canonical final verdict block. -->
<!-- Codex CLI command: codex exec --enable web_search_cached "... GATE-CLOSE consult ..." -->
<!-- Captured: 2026-05-17 (session 10ace1bf-9cd7-443c-8225-15e8bc602a33) -->
<!-- Branch: wave/B10-w5-sp1-paysync at d1bc59d0 -->

# SP-1 PaySync Gate-Close Consult R1

**Overall Verdict: NO-GO**

SP-1 is not merge-ready into `wave/B10-w5`. The branch contains committed SP-2 work, active Plan-F stubs, missing Echo gate items from Plan E, deferred E2E execution, skipped tests, and unresolved tenant-isolation debt that directly violates project rules.

**BLOCKs**

1. SP-2 work is committed on the SP-1 merge candidate.
   The branch adds SP-2 plan files such as `docs/superpowers/plans/2026-05-17-sp2-plan-a-search-spine.md:1`, `docs/superpowers/plans/2026-05-17-sp2-plan-b-browse-clusters.md:1`, and `docs/superpowers/plans/2026-05-17-sp2-plan-e-e2e-fixtures.md:1`. This violates the consult requirement of no SP-2 file touches. These commits must be removed from the SP-1 branch before merge.

2. Plan E Echo gate did not land in code.
   Plan E requires adding `/admin/paysync/echo` to `module.config.ts`, adding `echo_run_status_received` to taxonomy/config, and adding `EchoRunStatusCard.tsx` with a unit test (`docs/superpowers/plans/2026-05-16-sp1-plan-e-reports-setup-e2e.md:294`, `:295`, `:328`, `:379`, `:380`). Actual code has only a static `EchoSurface` (`packages/modules/paysync/src/surfaces/echo/index.ts:12`) and the route/inbox config stops at setup and `journal_periodic_review` (`packages/modules/paysync/module.config.ts:25`, `:96`, `:107`, `:122`; `packages/modules/paysync/src/inbox/types.ts:18`, `:48`). No `EchoRunStatusCard` exists.

3. Active stubs/deferred code remain in merge-candidate paths.
   Project rules forbid committed stubs/dead code (`.claude/rules/code-standards.md:21`, `.claude/rules/testing.md:21`, `:22`, `:24`; `CLAUDE.md:140`, `:141`). The branch has live routers returning empty/404 stubs for bank settlements, reconciliations, and payment runs (`modules/billing/src/api/bank_settlements.py:7`, `:43`; `modules/billing/src/api/reconciliations.py:7`, `:43`; `modules/billing/src/api/payment_runs.py:7`, `:43`), a stub-only Echo client (`packages/contract/src/impls/paysync/echo-client.ts:10`, `:11`), and Plan-F TODO setup write handlers (`packages/modules/paysync/src/surfaces/setup/bff/setup.ts:4`, `:6`, `:24`).

4. TenantScopedMixin requirement is not met.
   Tenant rules require `TenantScopedMixin` on every tenant-owned model and `install_tenant_loader` on session factories (`.claude/rules/tenant-isolation.md:4`, `:6`). The acceptance doc explicitly defers this (`docs/sp-1-acceptance.md:124`). SP-1 tenant-owned models still inherit only `BillingBase`, including `PaymentBatch`, `Invoice`, `InvoiceLineItem`, `Carryover`, `Upload`, and `FileArtifact` (`modules/billing/src/models/tables.py:230`, `:354`, `:412`, `:500`, `:936`; `modules/billing/src/models/file_artifact.py:26`). The session file also documents that billing models “do not yet inherit the mixin” (`modules/billing/src/db/session.py:6`).

5. E2E acceptance is deferred/skippable, not gate-close evidence.
   Plan E required the 25-step E2E to pass (`docs/superpowers/plans/2026-05-16-sp1-plan-e-reports-setup-e2e.md:372`). The acceptance doc defers it as high-priority follow-up (`docs/sp-1-acceptance.md:126`). The Playwright spec skips unless `E2E_STACK_READY=true` (`portal/operator/tests/e2e/sp1-paysync-round-trip.spec.ts:27`, `:159`, `:228`, `:352`, `:439`). This is not a passing gate.

6. Test policy says zero skips, but committed tests include skips.
   `.claude/rules/testing.md:13` requires zero skips. Committed tests include explicit skips/import skips in SP-1-touched areas (`modules/billing/tests/test_seed.py:147`, `modules/billing/tests/integration/test_uploads_router.py:928`, `modules/billing/tests/unit/test_upload.py:365`, `modules/billing/tests/golden/test_golden_masters.py:87`, `:129`).

7. Coverage gate is not proven.
   Auto-Gate requires 100% on financial/PHI/security/auth and 99% branch coverage elsewhere (`CLAUDE.md:140`, `:141`). Acceptance lists pass counts and commands, but no coverage commands or reports (`docs/sp-1-acceptance.md:137`, `:138`, `:139`, `:147`, `:150`, `:153`, `:156`). Package test scripts are plain `vitest run` without coverage (`packages/modules/paysync/package.json:11`, `packages/contract/package.json:11`).

**CONCERNs**

1. Acceptance doc is stale relative to branch HEAD.
   It records final Task 6 commit `7326d268` (`docs/sp-1-acceptance.md:5`), but many SP-1 follow-up commits and all SP-2 commits landed after that. The test summary therefore is not final branch evidence.

2. Acceptance claims several high/medium deferred items that are merge-significant: QA harness extension, E2E, Plan-F ORM stubs, mutation clients, Echo RealImpl/MockImpl (`docs/sp-1-acceptance.md:125`, `:126`, `:127`, `:128`, `:129`).

3. Financial precision review found no direct `float`/`Float` money violation in the SP-1 billing additions. `amount_billed` is `Numeric(14, 4)` (`modules/billing/src/models/tables.py:72`), upload parsing uses `Decimal(str(value))` (`modules/billing/src/services/upload.py:118`), and response quantization uses `ROUND_HALF_UP` (`modules/billing/src/api/uploads.py:99`, `:101`). Keep this covered in the fix pass.

**NITs**

1. `.claude/rules/testing.md:7` still says 95% for non-critical code while `CLAUDE.md:140` and SP-1 plans use 99%. Harmonize the rule files to prevent future gate ambiguity.

2. The acceptance doc says “~350” billing tests (`docs/sp-1-acceptance.md:139`). Final gate docs should use exact pass/fail/skip counts from the final branch head.

**Coverage / Test Summary**

Documented evidence: paysync module 413 pass, contract 167 pass, billing ~350 pass (`docs/sp-1-acceptance.md:137`-`:139`). I did not find committed coverage reports proving the 100%/99% branch gates. I did find committed skip paths, and the E2E round trip is guarded to skip unless the full stack env var is set.

**Stragglers / Billing Touches**

The two non-prefixed stragglers are legitimately SP-1 scoped:
- `33ca1fd7 fix(billing)` touches upload/inbox SP-1 files only.
- `7d7c91a5 fix(contract)` changes `packages/contract/src/error-envelope.ts` to support duplicate-upload recovery.

The modules/billing changes are broadly in SP-1 scope for upload, inbox, cycles, RBAC, files, journal, seed, and tests. The issue is not scope creep in billing; the issue is merge readiness: tenant mixins are deferred and several active routers remain stubs.

**R2 B11 Verification**

R2’s requested wording fix landed in plan text. Plan A explicitly labels `src/bff/inbox.ts` as a stub and says real Inbox implementation is Plan B (`docs/superpowers/plans/2026-05-16-sp1-plan-a-module-scaffold-inbox-spine.md:354`, `:355`, `:691`). Plan E explicitly requires `EchoRunStatusCard.tsx` as a typed stub (`docs/superpowers/plans/2026-05-16-sp1-plan-e-reports-setup-e2e.md:380`). However, the execution did not satisfy the Plan E Echo gate in code.

**Final Recommendation**

Rework before merge. Remove SP-2 commits from this branch, complete or remove active stubs, satisfy the Echo gate, resolve TenantScopedMixin debt for SP-1 tenant-owned models, run non-skipped E2E, and produce final exact pass/fail/skip plus coverage evidence. Then re-run gate-close.
