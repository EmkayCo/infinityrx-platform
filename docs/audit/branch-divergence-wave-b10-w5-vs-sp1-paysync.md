# Branch Divergence Audit: wave/B10-w5 vs wave/B10-w5-sp1-paysync

**Date:** 2026-05-20
**Auditor:** Claude (read-only analysis — no merge, cherry-pick, or write ops performed)
**Purpose:** Integration picture before any merge decision

---

## 1. Divergence Summary

| Item | Value |
|---|---|
| Merge-base commit | `ef13b320` — `feat(sp-1-a): scaffold @infinityrx/module-paysync package` (2026-05-16) |
| HEAD (`wave/B10-w5`) commits ahead | **100 commits** (2026-05-17 → 2026-05-20) |
| sp1-paysync commits ahead | **95 commits** (2026-05-16 → 2026-05-18) |
| Date range (parallel work) | ~2 days of parallel development from same scaffold point |

### Branch Focus (inferred from commit themes)

**wave/B10-w5 (HEAD)** — SP-2 Directories module + SP-3 ReclaimRx module
- SP-2 (Plans A–E): Federated search, 6 browse clusters, ingestion console, quality dashboard, E2E harness
- SP-3 (Plans A1–A5): ReclaimRx ORM extensions, outbox/DLQ, investigation state machine, graph job, portal scaffold
- Portal fixes: react-query dual-bundle collapse, transpilePackages, Turbopack alias
- Docs: SP-2 acceptance doc (codex R5 GO), SP-3 plans (still in codex review cycle)
- **Zero billing backend changes since merge-base** — billing dir on HEAD is identical to merge-base

**wave/B10-w5-sp1-paysync** — SP-1 billing/paysync upload subsystem completion
- Plans B–E: Upload ORM+service, inbox router, cycles router, files router, journal hash chain
- RBAC hardening (19 endpoints), SAVEPOINT test isolation, error envelope standardization
- Frontend: paysync module surfaces wired as Next.js App Router pages, Playwright E2E
- QA harness: fixtures, auth helpers, DB cleanup, seed endpoints
- **Zero reclaimrx changes, zero directories changes**

---

## 2. Per-Module Breakdown

### Backend modules

| Module | HEAD (files / ±lines) | sp1-paysync (files / ±lines) | Status |
|---|---|---|---|
| `modules/billing` | **0 / 0** — unchanged | **59 files / +11,646 −111** | sp1-paysync ONLY |
| `modules/reclaimrx` | **61 files / +9,374 −319** | **0 / 0** — unchanged | HEAD ONLY |
| `modules/prescriber-directory` | **9 files / +850 −301** | **0 / 0** — unchanged | HEAD ONLY |
| `modules/drug-database` | **5 files / ~+200** | **0 / 0** — unchanged | HEAD ONLY |
| `modules/core-platform` | **6 files / +393 −25** | **6 files / +393 −25** | BOTH TOUCHED — conflict risk (see §4) |

### Frontend packages

| Package | HEAD (files / ±lines) | sp1-paysync (files / ±lines) | Status |
|---|---|---|---|
| `packages/modules/paysync` | 0 (at merge-base) → exists | **large** — full surface tree | sp1-paysync ONLY |
| `packages/modules/directories` | **~100 files / +14k** | 0 | HEAD ONLY |
| `packages/modules/reclaimrx` | **~10 files / +800** | 0 | HEAD ONLY |
| `packages/contract/src` | **+35 lines** (index.ts) | **+123 lines** (index.ts + paysync impls) | BOTH TOUCHED — conflict risk |
| `packages/qa-harness` | **~10 files / +800** (directories E2E) | **~10 files / +800** (paysync fixtures) | BOTH TOUCHED — different files, low conflict risk |
| `packages/shell/src/_generated/manifest.json` | **+57 lines** | **0** — unchanged | HEAD ONLY |

### Portal

| Area | HEAD (files / ±lines) | sp1-paysync (files / ±lines) | Status |
|---|---|---|---|
| `portal/operator` (overall) | **36 files / +1,256 −1,805** | **41 files / +673 −6,216** | BOTH TOUCHED |
| `portal/operator/app/admin/paysync/` | Large additions (paysync pages) | Large additions (same path) | BOTH TOUCHED — conflict risk |
| `portal/operator/components/layout/nav-config.ts` | +7 lines | +8 −7 lines | BOTH TOUCHED — conflict risk |
| `portal/operator/tests/e2e/` | directories round-trip spec | paysync round-trip spec | Different files, low conflict |

---

## 3. Billing/Paysync Upload Subsystem (sp1-paysync ONLY)

These 59 files exist on sp1-paysync and are **absent from HEAD**. This is the integration target.

### New backend files (net-new, HEAD has none of these)

**Alembic migrations (6 new after baseline 0001/0002):**
- `0003_add_upload_resource.py` — Upload table + nullable upload_id FK + amount_billed on claim_records
- `0004_propagate_upload_id.py` — FK propagation onto derived billing entities
- `0005_add_file_artifacts.py` — FileArtifact table
- `0006_add_journal_hash_chain.py` — journal hash chain columns
- `0007_journal_entry_hash_drop_default.py`
- `0008_journal_chain_index_includes_id.py` — deterministic chain ordering fix

**New API routers (9 new):**
- `src/api/uploads.py` — POST /uploads (dropzone), GET /uploads, GET /uploads/{id}, supersede logic
- `src/api/inbox.py` — inbox derivation (4 card types)
- `src/api/cycles.py` — /cycles backed by PaymentBatch
- `src/api/files.py` — generate/download/list/get
- `src/api/journal.py` — hash chain + sync verifier
- `src/api/bank_settlements.py`, `carryovers.py`, `payment_runs.py`, `reconciliations.py`
- `src/api/seed.py` — fixture seed endpoint (auth-gated, tenant-safe)

**Modified shared files:**
- `src/api/router.py` — mounts all 9 new routers
- `src/api/dependencies.py` — RBAC enforcement additions
- `src/main.py` — configure_auth_trust_jwt wired, error envelope handler

**New models:**
- `src/models/file_artifact.py` — FileArtifact ORM
- `src/models/journal_hash.py` — JournalHash ORM
- `src/models/tables.py` — extended with Upload model + FK columns

**New services:**
- `src/services/upload.py` — parser, sha256 dedup, row-error capture, supersede, Decimal precision
- `src/services/file_artifact.py`

**New events:**
- `src/events/upload_events.py` — paysync.upload.parsed publisher
- `src/events/consumers.py` — upload_parsed consumer via _make_wrapper

**New jobs:**
- `src/jobs/scheduled.py` — cleanup_old_uploads job

### New test files (28 new integration + unit tests)

| File | Scope |
|---|---|
| `tests/unit/test_upload.py` | Upload service unit tests |
| `tests/unit/test_upload_model.py` | ORM model tests |
| `tests/unit/test_upload_events.py` | Event publisher tests |
| `tests/unit/test_upload_id_propagation.py` | FK propagation tests |
| `tests/unit/test_file_artifact_model.py` | FileArtifact ORM |
| `tests/unit/test_journal_hash_chain.py` | Hash chain logic |
| `tests/unit/test_journal_auto_hash.py` | Auto-compute on insert |
| `tests/unit/test_events_and_jobs.py` | Consumer + cleanup job |
| `tests/integration/test_uploads_router.py` | Upload endpoint integration |
| `tests/integration/test_cycles_router.py` | Cycles endpoint |
| `tests/integration/test_inbox_router.py` | Inbox derivation |
| `tests/integration/test_files_router.py` | File generate/download |
| `tests/integration/test_journal_router.py` | Journal hash chain API |
| `tests/integration/test_bank_settlements_router.py` | Bank settlements |
| `tests/integration/test_carryovers_router.py` | Carryovers |
| `tests/integration/test_payment_runs_router.py` | Payment runs |
| `tests/integration/test_reconciliations_router.py` | Reconciliations |
| `tests/integration/test_rbac_b6_endpoints.py` | RBAC on 19 endpoints |
| `tests/integration/test_rbac_mutating_endpoints.py` | Mutating endpoint guards |
| `tests/integration/test_wired_routes.py` | Route wiring smoke |
| `tests/integration/test_api_routes.py` | Extended API route tests |
| `tests/conftest.py` | SAVEPOINT-based isolation (LESSON-001) |
| `tests/test_main.py`, `test_seed.py`, `test_tables.py` | App-level tests |
| `tests/test_bank_settlements.py`, `test_carryovers.py`, `test_payment_runs.py`, `test_reconciliations.py` | Service-level |

**Test coverage assessment:** The commit history shows repeated codex gate NO-GO / BLOCK cycles resolved through R1–R3, indicating these tests were hardened through review. SAVEPOINT isolation is present (LESSON-001 compliant). No coverage percentage is available without running pytest, but the 28 test files with integration + unit + RBAC + events coverage is substantial.

---

## 4. Conflict-Risk Hotspots

Files modified on **both** branches since merge-base (`ef13b320`). These will require manual resolution on merge.

| File | HEAD delta | sp1-paysync delta | Conflict risk level | Notes |
|---|---|---|---|---|
| `portal/operator/components/layout/nav-config.ts` | +7 lines | +8 ins, −7 del | **HIGH** | Both added nav entries; sp1 also deleted stale links. Different nav sections but same file — likely line-level conflict |
| `packages/contract/src/index.ts` | +35 lines | +123 lines | **HIGH** | HEAD added directories exports (+35); sp1 added paysync contract impls (+123). Both appended to barrel — likely additive but same file |
| `infrastructure/manifests/operator-dev.yml` | +19 −5 | +33 −7 | **MEDIUM** | Both added module entries to the dev manifest. Probably different sections but structural YAML conflicts possible |
| `package-lock.json` | +119 −38 | +64 ins | **MEDIUM** | Different npm dependency sets. Regenerating after merge is safer than manual resolution |
| `modules/core-platform/src/main.py` | +some | +71 −some | **HIGH** | sp1 added `configure_auth_trust_jwt` wiring + canonical error envelope handler; HEAD path unclear but both touched. Check for duplicate handler registration |
| `modules/core-platform/tests/test_main_auth_wired.py` | +12 | +12 | **MEDIUM** | Both modified auth wiring tests — likely different assertions |
| `modules/core-platform/tests/test_main.py` | present | +58 | **MEDIUM** | sp1 added 58 lines of new tests |
| `modules/core-platform/tests/test_test_auth.py` | present | +107 | **LOW** | sp1 added 107-line test file; HEAD may have same or different version |

### Critical file to inspect before merging: `modules/core-platform/src/main.py`

sp1-paysync added `configure_auth_trust_jwt` call in billing's `create_app()` and a canonical `HTTPException` handler (`fix(sp-1-e-B7)`). HEAD also touched core-platform. If both added exception handlers or modified the same `create_app` function body, this will be a semantic conflict (no marker, but wrong behavior).

---

## 5. What HEAD Has That sp1-paysync Lacks

The following is **not** on sp1-paysync and would be lost in a sp1→HEAD overwrite. A merge direction of sp1-paysync→HEAD (i.e., bringing sp1 work onto HEAD) correctly preserves all of this.

### SP-3 ReclaimRx (61 files, ~9,374 net lines)
- `modules/reclaimrx/alembic/versions/0008_sp3_extensions.py`
- Full outbox/DLQ subsystem: `OutboxService`, `OutboxDispatcher`, `DLQRepository`, idempotency wiring
- Investigation state machine (`validate_transition`, `InvestigationService.transition()`)
- `POST /investigations/{id}/transitions`, `POST /holds/{id}/release` endpoints
- `AccumulatorConsumer` wired to `accumulator.updated` event
- Graph analysis job real implementation + `/graph-runs/trigger` endpoint
- 14+ new integration tests, 7 new unit tests (scheduler, audit-chain job, DLQ monitor)
- ReclaimRx contract layer: types, real client, mock client, 6 portal pages scaffolded

### SP-2 Directories (138 files, ~14,492 net lines on packages side)
- `packages/modules/directories/` — entire module (federated search, 6 browse clusters, ingestion console, quality dashboard, CommandPalette)
- BFF routes: `/api/directories/search`, `/api/directories/quality`, ingest proxy
- `prescriber-directory`: shared ingestion router mounted + integration test
- SP-2 acceptance document (codex R5 GO)

### Portal / Infrastructure
- `packages/shell/src/_generated/manifest.json` — 57-line expansion (directories + reclaimrx entries)
- `portal/operator/tests/e2e/directories/sp2-directories-round-trip.spec.ts` — 896-line E2E spec
- `.gitignore` updates, `CLAUDE.md` compaction, `tsconfig.json` changes
- `infrastructure/integrations.yml` additions
- Drug-database API fixes (router repoints to seeded data)
- Turbopack/react-query bundle fixes (Windows build fix)

**Confirmed: SP-3 reclaimrx and SP-2 directories live ONLY on HEAD. They would be unaffected by merging sp1-paysync INTO HEAD.**

---

## 6. Recommended Merge Strategy

### Direction: sp1-paysync → HEAD (bring sp1 work onto HEAD, not the reverse)

Reversing direction (HEAD → sp1-paysync) would lose all SP-2 and SP-3 work. Do not do this.

### Strategy: Full merge, not cherry-pick

**Rationale for full merge over cherry-pick:**
- sp1-paysync has 95 commits. Individually cherry-picking the ~59 billing files would require selecting ~40+ commits while skipping sp1-paysync's own portal/contract commits that overlap with HEAD's portal work. The overlap is in exactly the 4–8 conflict files — cherry-pick does not help with those, it just makes the history harder to read.
- A full merge produces one reconciliation point with a clear audit trail. The conflict surface (4–8 files) is manageable.
- The `backup/wave-B10-w5-sp1-paysync-with-sp2-cherrypick` branch suggests this exact merge pattern was already explored — inspect it before starting.

### Sequencing

1. **Pre-merge:** Check `backup/wave-B10-w5-sp1-paysync-with-sp2-cherrypick` to see if prior reconciliation work already exists. If it's ahead of both branches, it may be the right base.
2. **Create a merge branch** off HEAD: `git checkout -b merge/sp1-paysync-into-b10-w5`
3. **Run `git merge wave/B10-w5-sp1-paysync --no-ff --no-commit`** — stage conflicts without committing.
4. **Resolve conflicts in priority order:**

| Priority | File | Resolution approach |
|---|---|---|
| 1 | `modules/core-platform/src/main.py` | Manual — check for duplicate handler registration; sp1's `configure_auth_trust_jwt` and error envelope handler must be kept; HEAD's changes must also be preserved |
| 2 | `portal/operator/components/layout/nav-config.ts` | Manual — keep all nav entries from both branches; sp1 deleted orphan links (keep those deletions) |
| 3 | `packages/contract/src/index.ts` | Likely additive — keep all exports from both; no semantic conflict expected |
| 4 | `infrastructure/manifests/operator-dev.yml` | Manual YAML merge — keep all module entries from both |
| 5 | `package-lock.json` | Delete and regenerate with `npm install` after all other conflicts resolved |
| 6 | `modules/core-platform/tests/` | Keep all test files from both; resolve assertion conflicts carefully |

5. **After resolution:** Run full test suite for billing + core-platform + reclaimrx modules.
6. **Billing-specific smoke:** Confirm `/api/v1/billing/uploads` returns 200 (not 404) in the merged portal.

### High-risk files needing manual review (do not accept either side blindly)

- `modules/core-platform/src/main.py` — semantic conflict risk even if git resolves cleanly
- `portal/operator/components/layout/nav-config.ts` — sp1 deleted lines that HEAD may have modified

---

## 7. Open Question for the User

**Is sp1-paysync's billing the canonical version, or has HEAD's billing also advanced?**

Based on this audit: **HEAD's `modules/billing/` directory is byte-for-byte identical to the merge-base** (`ef13b320`). HEAD made zero changes to the billing Python module after the branch point. sp1-paysync made all 59 billing file changes.

However, before merging, confirm:
- Are the **6 new Alembic migrations** on sp1-paysync (0003–0008) compatible with any migration changes made directly to the deployment database since May 16? If the `develop`/`main` DB has already been migrated past 0002, the migration chain needs verification.
- The sp1-paysync commit `fix(sp-1): Plan B R2 — address pre-execute codex NO-GO (10 items)` + R3 fixes addressed 13 codex blockers. The final gate-close (`docs(sp-1): codex gate-close r1 verdict`) is present but the `docs(sp-1): deferred follow-ups for 6 NO-GO BLOCKs from codex gate-close r1` commit (`661f0d9c`) suggests **6 outstanding NO-GO items were deferred**. These are on sp1-paysync. Confirm whether those deferred items are acceptable to carry into HEAD or need resolution first.

---

## Appendix: File Counts Summary

| Category | Files on sp1-paysync only | Files on HEAD only | Files on both (conflict risk) |
|---|---|---|---|
| `modules/billing/` | 59 | 0 | 0 |
| `modules/core-platform/` | 0 | 3 | 3 |
| `modules/reclaimrx/` | 0 | 61 | 0 |
| `modules/prescriber-directory/` | 0 | 9 | 0 |
| `modules/drug-database/` | 0 | 5 | 0 |
| `packages/contract/src/` | paysync impls (5 files) | directories exports | index.ts shared |
| `packages/modules/paysync/` | ~50 surface files | 0 | 0 |
| `packages/modules/directories/` | 0 | ~100 files | 0 |
| `packages/modules/reclaimrx/` | 0 | ~10 files | 0 |
| `packages/qa-harness/` | paysync seeds | directories seeds | different files |
| `portal/operator/` | paysync pages + E2E | directories pages + E2E | nav-config.ts |
| Root / infra | — | — | manifest.yml, package-lock.json, contract/index.ts |

**Total conflict-risk files requiring manual resolution: ~6–8**
**Total new files sp1-paysync brings to HEAD: ~140 (59 billing Python + ~80 TS frontend)**
