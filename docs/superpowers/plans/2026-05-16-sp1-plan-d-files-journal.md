# SP-1 Plan D — Files (NACHA/835) + Journal Ledger + Hash-Chain Verifier

**Date:** 2026-05-16
**Sub-project:** SP-1 PaySync Operator Portal
**Status:** Ready for execution
**Depends on:** SP-1 Plan C (Batches + AR/AP surfaces complete)

---

## §10 Plan-Time Decisions Owned by This Plan

| # | Decision | Resolution |
|---|---|---|
| §10.4 | Hash-chain verifier perf budget | Sync endpoint acceptable for ≤10 000 journal entries (target: <5 seconds on a single Postgres query scan with hash recomputation in Python). For chains >10 000 entries the sync endpoint returns `{"verified": null, "too_large": true, "job_id": null}` and the UI shows "Chain too large for sync verify — use the scheduled job" with a link to the audit-job runner. The job-based path (`core-platform/src/jobs/verify_audit_chain_job.py`) already exists; SP-1 does not modify it. The 10 000-entry threshold is configurable via `PAYSYNC_HASH_CHAIN_SYNC_LIMIT` env var (default: 10000). |

---

## Goal

Deliver the three remaining new surfaces: `files/` (NACHA + 835 file generation, download, and
provenance trace), `journal/` (immutable ledger viewer + synchronous hash-chain verifier), and
the final Inbox card (`journal_periodic_review`). After Plan D, an Auditor can open the journal,
view the full hash-chained entry list, trigger the sync verifier, and see a red/green/amber
`HashChainBadge`. An Approver can generate NACHA and 835 files from a released payment run or
batch, download them, and see the provenance trace back to the source upload.

This plan also wires the three backend capabilities that support these surfaces:
1. Thin sync wrapper around `core-platform`'s existing `verify_audit_chain_job.py` logic.
2. NACHA/835 file artifact tracking table (so generated files are queryable and downloadable).
3. File-provenance backward link: every generated file carries the batch/payment-run ID and
   the upload chain.

---

## Scope

**In:**
- `surfaces/files/` — `FilesListPage`, `FileGeneratePanel`, `ProvenanceTrace` component, BFF handlers
- `surfaces/journal/` — `JournalLedgerView`, `HashChainVerifierPanel`, `JournalEntryDetail`, BFF handlers
- `src/inbox/cards/JournalPeriodicReviewCard.tsx` — final stub replaced with real component
- Backend: `modules/billing/src/api/files.py` — file artifact CRUD + download endpoint
- Backend: `modules/billing/src/models/file_artifact.py` — `FileArtifact` ORM model
- Backend: `modules/billing/alembic/versions/0013_add_file_artifacts.py` — migration
- Backend: `modules/core-platform/src/api/journal_verify.py` — new thin sync verifier endpoint
- Backend: `modules/billing/src/api/inbox.py` extended — `journal_periodic_review` derivation
- Contract: `FilesClient`, `JournalClient` — interface + RealImpl + MockImpl
- `packages/contract/src/paysync/types.ts` — `FileArtifact`, `JournalEntry`, `HashChainResult` types
- `infrastructure/manifests/operator-dev.yml` — add `PAYSYNC_HASH_CHAIN_SYNC_LIMIT` to `required_env`
- Unit tests: file artifact service, sync verifier (verified / broken / empty / too-large cases)
- Integration tests: files router (3 roles × 4 endpoints), journal-verify router (Auditor only)

**Out:**
- Real bank ACH submission (deferred per spec §3)
- Real clearinghouse 835 routing (deferred per spec §3)
- E2E Playwright round trip (Plan E)
- Reports and setup surfaces (Plan E)

---

## Tasks

### Task 1 — Backend: FileArtifact model + migration

The existing `modules/billing/src/services/nacha.py` and
`modules/edi-compliance/src/x12/generators/gen_835.py` generate files but do not persist
artifact metadata. Plan D adds a `FileArtifact` table that tracks every generated file.

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 1.1 | `FileArtifact` ORM model | `modules/billing/src/models/file_artifact.py` | unit: model fields | Model importable |
| 1.2 | Alembic migration | `modules/billing/alembic/versions/0013_add_file_artifacts.py` | upgrade + downgrade clean | Schema updated |

**`FileArtifact` model fields:**
- `id` — `PG_UUID(as_uuid=True)`, PK
- `tenant_id` — `PG_UUID(as_uuid=True)`, NOT NULL, indexed `(tenant_id, generated_at)`
- `kind` — `VARCHAR(16)`, NOT NULL; enum values: `nacha`, `835`
- `source_batch_id` — `PG_UUID(as_uuid=True)`, nullable FK `batches.id` (NACHA source)
- `source_payment_run_id` — `PG_UUID(as_uuid=True)`, nullable FK `payment_runs.id` (835 source)
- `upload_id` — `PG_UUID(as_uuid=True)`, nullable FK `uploads.id` (backward provenance link)
- `generated_by` — `PG_UUID(as_uuid=True)`, NOT NULL, FK `users.id`
- `generated_at` — `TIMESTAMP WITH TIME ZONE`, NOT NULL, server_default=now()
- `filename` — `VARCHAR(512)`, NOT NULL
- `file_path` — `VARCHAR(1024)`, NOT NULL (absolute path on disk; never exposed in API response)
- `file_size` — `BIGINT`, NOT NULL
- `sha256` — `CHAR(64)`, NOT NULL
- `status` — `VARCHAR(32)`, NOT NULL, default `'ready'`; values: `generating`, `ready`, `error`
- Inherits `TenantScopedMixin`

**Constraint:** exactly one of `source_batch_id` or `source_payment_run_id` must be non-null
(enforced at the service layer, not DB constraint, to keep migration simple).

- [ ] Step 1.1: Write `modules/billing/src/models/file_artifact.py`
- [ ] Step 1.2: Write migration `0013`; verify upgrade + downgrade
- [ ] Step 1.3: Write unit tests for model fields
- [ ] Step 1.4: Commit — `feat(sp-1-d): FileArtifact ORM model + alembic 0013`

---

### Task 2 — Backend: files router (generate + download + list)

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 2.1 | `FilesService.generate_nacha` | `modules/billing/src/services/file_artifact.py` | unit: wraps `nacha.py` generator, writes FileArtifact row, sets upload_id chain | NACHA generated + tracked |
| 2.2 | `FilesService.generate_835` | same file | unit: wraps `gen_835.py` generator | 835 generated + tracked |
| 2.3 | Files router | `modules/billing/src/api/files.py` | integration: 3 roles × 4 endpoints | Endpoints live |
| 2.4 | Mount on billing app | `modules/billing/src/main.py` | integration: `/api/v1/billing/files` responds | Router wired |

**Endpoints:**
- `GET /api/v1/billing/files` — list file artifacts (all roles, tenant-scoped)
- `GET /api/v1/billing/files/{id}` — file artifact detail (all roles)
- `POST /api/v1/billing/files/generate` — body: `{kind: "nacha"|"835", source_id: uuid}` — **Approver only** (403 for Operator, Auditor)
- `GET /api/v1/billing/files/{id}/download` — streams file bytes (all roles; sets `Content-Disposition: attachment`)

**Download security:** `file_path` is never returned in API JSON. The download endpoint reads
the file from disk using the stored `file_path` and streams bytes. `Cache-Control: no-store`
on download response (files may contain payment data).

**upload_id chain resolution:** when generating, the service resolves `upload_id` by:
- NACHA: `batch.upload_id` (set in Plan C Task 1)
- 835: `payment_run.upload_id` (set in Plan C Task 1)
If the source entity has no `upload_id` (legacy data), `FileArtifact.upload_id` is null.

**Existing generator integration:**
- `modules/billing/src/services/nacha.py` — call `generate_nacha_file(batch_id)` (confirm exact
  function signature by reading the file before writing the wrapper; do not invent a signature)
- `modules/edi-compliance/src/x12/generators/gen_835.py` — call the 835 generator (confirm
  function signature by reading before writing; use the existing interface, no changes to that file)

- [ ] Step 2.1: Read `modules/billing/src/services/nacha.py` and `modules/edi-compliance/src/x12/generators/gen_835.py` to confirm exact function signatures
- [ ] Step 2.2: Write `modules/billing/src/services/file_artifact.py` wrapping both generators
- [ ] Step 2.3: Write `modules/billing/src/api/files.py` router
- [ ] Step 2.4: Mount on `modules/billing/src/main.py`
- [ ] Step 2.5: Write unit tests for service (generate + artifact row creation)
- [ ] Step 2.6: Write integration tests (3 roles × 4 endpoints; download streams bytes)
- [ ] Step 2.7: Run billing tests — 100% on auth/RBAC paths, ≥95% on file service
- [ ] Step 2.8: Commit — `feat(sp-1-d): files router — NACHA/835 generate + download + provenance`

---

### Task 3 — Backend: sync hash-chain verifier endpoint

Per spec §5.5 point 3 and §10.4 resolution.

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 3.1 | Sync verifier service | `modules/core-platform/src/api/journal_verify.py` | unit: verified / broken / empty / too-large | Endpoint live |
| 3.2 | Mount on core-platform app | `modules/core-platform/src/main.py` | integration: Auditor 200, non-Auditor 403 | RBAC enforced |

**Endpoint:** `POST /api/v1/core/journal/verify`

**Request:** `{}` (no body required — verifies the full chain for the current tenant)

**Response schema:**
```json
{
  "verified": true | false | null,
  "broken_at_entry": "entry-id-string | null",
  "entry_count": 9999,
  "too_large": false | true,
  "elapsed_ms": 1234
}
```

**Implementation (§10.4 resolution):**
1. Count entries for tenant: `SELECT COUNT(*) FROM audit_log WHERE tenant_id = :tid`
2. If count > `PAYSYNC_HASH_CHAIN_SYNC_LIMIT` (default 10000): return `{verified: null, too_large: true, entry_count: N, broken_at_entry: null, elapsed_ms: <elapsed>}`
3. Else: iterate entries in `created_at ASC` order, recompute each `entry_hash` from `(prev_hash + action + who + when + payload)` using the same algorithm as `verify_audit_chain_job.py`. Stop at first mismatch.
4. Return `{verified: true/false, broken_at_entry: <id>|null, entry_count: N, too_large: false, elapsed_ms: <elapsed>}`

**CRITICAL:** read `modules/core-platform/src/jobs/verify_audit_chain_job.py` before writing
the hash computation. Use the **exact same** hash function and field ordering. Any deviation
will produce false "chain broken" results. Do not invent a hash algorithm.

**RBAC:** Auditor only. Operator and Approver receive 403.

**Unit tests** (per spec §9.1):
- verified: feed 5 correct entries → `{verified: true}`
- broken: feed 5 entries with one corrupted hash → `{verified: false, broken_at_entry: <id>}`
- empty: 0 entries → `{verified: true, entry_count: 0}` (empty chain is trivially valid)
- too-large: entry_count > limit → `{verified: null, too_large: true}`

- [ ] Step 3.1: Read `modules/core-platform/src/jobs/verify_audit_chain_job.py` to extract hash function
- [ ] Step 3.2: Write `modules/core-platform/src/api/journal_verify.py` using extracted hash function
- [ ] Step 3.3: Mount on `modules/core-platform/src/main.py`
- [ ] Step 3.4: Write unit tests for all 4 cases
- [ ] Step 3.5: Write integration test: Auditor 200, Operator 403, Approver 403
- [ ] Step 3.6: Run core-platform tests — all pass
- [ ] Step 3.7: Commit — `feat(sp-1-d): sync hash-chain verifier endpoint (Auditor-only, ≤10k entries)`

---

### Task 4 — Backend: inbox extension + journal_periodic_review

Extend `modules/billing/src/api/inbox.py` with `journal_periodic_review` kind derivation.

**Derivation logic:** one `journal_periodic_review` item appears in the Auditor's inbox if the
last completed hash-chain verification (stored as an audit event of type `audit.journal.verified`)
is older than 7 days, OR if no verification has ever been run. Priority: `normal`. `upload_id: null`
(journal entries are not upload-scoped).

- [ ] Step 4.1: Extend `inbox.py` with `journal_periodic_review` derivation
- [ ] Step 4.2: Write integration test: Auditor inbox contains `journal_periodic_review` item when last verify > 7 days ago
- [ ] Step 4.3: Commit (can be squashed with Task 3's commit if small)

---

### Task 5 — Contract: FilesClient + JournalClient

| # | Client | File | Key methods |
|---|---|---|---|
| 5.1 | `FilesClient` | `packages/contract/src/paysync/files-client.ts` | `list`, `get`, `generate`, `download` |
| 5.2 | `JournalClient` | `packages/contract/src/paysync/journal-client.ts` | `listEntries`, `verify` |

**`HashChainResult` type** in `packages/contract/src/paysync/types.ts`:
```ts
export type HashChainResult = {
  verified: boolean | null;   // null = too_large
  broken_at_entry: string | null;
  entry_count: number;
  too_large: boolean;
  elapsed_ms: number;
};
```

**`JournalEntry` type:**
```ts
export type JournalEntry = {
  id: string;
  tenant_id: string;
  action: string;
  who: string;          // user_id — not a PHI field
  when: string;         // ISO 8601
  entry_hash: string;   // full SHA-256, shown truncated in UI
  prev_hash: string | null;
  payload: Record<string, unknown>;
  upload_id: string | null;
};
```

**MockImpl for `JournalClient.verify`:** returns `{verified: true, broken_at_entry: null, entry_count: 5, too_large: false, elapsed_ms: 42}` by default. Fixture override available for broken-chain test scenario.

- [ ] Step 5.1–5.2: Write both clients with RealImpl + MockImpl
- [ ] Step 5.3: Add `HashChainResult`, `JournalEntry`, `FileArtifact` to `types.ts`
- [ ] Step 5.4: `tsc -b` clean
- [ ] Step 5.5: Commit — `feat(sp-1-d): contract FilesClient + JournalClient + HashChainResult type`

---

### Task 6 — Frontend: files surface

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 6.1 | `FilesListPage` | `surfaces/files/FilesListPage.tsx` | RTL: renders list, kind badge (NACHA/835), download link | List view |
| 6.2 | `FileGeneratePanel` | `surfaces/files/FileGeneratePanel.tsx` | RTL: Approver sees generate button; Auditor sees disabled; success shows new artifact | Generate panel |
| 6.3 | `ProvenanceTrace` | `surfaces/files/ProvenanceTrace.tsx` | RTL: chain file → batch → cycle → upload rendered | Provenance |
| 6.4 | BFF handlers | `surfaces/files/bff/` | — | Route handlers |
| 6.5 | Update surface `index.ts` | `surfaces/files/index.ts` | — | Surface wired |

**`FileGeneratePanel`** — Approver-only action via `RbacGate`. On submit: POST to BFF →
`FilesClient.generate({kind, source_id})` → backend writes artifact → response includes new
`FileArtifact`; panel shows success with download link. Write-path fail-fast: backend error →
error toast with `correlation_id`; never optimistic.

**`ProvenanceTrace`** — renders the full backward chain: `File → Batch B-0421 → Cycle 2026-05 → Upload #107`.
Uses `ProvenanceBreadcrumb` internally with the extended chain. If any link is null (legacy data),
renders that node as "Legacy (no link)".

**Download:** `GET /api/paysync/files/{id}/download` BFF handler proxies bytes from backend with
`Content-Disposition: attachment; filename="<artifact.filename>"`. Sets `Cache-Control: no-store`.

- [ ] Step 6.1–6.4: Implement files surface components + BFF
- [ ] Step 6.5: Update `surfaces/files/index.ts`
- [ ] Step 6.6: RTL tests
- [ ] Step 6.7: Commit — `feat(sp-1-d): files surface — NACHA/835 generate, download, provenance trace`

---

### Task 7 — Frontend: journal surface + HashChainBadge wired + final Inbox card

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 7.1 | `JournalLedgerView` | `surfaces/journal/JournalLedgerView.tsx` | RTL: renders entries, truncated hash shown, drill-in | Ledger view |
| 7.2 | `HashChainVerifierPanel` | `surfaces/journal/HashChainVerifierPanel.tsx` | RTL: Auditor trigger fires; shows verified/broken/too-large states | Verifier panel |
| 7.3 | `JournalEntryDetail` | `surfaces/journal/JournalEntryDetail.tsx` | RTL: full hash + prev_hash shown, upload cross-link present | Detail drawer |
| 7.4 | `HashChainBadge` wired | `src/components/HashChainBadge.tsx` (already created in Plan A) | RTL: green/amber/red states; click opens panel | Badge functional |
| 7.5 | BFF handlers | `surfaces/journal/bff/` | — | Route handlers |
| 7.6 | `JournalPeriodicReviewCard` | `src/inbox/cards/JournalPeriodicReviewCard.tsx` | RTL: renders last-verified date, click fires nav | Final card |
| 7.7 | Update surface `index.ts` | `surfaces/journal/index.ts` | — | Surface wired |

**`JournalLedgerView`** — TanStack Virtual list (per spec §6.4). Columns: `entry_hash` (first 8
chars + `...`), `prev_hash` (first 8 chars + `...`), `action`, `who`, `when`. Click row opens
`JournalEntryDetail` side drawer. Virtualized for performance — no pagination cursor needed for
display, though the BFF does cursor-based loading behind the scenes.

**`HashChainVerifierPanel`** — Auditor-only (`RbacGate role="auditor"`). States:
- Idle: "Verify chain integrity" button
- Running: spinner + "Verifying..."
- `verified: true`: green badge "Chain intact — N entries verified in Xms"
- `verified: false`: red badge "Chain BROKEN at entry [broken_at_entry short-hash]" + escalation
  message "Do not modify journal — contact compliance team"
- `verified: null` (too_large): amber badge "Chain too large for sync verify (>10 000 entries) — use the scheduled job"
- Per spec §8: does NOT auto-repair on break.

**`HashChainBadge` states** (Plan A created the shell; Plan D wires real state):
- Green: last verify passed + < 7 days ago
- Amber: last verify passed + ≥ 7 days ago (scheduled review overdue)
- Red: last verify returned `verified: false`
- Grey: no verify ever run

**`JournalEntryDetail`** — cross-links to upload provenance: if `entry.upload_id` is non-null,
renders "Provenance: Upload #N" linking to `UploadDetailPage`.

- [ ] Step 7.1–7.5: Implement journal surface components + BFF
- [ ] Step 7.6: Implement `JournalPeriodicReviewCard` (replaces Plan A stub)
- [ ] Step 7.7: Update `surfaces/journal/index.ts`
- [ ] Step 7.8: Wire `HashChainBadge` to `JournalClient.verify` result state
- [ ] Step 7.9: RTL tests for all components + all 4 verifier states + all 4 badge states
- [ ] Step 7.10: Run `npm --workspace=@infinityrx/module-paysync test` — all pass
- [ ] Step 7.11: Commit — `feat(sp-1-d): journal surface — ledger, verifier panel, hash-chain badge + final inbox card`

---

## Gate Criteria

Plan D is complete when ALL of the following are true:

- [ ] `modules/billing` tests pass; 100% on auth/RBAC paths for files router (Approver-only generate, all roles download); ≥95% on file artifact service
- [ ] `modules/core-platform` tests pass; 100% on journal_verify auth path (Auditor only → 200; others → 403); 4 verifier unit tests pass (verified/broken/empty/too-large)
- [ ] Migration `0013` upgrades and downgrades cleanly
- [ ] `POST /api/v1/core/journal/verify` with 0 entries returns `{verified: true, entry_count: 0}`
- [ ] `POST /api/v1/core/journal/verify` with a corrupted entry returns `{verified: false, broken_at_entry: <id>}`
- [ ] `POST /api/v1/core/journal/verify` when count > limit returns `{verified: null, too_large: true}`
- [ ] `POST /api/v1/billing/files/generate` by Auditor returns 403
- [ ] `npm --workspace=@infinityrx/module-paysync test` passes; all 11 Inbox card components non-stub; ≥95% on files + journal surfaces
- [ ] `HashChainVerifierPanel` RTL test: 4 states (idle, verified, broken, too-large) all render correctly
- [ ] `HashChainBadge` RTL test: green/amber/red/grey states rendered
- [ ] `JournalEntryDetail` RTL test: upload cross-link renders when `upload_id` present
- [ ] `tsc -b` clean across workspace
- [ ] `infrastructure/manifests/operator-dev.yml` includes `PAYSYNC_HASH_CHAIN_SYNC_LIMIT` in `required_env`

---

## Deliverables

- `FileArtifact` model + migration — queryable generated-file registry with upload provenance
- Files surface (generate, list, download, provenance trace)
- Journal surface (ledger viewer, verifier panel, entry detail)
- Sync hash-chain verifier endpoint (Auditor-only, <5s for ≤10k entries, graceful too-large path)
- All 11 Inbox card components fully implemented (no stubs remaining)
- `FilesClient` + `JournalClient` real implementations
- `HashChainBadge` fully wired with 4 states

---

## Dependencies

- SP-1 Plan C complete (Batch + PaymentRun `upload_id` FKs present; billing app factory running)
- `modules/core-platform/src/jobs/verify_audit_chain_job.py` exists (confirmed in directory listing)
- `modules/billing/src/services/nacha.py` exists (confirmed)
- `modules/edi-compliance/src/x12/generators/gen_835.py` exists (confirmed)
- `TanStack Virtual` available in `packages/ui` (SP-0 Plan C/D)
- `@infinityrx/module-paysync` Plan A primitives: `HashChainBadge`, `RbacGate`, `ProvenanceBreadcrumb`

---

## Cross-references

- Spec §5.5 (backend posture — sync verifier endpoint), §6.3 (files surface), §6.4 (journal surface), §6.6 (HashChainBadge, RoleSwitcherChip production ban), §7.1 (canonical flow steps 11–13), §8 (hash chain break — no auto-repair; write-path fail-fast), §9.1 (unit test layers for hash verifier), §10.4 (perf budget decision)
- Rules: `.claude/rules/security.md` (Auditor-only gate; no PHI in error envelopes), `.claude/rules/phi-compliance.md` (`Cache-Control: no-store` on file download), `.claude/rules/testing.md` (100% security/auth path coverage), `.claude/rules/hipaa-2026.md` (audit tamper-evidence — do not auto-repair broken chain)
- SP-1 Plan C: `docs/superpowers/plans/2026-05-16-sp1-plan-c-batches-ar-ap.md`
- SP-1 Plan E: E2E covers the full NACHA + 835 download path and journal verify as Auditor
- Existing: `modules/core-platform/src/jobs/verify_audit_chain_job.py`, `modules/billing/src/services/nacha.py`, `modules/edi-compliance/src/x12/generators/gen_835.py`
