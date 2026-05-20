# SP-1 PaySync — Deferred Follow-ups (Ship-with-Gaps)

**Date:** 2026-05-18
**Branch:** `wave/B10-w5-sp1-paysync`
**Codex gate-close consult:** `docs/superpowers/codex-sp1-paysync-gate-close-r1.md` — verdict **NO-GO** with 7 BLOCKs
**Decision (operator):** ship with documented gaps; deferred items tracked here for follow-up sprints.
**Acceptance doc cross-reference:** `docs/sp-1-acceptance.md` (Final Task 6 commit `7326d268`, stale relative to current HEAD `d1bc59d0`)

---

## Resolution status of codex gate-close BLOCKs

| # | BLOCK | Status | Notes |
|---|---|---|---|
| B1 | SP-2 commits on SP-1 merge candidate | **RESOLVED** | Reorganized via clean cherry-pick to `wave/B10-w5-sp2-integration`. SP-2 merged independently to `wave/B10-w5` at commit `2207e945`. |
| B2 | Plan E Echo gate not landed in code | **DEFERRED** | See F1 below. |
| B3 | Active stubs in shipped routes | **DEFERRED** | See F2 below. |
| B4 | TenantScopedMixin missing on tenant-owned models | **DEFERRED** | See F3 below. |
| B5 | E2E spec skipped unless `E2E_STACK_READY=true` | **DEFERRED** | See F4 below. SP-2 Plan E explicitly avoided this anti-pattern as its own gate condition. |
| B6 | Committed tests include explicit skips (5 files) | **DEFERRED** | See F5 below. |
| B7 | Coverage gate not proven (no coverage reports) | **DEFERRED** | See F6 below. |

---

## Follow-up backlog

### F1 — Plan E Echo gate (severity: high)

**What's missing:**
- `/admin/paysync/echo` route in `packages/modules/paysync/module.config.ts`
- `echo_run_status_received` kind in inbox taxonomy (`packages/modules/paysync/src/inbox/types.ts`)
- `EchoRunStatusCard.tsx` typed component with unit test

**Current state:** static `EchoSurface` (`packages/modules/paysync/src/surfaces/echo/index.ts:12`) only. Route + inbox config stops at setup and `journal_periodic_review`.

**Plan reference:** `docs/superpowers/plans/2026-05-16-sp1-plan-e-reports-setup-e2e.md:294,295,328,379,380`

**Target ship-after:** before next operator-portal customer demo OR before Echo backend integration goes live, whichever first.

### F2 — Active stubs in shipped routes (severity: high)

**Files returning empty/404 stubs in production paths:**
- `modules/billing/src/api/bank_settlements.py:7,43` — bank settlements router
- `modules/billing/src/api/reconciliations.py:7,43` — reconciliations router
- `modules/billing/src/api/payment_runs.py:7,43` — payment runs router
- `packages/contract/src/impls/paysync/echo-client.ts:10,11` — Echo client (stub-only)
- `packages/modules/paysync/src/surfaces/setup/bff/setup.ts:4,6,24` — Plan-F TODO setup write handlers

**Rule violated:** `.claude/rules/code-standards.md:21`, `.claude/rules/testing.md:21,22,24`, `CLAUDE.md:140,141` — no committed stubs/dead code.

**Disposition:** either implement (Plan-F territory) or remove route mounts and surface "Not implemented" banner. Coordinator recommends remove-then-reimplement to avoid producing 404s on live paths.

**Target ship-after:** before next external integration that calls these endpoints.

### F3 — TenantScopedMixin debt (severity: high)

**Tenant-owned models that inherit only `BillingBase` (missing `TenantScopedMixin`):**
- `PaymentBatch` (`modules/billing/src/models/tables.py:230`)
- `Invoice` (`modules/billing/src/models/tables.py:354`)
- `InvoiceLineItem` (`modules/billing/src/models/tables.py:412`)
- `Carryover` (`modules/billing/src/models/tables.py:500`)
- `Upload` (`modules/billing/src/models/tables.py:936`)
- `FileArtifact` (`modules/billing/src/models/file_artifact.py:26`)

**Session file documents the gap:** `modules/billing/src/db/session.py:6` — "billing models do not yet inherit the mixin"
**Acceptance doc explicitly defers:** `docs/sp-1-acceptance.md:124`
**Rule violated:** `.claude/rules/tenant-isolation.md:4,6`

**Mitigation in place:** billing relies on PostgreSQL RLS (Row-Level Security) policies as the defense-in-depth layer per `fix(sp-1-b-B4): document billing RLS-only tenant isolation pattern for Upload`. RLS is enforced at the database session level, not the ORM level — application code that bypasses the session (rare) would bypass isolation.

**Target ship-after:** before SP-1 is used with more than one tenant in any environment OR before any change to billing models that introduces a new query path that doesn't route through the RLS-enforced session.

### F4 — E2E spec skip-by-default (severity: medium)

**Spec:** `portal/operator/tests/e2e/sp1-paysync-round-trip.spec.ts:27,159,228,352,439`
**Skip mechanism:** `E2E_STACK_READY=true` env var required for tests to execute.

**Why this was flagged:** test policy (`.claude/rules/testing.md:13`) requires zero skips. SP-2 Plan E gate-close explicitly avoided this anti-pattern (its E2E spec runs without env-gate via mock servers + `fetchViaPage` pattern).

**Disposition options:**
- Apply SP-2 Plan E's pattern to SP-1 paysync E2E (mock servers + same-origin fetch via `page.evaluate`)
- OR mark E2E as `test.fixme` with linked tracking issue (still doesn't run, but is honest about the state)

**Target ship-after:** before SP-1 is positioned as having E2E coverage in any external documentation.

### F5 — Explicit test skips (severity: medium)

**Files with committed `skip`/`importorskip`:**
- `modules/billing/tests/test_seed.py:147`
- `modules/billing/tests/integration/test_uploads_router.py:928`
- `modules/billing/tests/unit/test_upload.py:365`
- `modules/billing/tests/golden/test_golden_masters.py:87,129`

**Rule violated:** `.claude/rules/testing.md:13` — zero skips.

**Disposition:** triage each skip — convert to either (a) passing test, (b) `xfail` with linked issue, or (c) deletion if scope-removed. The golden-master skips likely indicate fixture-generation gaps; the upload/seed skips may be intentional integration-only scoping.

**Target ship-after:** next sprint after SP-1 ships — testing-debt cleanup pass.

### F6 — Coverage gate unproven (severity: medium)

**Auto-Gate requirement:** 100% on financial/PHI/security/auth, 99% branch coverage elsewhere (`CLAUDE.md:140,141`).
**Current state:** acceptance doc lists pass counts but no coverage reports. Package test scripts are plain `vitest run` without `--coverage`:
- `packages/modules/paysync/package.json:11`
- `packages/contract/package.json:11`

**Disposition:** add `--coverage` to package test scripts; wire coverage reporters; produce evidence on next CI run.

**Target ship-after:** before next claim of SP-1 ready-for-production OR before next release gate that requires coverage proof.

---

## Concerns (codex non-blocking findings)

| # | Concern | Status |
|---|---|---|
| C1 | Acceptance doc stale relative to branch HEAD | Documented here. `docs/sp-1-acceptance.md` was written at `7326d268`; current HEAD `d1bc59d0` includes ~15+ subsequent commits not reflected in pass-count totals. |
| C2 | Acceptance doc claims high/medium deferred items | Items overlap with F-followups above. Treat this doc as the canonical list. |
| C3 | Financial precision passed cleanly | No action — Decimal usage verified (`amount_billed=Numeric(14,4)`, `Decimal(str(value))` parsing, `ROUND_HALF_UP` on quantize). |

---

## NITs (nice-to-have)

| # | NIT | Status |
|---|---|---|
| N1 | `.claude/rules/testing.md:7` says 95% non-critical coverage; `CLAUDE.md:140` and SP-1 plans say 99% | Drift between rule files. Pick one (recommend 99% per CLAUDE.md). |
| N2 | Acceptance doc says "~350" billing tests | Should be exact pass/fail/skip count from final branch HEAD. |

---

## Cross-references

- **Codex gate-close artifact:** `docs/superpowers/codex-sp1-paysync-gate-close-r1.md` (raw consult output, 9238 lines)
- **SP-1 acceptance document:** `docs/sp-1-acceptance.md` (executor's report, stale at `7326d268`)
- **SP-1 launch packet:** `docs/superpowers/SP-1-LAUNCH.md`
- **SP-2 acceptance document** (sister vertical, fully gate-closed): `docs/sp-2-acceptance.md`
- **Codex SP-2 Plan E gate verdict** (reference for E2E-without-skip pattern): commit `2207e945`
