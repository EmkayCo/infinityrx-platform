# SP-1 Plan E — Reports + Setup + End-to-End Round Trip

**Date:** 2026-05-16
**Sub-project:** SP-1 PaySync Operator Portal
**Status:** Ready for execution
**Depends on:** SP-1 Plan D (Files + Journal surfaces complete)

---

## Goal

Close SP-1. Deliver the two remaining surfaces (reports, setup), populate all fixture seed data
with real synthetic non-PHI content, execute the full end-to-end round trip on synthetic data,
remove original portal scaffolding that was copied-then-rewired in Plans B/C, and enforce the
production-bundle exclusion of `RoleSwitcherChip`. After Plan E, a fresh user can run the
qa-harness fixture seed, step through the complete Operator → Approver → Auditor workflow via
Playwright, and reach a green result at every gate.

---

## Scope

**In:**
- `surfaces/reports/` — rewire existing `portal/operator/app/accounting/cycles/`, `portal/operator/app/accounting/journal-entries/`, and period-report pages; `RbacGate` read-only for Auditor (all roles read); BFF handlers
- `surfaces/setup/` — rewire existing `portal/operator/app/admin/paysync/` setup surfaces (email-recipients, email-templates, export-templates, gl-account-mappings, invoice-sequences, cycle-schedules); all mutations `RbacGate role="approver"`; BFF handlers
- Contract: `ReportsClient`, `SetupClient` — interface + RealImpl + MockImpl
- `packages/modules/paysync/fixtures/` — all 3 CSV fixtures fully populated (20/20/30 rows); all 6 JSON seed files fully populated with real synthetic non-PHI data; `fixtures/seeds/tenant.json` with 1 demo tenant
- `packages/qa-harness` extension — PaySync fixture seed button, role-switcher chip wired, request inspector showing `paysync:*` cache tags
- Playwright E2E: `portal/operator/tests/e2e/sp1-paysync-round-trip.spec.ts` — full scenario per spec §9.1
- CI: production bundle check — assert `RoleSwitcherChip` absent from `.next/static/chunks/*.js`
- Delete original portal scaffolding that was copied (not moved) in Plans B/C: `portal/operator/app/admin/paysync/cycles/`, `portal/operator/app/admin/paysync/batches/`, `portal/operator/app/payments/batches/`, `portal/operator/app/admin/paysync/manual-ap/`, `portal/operator/app/accounting/invoices/`, `portal/operator/app/admin/paysync/carryovers/`, `portal/operator/app/admin/paysync/bank-settlements/`, `portal/operator/app/admin/paysync/reconciliations/`
- `infrastructure/manifests/operator-dev.yml` — final state: all `required_*` fields populated
- Module-level README: `packages/modules/paysync/README.md`

**Out:**
- Excel/PDF report rendering (spec §3 non-goal — deferred)
- 50-state compliance tables (spec §3 non-goal — deferred)
- Standalone PaySync deployable (spec §3 non-goal — deferred)
- External bank ACH submission (spec §3 non-goal — deferred)

---

## Tasks

### Task 1 — Reports surface

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 1.1 | Copy + rewire cycle reports | `surfaces/reports/CycleReportsPage.tsx` | RTL: renders, all-roles access | Wired |
| 1.2 | Copy + rewire journal-entry reports | `surfaces/reports/JournalEntriesReportPage.tsx` | RTL: renders | Wired |
| 1.3 | Period summary report page | `surfaces/reports/PeriodSummaryPage.tsx` | RTL: renders period selector, all amounts via `MoneyDisplay` | Wired |
| 1.4 | `ReportsClient` | `packages/contract/src/paysync/reports-client.ts` | — | RealImpl + MockImpl |
| 1.5 | BFF handlers | `surfaces/reports/bff/` | — | Route handlers |
| 1.6 | Update surface `index.ts` | `surfaces/reports/index.ts` | — | Surface wired |

**RBAC:** all roles can view reports (read-only surface). No mutating actions on reports surface.
Excel/PDF export button is present in the UI but renders as disabled with tooltip
"PDF/Excel export coming in a future release" — never hidden, per spec soft-disable convention.

**Performance:** per spec §9.4, reports are "honest first-paint + loading states" — no sub-150ms
requirement. Skeleton loaders shown while data fetches. No virtualisation required for reports
tables (typical row count < 200).

All monetary values in report tables use `MoneyDisplay`. Column totals computed server-side
(never client-side sum) and returned as `string` (Decimal).

- [ ] Step 1.1–1.3: Implement 3 report pages
- [ ] Step 1.4: Write `ReportsClient`
- [ ] Step 1.5: Write BFF handlers
- [ ] Step 1.6: Update `surfaces/reports/index.ts`
- [ ] Step 1.7: RTL tests
- [ ] Step 1.8: Commit — `feat(sp-1-e): reports surface — cycle, journal, period-summary wired`

---

### Task 2 — Setup surface

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 2.1 | Email recipients page | `surfaces/setup/EmailRecipientsPage.tsx` | RTL: Approver can save; Operator sees disabled save | Wired |
| 2.2 | Email templates page | `surfaces/setup/EmailTemplatesPage.tsx` | RTL: Approver mutate; Auditor read-only | Wired |
| 2.3 | Export templates page | `surfaces/setup/ExportTemplatesPage.tsx` | RTL | Wired |
| 2.4 | GL account mappings page | `surfaces/setup/GlAccountMappingsPage.tsx` | RTL: Approver-only save | Wired |
| 2.5 | Invoice sequences page | `surfaces/setup/InvoiceSequencesPage.tsx` | RTL | Wired |
| 2.6 | Cycle schedules page | `surfaces/setup/CycleSchedulesPage.tsx` | RTL | Wired |
| 2.7 | `SetupClient` | `packages/contract/src/paysync/setup-client.ts` | — | RealImpl + MockImpl |
| 2.8 | BFF handlers | `surfaces/setup/bff/` | — | Route handlers |

**RBAC:** all setup mutations are Approver-only per spec §5.4. `RbacGate role="approver"` on
every save/create/delete button. Auditor and Operator see the forms read-only.

**Backend RBAC verification:** confirm that `portal/operator/app/admin/paysync/` setup endpoints
(email-recipients, export-templates, gl-account-mappings, invoice-sequences, cycle-schedules) are
all Approver-gated at the billing backend. If any are missing role enforcement, add in this task
(same pattern as Plan C Task 2).

- [ ] Step 2.1–2.6: Implement 6 setup pages
- [ ] Step 2.7: Write `SetupClient`
- [ ] Step 2.8: Write BFF handlers
- [ ] Step 2.9: Verify + gap-fill backend RBAC on setup endpoints
- [ ] Step 2.10: RTL tests
- [ ] Step 2.11: Commit — `feat(sp-1-e): setup surface — 6 pages, Approver-only mutations`

---

### Task 3 — Fixture data population

Populate all fixture files with real synthetic non-PHI data per spec §9.3. All data is
demonstrably non-PHI: synthetic names from a public test-data corpus, synthetic NPIs (80840 +
Luhn-valid invented suffix), synthetic NDCs (11 digits, well-formed), no real member identifiers.

| File | Target content |
|---|---|
| `fixtures/uploads/upload-001-healthy.csv` | 20 rows, all 8 required columns valid; 2 different `source_platform` values to test that field |
| `fixtures/uploads/upload-002-validation-fail.csv` | 20 rows; 10 with bad NDC (wrong length), 5 with bad date format, 5 with negative `amount_billed` |
| `fixtures/uploads/upload-003-half-bad.csv` | 30 rows; 10 with NDC `0000000000` (fails 11-digit check), 20 valid |
| `fixtures/seeds/tenant.json` | 1 tenant: `{id, name: "Acme Health Plan (Demo)", created_at}` |
| `fixtures/seeds/users.json` | 3 users: `alice_operator`, `bob_approver`, `carol_auditor`; synthetic emails; no real data |
| `fixtures/seeds/cycles.json` | 5 cycles: 2 open, 1 closing (awaiting Approver close-review), 1 closed, 1 error |
| `fixtures/seeds/invoices.json` | 10 invoices; amounts as Decimal strings; 3 draft (Approver Inbox items), 4 sent, 3 paid |
| `fixtures/seeds/payment-runs.json` | 5 runs; 2 held (Approver Inbox), 2 released, 1 settled |
| `fixtures/seeds/reconciliations.json` | 1 reconciliation with `discrepancy_amount: "12.34"` (string Decimal); status `pending` |

**PHI compliance check:** before committing, verify no field in any fixture file contains a real
NPI (prefix must be 80840 or other synthetic prefix, not a real issuer), real NDC, real member
name, or real address. Per `.claude/rules/phi-compliance.md`.

- [ ] Step 3.1: Write all 3 CSV files with real synthetic rows
- [ ] Step 3.2: Write all 6 JSON seed files
- [ ] Step 3.3: PHI compliance check (manual review + grep for real NPI prefixes other than 80840)
- [ ] Step 3.4: Commit — `feat(sp-1-e): fixture data — 3 CSVs + 6 JSON seeds, demonstrably non-PHI`

---

### Task 4 — QA-harness extension

Extend `packages/qa-harness` with PaySync-specific dev tooling per spec §9.1.

| # | Subject | Files | Deliverable |
|---|---|---|---|
| 4.1 | PaySync fixture seed button | `packages/qa-harness/src/seeds/paysync-seed.ts` | Button in qa-harness UI that POSTs fixture data to backend seed endpoint |
| 4.2 | `RoleSwitcherChip` wired | re-exported from qa-harness; consumed by module's `qa.RoleSwitcherChip` dynamic import | Role toggle functional in dev/staging |
| 4.3 | Request inspector cache-tag overlay | `packages/qa-harness/src/inspector/` | Shows `paysync:uploads`, `paysync:cycles`, etc. cache tags on each request |
| 4.4 | Backend seed endpoint | `modules/billing/src/api/seed.py` | `POST /api/v1/billing/seed` (dev/staging only; blocked in production by `INFINITYRX_ENV` check) |

**Production guard on seed endpoint:** the seed endpoint MUST check `settings.env != 'production'`
and return 403 if in production. The qa-harness seed button is excluded from production builds
via the same tree-shaking mechanism as `RoleSwitcherChip`.

**`RoleSwitcherChip` production exclusion CI check** (spec §6.6 + CONCERN fix):
The check must prove not just that `RoleSwitcherChip` string is absent, but also that the
`qa-harness` module's exports are unreachable from production bundle entry points (tree-shaking
is working, not just that the string was renamed/minified). Add TWO steps:

```yaml
- name: Check RoleSwitcherChip absent from production bundle
  run: |
    if grep -r "RoleSwitcherChip" portal/operator/.next/static/chunks/ 2>/dev/null; then
      echo "FATAL: RoleSwitcherChip found in production bundle"
      exit 1
    fi
    echo "RoleSwitcherChip absent from production bundle — OK"

- name: Check qa-harness exports unreachable from production chunks
  run: |
    # Verify no production chunk imports from @infinityrx/qa-harness
    # (checks the bundle manifest, not just string presence)
    if node -e "
      const manifest = require('./portal/operator/.next/build-manifest.json');
      const chunks = Object.values(manifest.pages).flat();
      const fs = require('fs');
      let found = false;
      chunks.forEach(chunk => {
        const path = './portal/operator/.next/static/' + chunk;
        try {
          const content = fs.readFileSync(path, 'utf8');
          if (content.includes('qa-harness') || content.includes('RoleSwitcher')) {
            console.error('FATAL: qa-harness reference in chunk:', chunk);
            found = true;
          }
        } catch(e) {}
      });
      process.exit(found ? 1 : 0);
    "; then
      echo "qa-harness exports unreachable from production chunks — OK"
    else
      exit 1
    fi
```

Both steps run after `next build` in the CI workflow. The second step checks the build manifest
to enumerate actual production chunks — this catches cases where tree-shaking fails silently
(e.g., the string `RoleSwitcherChip` was minified to `r` but the qa-harness module is still
bundled).

- [ ] Step 4.1: Write `paysync-seed.ts` + backend seed endpoint
- [ ] Step 4.2: Wire `RoleSwitcherChip` through qa-harness re-export
- [ ] Step 4.3: Add request inspector cache-tag overlay for paysync tags
- [ ] Step 4.4: Add `RoleSwitcherChip` production-bundle CI check
- [ ] Step 4.5: Integration test: seed endpoint returns 403 when `INFINITYRX_ENV=production`
- [ ] Step 4.6: Commit — `feat(sp-1-e): qa-harness PaySync seed button + role switcher + bundle check`

---

### Task 5 — Playwright E2E round trip

**File:** `portal/operator/tests/e2e/sp1-paysync-round-trip.spec.ts`

Full scenario per spec §7.1 + §9.1. Runs against full docker-compose stack with real backends.

```
Scenario: Full PaySync round trip on synthetic data

  As Operator (alice_operator):
    1. Navigate to /admin/paysync (Inbox — empty at start)
    2. Go to Uploads → drag-drop upload-001-healthy.csv
    3. Assert: upload appears in list with status "parsing" → "validated"
    4. Assert: Inbox shows "upload_validated_awaiting_batching" item
    5. Click Inbox item → UploadDetailPage → 20 claims visible
    6. Create draft batch from upload → BatchDetailPage
    7. Assert: ProvenanceBreadcrumb shows "Upload #N → Cycle ... → Batch B-XXXX"

  As Approver (bob_approver):
    8. Open Inbox → "batch_drafted" item visible
    9. Navigate to Cycles → close the current cycle (cycle_close_review flow)
    10. Navigate to Invoices → send the draft invoice (ar_invoice_draft flow)
       - Assert: MoneyDisplay shows amount in USD format
       - Assert: send button requires explicit confirm step
    11. Navigate to Payment Runs → release the held payment run
    12. Navigate to Files → generate NACHA file for batch
       - Assert: NACHA artifact appears in list with download link
    13. Generate 835 file for payment run
       - Assert: 835 artifact appears; ProvenanceTrace shows Upload → Cycle → Batch → File
    14. Download NACHA file → assert non-empty bytes received
    15. Navigate to Reconciliations → finalize the reconciliation

  As Auditor (carol_auditor):
    16. Open Inbox → "journal_periodic_review" item visible
    17. Navigate to Journal → JournalLedgerView shows entries
    18. Click HashChainVerifierPanel → trigger verify
    19. Assert: badge shows green "Chain intact — N entries verified"
    20. Assert: generate button is disabled with tooltip "Approver role required"
    21. Navigate to Files → all files visible; download works; generate button disabled
    22. Navigate to Reports → all report pages render; no errors

  Final assertions:
    23. Upload #N ProvenanceBreadcrumb appears on: UploadDetailPage, BatchDetailPage,
        InvoiceDetailPage, PaymentRunDetailPage, FilesListPage (ProvenanceTrace), JournalEntryDetail
    24. RoleSwitcherChip NOT present in page source (production build)
    25. All Inbox items cleared (or in correct terminal state) after workflow completes
```

**E2E infrastructure requirements:**
- docker-compose stack with postgres + redis + rabbitmq + all backend modules
- Fixture seed runs before test via `beforeAll` calling the qa-harness seed endpoint
- Playwright `page.waitForSelector` on upload status badge transitions (async backend parsing)
- Test uses `page.route()` to intercept download and assert non-empty response body
- Roles switched by logging out + logging in as the next user (not via `RoleSwitcherChip` in
  production build; in E2E test mode, a test-auth shortcut endpoint issues JWTs for fixture users)

**Test-auth shortcut endpoint** (E2E-only):
`POST /api/v1/core/test-auth/token` — accepts `{user_id}`, returns JWT for fixture user.
Guarded by `INFINITYRX_ENV in ('development', 'mock')` — blocked in production. Same pattern
as seed endpoint.

- [ ] Step 5.1: Write test-auth shortcut endpoint (`modules/core-platform/src/api/test_auth.py`)
- [ ] Step 5.2: Write `portal/operator/tests/e2e/sp1-paysync-round-trip.spec.ts` with full 25-step scenario
- [ ] Step 5.3: Run E2E against docker-compose stack — all 25 assertions pass
- [ ] Step 5.4: Add E2E workflow to `.github/workflows/sp1-paysync.yml` (runs on push to `wave/` branches)
- [ ] Step 5.5: Commit — `feat(sp-1-e): Playwright E2E round trip — 25-step Operator→Approver→Auditor scenario`

---

### Task 6 — Cleanup: delete copied portal scaffolding + wrap echo/ surface

Now that module surfaces are wired and E2E confirms they work, delete the original portal pages
that were copied (not moved) in Plans B and C. Also wrap the `echo/` surface (B12 fix).

**echo/ surface disposition (B12 fix — KEEP and wrap):**
`portal/operator/app/admin/paysync/echo/page.tsx` is REAL operational functionality — the
Echo Spec 400 operations page (Wave 41 M6). It lists Spec 400 runs with status, totals,
sha256 hashes; provides a manual-trigger button for the daily candor pipeline; surfaces recent
status file ingestions. It is NOT a debug route and must NOT be deleted.

Plan E wraps it into the module:
- Create `packages/modules/paysync/src/surfaces/echo/index.ts` — surface stub (Plan A's
  surface-13, missed in original scope)
- Create `packages/modules/paysync/src/surfaces/echo/EchoSpecPage.tsx` — wraps the existing
  page logic; replaces direct `paysync-api.ts` imports with `EchoClient` from contract layer
- Add `EchoClient` to `packages/contract/src/paysync/echo-client.ts` — wraps
  `listEchoRuns()`, `listEchoIngestions()`, `runEchoCandor()` from `portal/shared/lib/paysync-api.ts`
  (real functions confirmed in inventory §9)
- Add `echo/` route to `module.config.ts` routes table:
  `{ path: '/admin/paysync/echo', surface: 'echo', label: 'Echo Spec 400' }`
- Add Inbox item kind `echo_run_status_received` for echo run status changes:
  - Add to `InboxItemKind` union in `src/inbox/types.ts`
  - Add to `INBOX_KIND_ROLE` map: `echo_run_status_received: 'approver'`
  - Add `EchoRunStatusCard.tsx` stub (Plan D/E fills real implementation)
  - Add to `module.config.ts` `inboxItemKinds` array
- Backend paysync-api base path: check `portal/shared/lib/paysync-api.ts` for `PAYSYNC_BASE`
  to find the existing base URL (inventory §10 CONCERN: may point at adjudication-engine
  `/admin/paysync`). Document migration path in `EchoClient` comments.

**Portal pages to delete** (9 paths confirmed copied-not-moved in Plans B/C):

| Path to delete | Replaced by |
|---|---|
| `portal/operator/app/admin/paysync/cycles/` | `packages/modules/paysync/src/surfaces/cycles/` |
| `portal/operator/app/admin/paysync/batches/` | `packages/modules/paysync/src/surfaces/batches/` |
| `portal/operator/app/admin/paysync/carryovers/` | `packages/modules/paysync/src/surfaces/carryovers/` |
| `portal/operator/app/admin/paysync/bank-settlements/` | `packages/modules/paysync/src/surfaces/bank-settlements/` |
| `portal/operator/app/admin/paysync/reconciliations/` | `packages/modules/paysync/src/surfaces/reconciliations/` |
| `portal/operator/app/admin/paysync/invoices/` | `packages/modules/paysync/src/surfaces/invoices/` |
| `portal/operator/app/accounting/invoices/` | `packages/modules/paysync/src/surfaces/invoices/` |
| `portal/operator/app/payments/batches/` | `packages/modules/paysync/src/surfaces/payment-runs/` |
| `portal/operator/app/admin/paysync/manual-ap/` | `packages/modules/paysync/src/surfaces/payment-runs/ManualApForm.tsx` |

**DO NOT delete:**
- `portal/operator/app/admin/paysync/page.tsx` — top-level paysync route; redirects to Inbox
- `portal/operator/app/admin/paysync/echo/` — KEPT; now mirrored by module surface (delete original only after E2E step 6.4 confirms module route works end-to-end)
- `portal/operator/app/admin/paysync/invoice-sequences/`, `cycle-schedules/`, `email-*/`, `export-templates/`, `gl-account-mappings/` — delete only after Task 2 confirms rewired

**After deletion:** run `npm run build` (portal) and `npm run typecheck` — confirm no broken
imports referencing deleted paths. Fix any remaining cross-references.

- [ ] Step 6.0: Create `packages/modules/paysync/src/surfaces/echo/` surface with `EchoSpecPage.tsx` wrapping existing page logic via `EchoClient`
- [ ] Step 6.0b: Add `EchoClient` to `packages/contract/src/paysync/echo-client.ts` wrapping `listEchoRuns`, `listEchoIngestions`, `runEchoCandor`
- [ ] Step 6.0c: Add `echo_run_status_received` to `InboxItemKind`, `INBOX_KIND_ROLE`, `module.config.ts`, and `EchoRunStatusCard.tsx`
- [ ] Step 6.0d: Add echo route to `module.config.ts` routes table
- [ ] Step 6.0e: `grep -n "PAYSYNC_BASE\|baseURL\|API_BASE" portal/shared/lib/paysync-api.ts` — document base URL in `EchoClient` comments
- [ ] Step 6.1: Delete all 9 copied surface directories listed above
- [ ] Step 6.2: Delete setup directories if rewired in Task 2
- [ ] Step 6.3: Run `npm run typecheck` + `npm run build` (portal) — clean
- [ ] Step 6.4: Run E2E again to confirm no regressions after deletion (including echo/ surface accessible via module route)
- [ ] Step 6.5: Delete `portal/operator/app/admin/paysync/echo/` only after Step 6.4 confirms module route works
- [ ] Step 6.6: Commit — `feat(sp-1-e): wrap echo/ into module surface + delete copied portal scaffolding`

---

### Task 7 — Final manifest + module README + acceptance doc

**`infrastructure/manifests/operator-dev.yml`** — final state:
- `modules: [paysync]`
- `required_backends: [billing, payment-processing, edi-compliance, core-platform]`
- `required_jobs: [paysync.cleanup_old_uploads, core.audit_chain_verify, core.session_reaper]`
- `required_env: [JWT_SECRET, NEXTAUTH_SECRET, INFINITYRX_ENV, PAYSYNC_UPLOAD_DIR, PAYSYNC_HASH_CHAIN_SYNC_LIMIT]`
- `required_buckets: []` (local disk in SP-1; S3 deferred)
- All other `required_*` arrays fully populated from what Plans A–E added

**`packages/modules/paysync/README.md`** — per project Module layer doc discipline (CLAUDE.md §5):
- WHAT: PaySync is the financial-processing module for the InfinityRx operator portal — uploads, cycles, AR/AP, NACHA/835, journal, reports, setup.
- WHY separate module: composition isolation (SD-4); RBAC boundary; independently testable.
- HOW: entry point is `module.config.ts`; routes registered via SP-0 shell; BFF handlers under `src/bff/`; backend via `packages/contract` clients; fixtures under `fixtures/`; run tests with `npm --workspace=@infinityrx/module-paysync test`.

**Acceptance doc:** `docs/superpowers/plans/2026-05-16-sp1-plan-e-status.md` — same format as
`2026-05-15-sp0-plan-a-status.md`. Records final commit SHA, all verification commands and
their results, what was shipped, what is explicitly deferred.

- [ ] Step 7.1: Update `infrastructure/manifests/operator-dev.yml` to final state
- [ ] Step 7.2: Run `npm run manifest:validate` — passes
- [ ] Step 7.3: Write `packages/modules/paysync/README.md`
- [ ] Step 7.4: Write `docs/superpowers/plans/2026-05-16-sp1-plan-e-status.md`
- [ ] Step 7.5: Commit — `docs(sp-1-e): final manifest, module README, SP-1 acceptance status`

---

## Gate Criteria

Plan E is complete when ALL of the following are true:

- [ ] E2E: all 25 steps of `sp1-paysync-round-trip.spec.ts` pass against docker-compose stack
- [ ] `npm --workspace=@infinityrx/module-paysync test` passes; 100% coverage on all financial (MoneyDisplay/Input, all Decimal paths), PHI (tenant isolation, access logging), security (RBAC on every surface); **≥99% branch coverage** on all other module code (CLAUDE.md Auto-Gate)
- [ ] `modules/billing` full suite passes; 100% on seed endpoint production-guard path
- [ ] `modules/core-platform` full suite passes; 100% on test-auth endpoint production-guard path
- [ ] `npm run typecheck` clean across workspace
- [ ] `npm run manifest:validate` passes with final `operator-dev.yml`
- [ ] Production-bundle check CI step: no `RoleSwitcherChip` string in `.next/static/chunks/`
- [ ] qa-harness exports unreachable CI step: build-manifest.json scan confirms no production chunk references `qa-harness` or `RoleSwitcher` (catches tree-shaking failures not caught by string grep alone)
- [ ] echo/ surface wrapped into `packages/modules/paysync/src/surfaces/echo/` with `EchoClient`; `echo_run_status_received` Inbox kind added to taxonomy + INBOX_KIND_ROLE + module.config.ts
- [ ] `EchoRunStatusCard.tsx` exists as a typed stub (accepts `item: InboxItem` prop, renders `<div data-testid="inbox-card-echo_run_status_received">{item.kind}</div>`, has a unit test); real implementation deferred to follow-on sprint — gate does NOT require full implementation, only that it is type-safe and not empty
- [ ] E2E step added for echo/ surface: navigate to `/admin/paysync/echo` via module route → page renders Echo Spec 400 runs table
- [ ] All 9 original portal surface directories deleted; no broken imports
- [ ] `portal/operator/app/admin/paysync/echo/` deleted only AFTER E2E confirms module route functional
- [ ] `packages/modules/paysync/README.md` exists and covers WHAT/WHY/HOW
- [ ] `fixtures/uploads/upload-001-healthy.csv` has 20 data rows (not header-only)
- [ ] `fixtures/seeds/invoices.json` has 10 invoices with amounts as strings
- [ ] Seed endpoint returns 403 on `INFINITYRX_ENV=production`
- [ ] Test-auth endpoint returns 403 on `INFINITYRX_ENV=production`
- [ ] Reconciliation fixture has `discrepancy_amount` as string (Decimal), not number
- [ ] All amounts in all fixture JSON files are strings — grep confirms no bare `number` type for money fields
- [ ] `docs/superpowers/plans/2026-05-16-sp1-plan-e-status.md` exists with final SHA + verification table

---

## Deliverables

- Reports and setup surfaces — full left-nav functional, all 13 routes wired
- All fixture data populated — E2E can seed and run without manual setup
- QA-harness PaySync fixture seed button + role-switcher chip + cache-tag inspector
- Full 25-step Playwright E2E passing against real backends
- Production bundle guard — `RoleSwitcherChip` CI check enforced
- Cleaned-up portal — original scaffolding deleted, no dead code
- SP-1 acceptance status doc — formal record of what shipped and what is deferred

---

## Dependencies

- SP-1 Plans A–D all complete (all 13 surfaces have at least stubs; all backends wired)
- docker-compose stack with all 4 backends healthy (billing, payment-processing, edi-compliance, core-platform)
- Playwright installed in portal (`@playwright/test` — check `portal/operator/package.json`)
- `packages/qa-harness` accepts new seed contributions (SP-0 Plan C/D)
- `INFINITYRX_ENV` env var available to all backend modules (confirmed in CLAUDE.md environment architecture)

---

## Cross-references

- Spec §2 (Goal 6 — E2E round trip on synthetic data = the shippable bar for SP-1), §3 (non-goals explicitly deferred: no PDF/Excel, no 50-state tables, no standalone deployable, no external ACH/clearinghouse), §6.5 (wrapping existing surfaces — reports/setup), §6.6 (RoleSwitcherChip production exclusion), §9.1 (E2E test layer spec), §9.3 (fixture data spec), §9.4 (performance posture)
- Rules: `.claude/rules/phi-compliance.md` (fixture data demonstrably non-PHI; no PHI in seed endpoint responses), `.claude/rules/financial-precision.md` (all fixture money fields as strings), `.claude/rules/security.md` (seed + test-auth endpoints blocked in production), `.claude/rules/testing.md` (100% financial/PHI/security; zero failures; dead-code scanner), `.claude/rules/code-standards.md` (no dead code — delete original scaffolding)
- CLAUDE.md §5 (Module layer doc discipline — README required before commit)
- CLAUDE.md (Continuous Learning — lessons-learned.md update if non-obvious bugs hit during E2E)
- SP-1 Plan D: `docs/superpowers/plans/2026-05-16-sp1-plan-d-files-journal.md`
- SP-0 Plan A status: `docs/superpowers/plans/2026-05-15-sp0-plan-a-status.md` (format reference for acceptance doc)
