# SP-1 — PaySync Operator Portal (Module on SP-0 Spine)

**Status:** Brainstormed; pending plan-writing.
**Date:** 2026-05-16
**Owner:** Mike
**Sub-project of:** Operator Portal & Platform Frontend milestone
**Builds on:** SP-0 (`2026-05-14-sp0-integration-foundation-design.md`)
**Replaces:** —

---

## 1. Problem statement

The PaySync backend is substantially built — `modules/billing/` ships AP/AR, hash-chained journal, NACHA, 835, cycle/batch model; `modules/payment-processing/` ships vendor adapters, ACH return handling, OFAC screening, business-day calendar; `modules/edi-compliance/` ships the 835 generator. The operator portal already scaffolds ~14 PaySync surfaces (`portal/operator/app/admin/paysync/` plus related routes in `accounting/`, `billing/`, `payments/`) and a typed client (`portal/shared/lib/paysync-api.ts`).

What's missing is the wiring that makes PaySync a usable, RBAC-gated, end-to-end operator product: an immutable upload-provenance layer (so claims forever trace back to their source file), a unified inbox-first IA that surfaces actionable work across all 14 surfaces, real-backend wiring of every scaffolded screen, and an end-to-end round-trip on synthetic non-PHI data. SP-1 delivers that as the first vertical built on the SP-0 spine — the first proof that the SP-0 module-package pattern produces a commercially coherent operator product.

---

## 2. Goals

1. Wrap the existing PaySync surfaces into `packages/modules/paysync/` per SP-0 §6.6 — composition becomes manifest-driven, no hardcoded portal routes for PaySync.
2. Add an **immutable Upload provenance layer**: every claim in upload #N stays forever associated with upload #N; bad data in one upload cannot poison other uploads.
3. Deliver an **Inbox-first all-in-one IA** (per locked S7) that surfaces actionable items across every PaySync workflow, filtered by RBAC role.
4. Enforce **Operator / Approver / Auditor RBAC** with segregation-of-duties on every mutating endpoint and every UI action.
5. Wire every PaySync surface to the real `modules/billing/` + `modules/payment-processing/` + `modules/edi-compliance/` backends via the SP-0 contract layer.
6. Ship an **end-to-end round trip on synthetic non-PHI data**: upload CSV → cycle close → AR invoice → AP payment run → NACHA + 835 download → journal hash-chain verify, runnable by a fresh user via the qa-harness fixture seed.

---

## 3. Non-goals (explicitly out of SP-1)

- **No claim adjudication.** Claims arrive already adjudicated (from operator's claims pipeline or historical export from a different adjudication engine). PaySync parses, validates, and processes them financially — it does not adjudicate.
- **No standalone-PaySync deployable.** SP-1 ships PaySync as a module inside the operator portal only. A separate `portal/paysync` deployable is a future SP.
- **No external partner delivery.** NACHA and 835 files are generated to disk / downloaded by the operator. Real bank ACH submission to the Federal Reserve and real clearinghouse 835 routing are deferred.
- **No 50-state PBM compliance reporting tables.** Backend gap flagged in CLAUDE.md; deferred.
- **No accumulator detection consumer wiring.** Backend gap flagged in CLAUDE.md; not blocking PaySync; deferred.
- **No client portal, provider portal, or no-code program builder.** Future SPs (per SP-0 §3 non-goals).

---

## 4. Locked decisions

| # | Decision | Choice | Source |
|---|---|---|---|
| S1 | SP-1 vertical | PaySync portal | brainstorm 2026-05-16 |
| S2 | Workflow scope | Full operator workflow (uploads → cycles → batches → AR/AP → NACHA/835 → settlement → journal → reports → setup) | brainstorm |
| S3 | Persona | All-in-one shared UI with RBAC gates (no single design center) | brainstorm |
| S4 | Integration depth | Portal/UI only; no external partner integration; no 50-state backend gap-fill; `Upload` resource counts as wiring, not gap-fill | brainstorm |
| S5 | Shippable bar | End-to-end round trip on synthetic data against the real backend | brainstorm |
| S6 | RBAC taxonomy | 3 roles — Operator / Approver / Auditor with segregation-of-duties | brainstorm |
| S7 | IA shape | Inbox-first (queue-driven landing + History + Journal + Reports + Setup) | brainstorm |
| S8 | Deployable shape | Module inside operator portal only; standalone deployable deferred | brainstorm |
| S9 | Upload provenance | NEW backend resource in scope; immutable file artifact; claims permanently scoped to their upload | brainstorm follow-up |

These decisions are inputs to the plan. If any are revisited, this spec must be revised first.

---

## 5. Architecture

### 5.1 Layering on SP-0

SP-1 is a **module package** consumed by `portal/operator` via the SP-0 composition mechanism (SD-4 generated artifact + manifest schema). Zero new framework, zero new packages outside the module.

```
portal/packages/modules/paysync/          ← NEW: the SP-1 deliverable
  src/
    inbox/                                  ← Inbox spine: queue model + item taxonomy + RBAC filter
    surfaces/                               ← One folder per operator workflow surface
      uploads/                                ← NEW surface (uploads list, upload detail, claim viewer scoped to upload)
      cycles/                                 ← composes existing app/admin/paysync/cycles/*
      batches/                                ← composes existing app/admin/paysync/batches/*
      carryovers/                             ← composes existing
      invoices/                               ← composes admin/paysync/invoices + accounting/invoices
      payment-runs/                           ← composes app/payments/batches + admin/paysync/manual-ap
      files/                                  ← NEW (NACHA + 835 generation + download + provenance trace)
      bank-settlements/                       ← composes existing
      reconciliations/                        ← composes existing
      journal/                                ← NEW (ledger viewer + sync hash-chain verifier)
      reports/                                ← composes accounting/cycles + accounting/journal-entries + period reports
      setup/                                  ← composes admin/paysync/{email-*, export-*, gl-*, invoice-sequences, cycle-schedules}
    bff/                                    ← Next.js route handlers per surface (per SP-0 §6.5; module-owned)
    components/                             ← Module-local primitives (ProvenanceBreadcrumb, MoneyDisplay, etc.)
    module.config.ts                        ← Composition entry: registered routes + RBAC matrix + Inbox kinds
  fixtures/                                 ← Synthetic non-PHI seed data (see §9)
  tests/                                    ← Unit + module-integration; E2E lives at portal level
```

Composed via `infrastructure/manifests/operator.yml` adding `paysync` to the module list; the SP-0 generator emits `packages/shell/src/_generated/module-imports.ts` containing only `import('@infinityrx/module-paysync')`.

### 5.2 Data model invariant — Upload provenance

**Every upload is an immutable provenance container.** Once N claims land in upload #107, those claims are forever scoped to upload #107. They never merge into a global claims store. Batches, invoices, and payment runs derived from those claims carry the upload-provenance backward link permanently.

```
Upload (NEW backend resource)
  ├─ id, tenant_id, filename, sha256, file_size, mime_type
  ├─ uploaded_at, uploaded_by, source_platform (free-text label; not an enum in SP-1)
  ├─ supersedes_upload_id (nullable FK to prior Upload — set when user re-uploads a corrected version)
  ├─ status: parsing | validation_failed | validated | superseded
  │            (superseded = a later Upload references this one via supersedes_upload_id;
  │             claims from the superseded Upload are NEVER deleted — provenance preserved)
  ├─ row_count, error_count
  └─ claims (FK: claim.upload_id NOT NULL)
       │
       ▼ feeds into existing scaffolding
Cycle (existing — payment_cycle | invoice_cycle)
  └─ Batches (existing — drafted | held | released | filed | settled)
       └─ NACHA / 835 file artifacts (downloadable, carry upload_id chain)
            └─ Bank Settlement → Reconciliation → Journal entry (immutable, hash-chained)
```

Provenance breadcrumb on every screen: `Upload #107 → Cycle 2026-05 → Batch B-0421 → Invoice INV-1029` or `Upload #107 → Cycle 2026-05 → Batch B-0421 → Payment Run PR-0317 → NACHA NACHA-20260516-001`.

### 5.3 Inbox spine — the design-center primitive

A **single typed item taxonomy** every surface contributes to. Designed up front so future surfaces register a new item kind without an Inbox refactor.

```ts
type InboxItemKind =
  | 'upload_pending_review'             // Operator: an upload finished parsing with row errors
  | 'upload_validated_awaiting_batching'// Operator: ready to flow into a cycle
  | 'cycle_pending_close'               // Operator: cycle window closed, awaits close action
  | 'cycle_close_review'                // Approver: close report ready for sign-off
  | 'batch_drafted'                     // Approver: payment batch awaiting release
  | 'ar_invoice_draft'                  // Approver: invoice ready to send
  | 'ap_payment_run_held'               // Approver: payment run held; release decision pending
  | 'banking_discrepancy'               // Approver: bank settlement does not match
  | 'reconciliation_pending'            // Approver: reconciliation awaits finalize
  | 'carryover_open'                    // Operator: carryover not yet settled
  | 'journal_periodic_review'           // Auditor: hash-chain verify scheduled
  // ... extensible

type InboxItem = {
  id: string;
  kind: InboxItemKind;
  tenant_id: string;
  upload_id: string | null;            // provenance link, always present where derivable
  rbac_required: RbacRole;             // 'operator' | 'approver' | 'auditor'
  created_at: string;
  priority: 'normal' | 'high';
  payload: object;                     // typed per kind via discriminated union
}
```

UI: virtualized list (TanStack Virtual) groups by kind, filters by `rbac_required` so each role sees only their own work, renders each item via a registered card component. Click-through navigates to the item's surface page.

### 5.4 RBAC matrix (Operator / Approver / Auditor)

| Action | Operator | Approver | Auditor |
|---|---|---|---|
| Upload file, view uploads, view upload-scoped claims | ✓ | ✓ | read-only |
| Create draft batch, invoice, payment run | ✓ | ✓ | read-only |
| Cycle close action | — | ✓ | read-only |
| Send invoice (commit) | — | ✓ | read-only |
| Release payment run (commit) | — | ✓ | read-only |
| Generate NACHA file, generate 835 file | — | ✓ | read-only |
| Finalize reconciliation | — | ✓ | read-only |
| Resolve banking discrepancy | — | ✓ | read-only |
| Manual AP entry (commit) | — | ✓ | read-only |
| Setup mutations (fee schedules, banks, GL, etc.) | — | ✓ | read-only |
| View journal | ✓ | ✓ | ✓ |
| Run sync hash-chain verifier | — | — | ✓ |
| View audit log | ✓ | ✓ | ✓ |

Enforced at three layers: BFF route handler (per SP-0 §6.5), backend endpoint (per SP-0 §6.2 + SD-1 claims), and UI (soft-disable + tooltip "Approver role required" rather than hide).

### 5.5 Backend posture

SP-1 talks to the real backends via the SP-0 contract layer. Mock client (per SP-0 mock/real toggle) remains available for offline dev.

**Backend work owned by SP-1 (call this wiring, not gap-fill):**
1. **`Upload` resource** (new) — table, sha256 dedup, file storage strategy (local for SP-1; deferred to S3/blob later), CSV/Excel parser dispatcher, validation pipeline, upload-scoped claim queries (`GET /uploads/{id}/claims`), upload_id FK on claim model and on every derived entity (cycle entries, batches, invoice lines).
2. **3-role server-side enforcement** — verify Operator/Approver/Auditor map cleanly to existing role infrastructure (per SP-0 SD-1 claims `roles: string[]`). Add role checks where missing on mutating endpoints listed in §5.4.
3. **Synchronous hash-chain verifier endpoint** — thin sync wrapper around `core-platform/src/jobs/verify_audit_chain_job.py` logic. Returns `{verified: bool, broken_at_entry: string | null}` for the Journal viewer.

**Backend explicitly NOT touched by SP-1 (deferred):**
- 50-state PBM compliance reporting tables
- External bank ACH submission (NACHA → Fed / sandbox bank)
- Real clearinghouse 835 routing
- Accumulator detection consumer wiring

### 5.6 Consumed from SP-0 (no rebuild)

- `packages/contract` — typed clients (extends existing `paysync-api.ts` patterns); new `UploadsClient` added
- `packages/auth` — JWT/MFA per SD-1; role enforcement primitives
- `packages/ui` — Radix/shadcn/TanStack Table+Virtual/recharts/react-hook-form+zod (already used by existing PaySync components)
- `packages/qa-harness` — fixture seeding buttons, mock/real toggle, request inspector, services-health
- `packages/shell` — routing, layout, RBAC gate, module mounting

---

## 6. Components

### 6.1 `inbox/`
- `InboxQueue` — virtualized list, group-by-kind, role filter
- `ItemRegistry` — maps `InboxItemKind` → card component + action set + RBAC gate
- `useInboxItems(role)` — TanStack Query hook polling `/api/paysync/inbox`
- Item card components — one per kind, scaled to the surface they hand off to

### 6.2 `surfaces/uploads/` (NEW)
- `UploadsListPage` — paginated table, status badge, sha256 dedup banner on retry uploads
- `UploadDropzone` — drag-and-drop + browse; multipart POST to BFF; progress bar
- `UploadDetailPage` — file metadata, parse status, row-error list, link to scoped claim viewer
- `UploadClaimViewer` — scoped to upload_id; reuses existing `PaginatedTable`
- `BFF /api/paysync/uploads/*` — POST (multipart streaming), GET (list, detail, claims)

### 6.3 `surfaces/files/` (NEW)
- `FilesListPage` — generated NACHA and 835 artifacts; columns: file_id, kind (NACHA|835), source batch, generated_by, generated_at, download
- `FileGeneratePanel` — Approver action: pick batch → POST to BFF → backend writes file → returns artifact ID
- `ProvenanceTrace` — file → batch → cycle → upload chain
- `BFF /api/paysync/files/*`

### 6.4 `surfaces/journal/` (NEW)
- `JournalLedgerView` — virtualized list of immutable journal entries; columns: entry_hash (short), prev_hash (short), action, who, when, drill-in
- `HashChainVerifierPanel` — Auditor action: trigger sync verifier; shows `{verified, broken_at_entry}` with timeline indicator
- `JournalEntryDetail` — full payload, hash, previous hash; cross-link to upload provenance
- `BFF /api/paysync/journal/*`

### 6.5 Wrapping existing surfaces

For each of `cycles/`, `batches/`, `carryovers/`, `invoices/`, `payment-runs/`, `bank-settlements/`, `reconciliations/`, `reports/`, `setup/`:
1. Copy or relocate the existing route pages into `surfaces/<name>/`
2. Replace direct imports of `@shared/lib/paysync-api` with the module's contract-layer adapter (so mock/real toggle works)
3. Add `RbacGate` wrappers around mutating buttons per the §5.4 matrix
4. Add `ProvenanceBreadcrumb` to detail pages showing upload chain
5. Register relevant Inbox item kinds in `ItemRegistry`

### 6.6 Module-local primitives (`components/`)

- `ProvenanceBreadcrumb` — renders `Upload #N → Cycle ... → Batch ... → Invoice ...` from any entity that carries an `upload_id`
- `MoneyDisplay` / `MoneyInput` — Decimal-safe; ROUND_HALF_UP per `.claude/rules/financial-precision.md`; rejects > 4 decimals on input
- `HashChainBadge` — green/amber/red verified state, click to open `HashChainVerifierPanel`
- `RbacGate` — declarative role check wrapping any action (`<RbacGate role="approver">...children...</RbacGate>`); soft-disables + tooltip on deny
- `RoleSwitcherChip` — qa-harness-only UI to toggle effective role in dev/staging builds. **Must be tree-shaken out of production bundles**: lives behind `qa-harness` package export which prod builds exclude per SP-0 §6.4. CI must fail if `RoleSwitcherChip` appears in any production `.next/static/` chunk.

### 6.7 `module.config.ts`

```ts
export default {
  id: 'paysync',
  routes: [/* one per surface */],
  rbac: {
    operator: ['paysync.upload', 'paysync.batch.draft', /* ... */],
    approver: [/* superset incl. commits */],
    auditor: ['paysync.read', 'paysync.journal.verify'],
  },
  inboxItemKinds: [
    { kind: 'upload_pending_review', card: () => import('./inbox/cards/UploadPendingReviewCard') },
    /* ... */
  ],
  navTree: {/* Inbox + History + Journal + Reports + Setup */},
} satisfies ModuleConfig;
```

---

## 7. Data flow

### 7.1 Canonical request — upload-driven processing

```
1. Operator uploads CSV in UploadDropzone
2. → multipart POST → portal/operator BFF /api/paysync/uploads
3. → contract client UploadsClient.create(multipartStream)
4. → POST /api/v1/billing/uploads (NEW backend resource)
5. → backend writes Upload row (status=parsing), dedups by sha256
6. → async parser dispatches by mime_type → writes claims with upload_id FK
7. → backend emits paysync.upload.parsed event with row_count + error_count
8. → Inbox revalidates via /api/paysync/inbox?role=operator → upload_pending_review item appears
9. → Operator clicks → UploadDetailPage shows parse status + row-error list
10. → Operator/Approver creates batch from upload (existing flow) → claims tagged batch_id, upload_id preserved
11. → Cycle close (existing) → AP/AR generation (existing) → NACHA + 835 files written, carry upload_id chain
12. → Bank settlement file imported → reconciliation matches → journal entry written (immutable, hash-chained)
13. → Auditor opens JournalLedgerView → click HashChainVerifierPanel → sync hash-chain verifier endpoint validates chain
```

### 7.2 Cache + invalidation
Per SP-0 §6.1 contract layer cache policy. Inbox items use short TTL (10s) + revalidate-on-focus. Mutations invalidate by cache-tag (`paysync:uploads`, `paysync:cycles`, `paysync:journal`, etc.) per SP-0 cache-tag pattern.

### 7.3 Mock/real toggle
Per SP-0 — each PaySync contract client has `RealImpl` + `MockImpl`. qa-harness UI flips per-domain at runtime. SP-1 ships both implementations for every new client; mocks return fixture data shaped identically to real.

### 7.4 Build-time composition
`infrastructure/manifests/operator.yml` adds `paysync` to the module list. SP-0's `scripts/generate-composition.ts` emits static import. SP-0's `scripts/audit-composition.ts` verifies the module is present in `.nft.json` and `.next/trace`.

---

## 8. Error handling

Inherits SP-0 §8 error envelope (`{error:{code, message, field?, correlation_id}}`). PaySync-specific rules:

| Failure mode | Behavior |
|---|---|
| Upload parse error | Row-level errors persisted on upload; viewable in UploadDetailPage; **never** poisons other uploads (data-model invariant per S9) |
| Upload validation failure | Upload status = `validation_failed`; not silently dropped; surfaces as `upload_pending_review` Inbox item with error count |
| Upload duplicate (sha256 match) | Backend returns 409 with existing upload reference; UI shows "Already uploaded — view existing" |
| RBAC denial | 403 + `RbacGate` soft-disables button with tooltip "Approver role required"; never hide |
| Backend down (read path) | SP-0 §8.3 stale-ok: last-known data + banner; cache TTL exhausted = error state with retry |
| Backend down (write path) | Always `fail-fast`; never optimistically commit money operations |
| Money precision | `MoneyInput` rejects > 4 decimals; backend Decimal validation per `.claude/rules/financial-precision.md`; ROUND_HALF_UP on display |
| Hash chain break | Verifier returns `{verified: false, broken_at_entry: 'abc...'}`; UI shows red `HashChainBadge` + escalation panel; **does not auto-repair** |
| Audit trail | Every mutation emits `audit.*` event; UI surfaces via existing `audit-log-timeline.tsx` |
| PHI safety | Per `.claude/rules/phi-compliance.md` — no PHI in error envelopes, no PHI in correlation_id, `Cache-Control: no-store` on PHI responses |
| Correlation ID | Per SP-0 §8.5 — thread end-to-end; surface in qa-harness inspector and in error toasts |

---

## 9. Testing

Per SP-0 §9 + project Auto-Gate + `.claude/rules/testing.md`.

### 9.1 Test layers

| Layer | Coverage |
|---|---|
| **Unit (frontend)** | Co-located `*.test.tsx` per existing pattern in `portal/operator/tests/unit/components/paysync/`; Vitest + RTL; all components incl. RBAC matrix per surface |
| **Unit (backend — Upload)** | `modules/billing/tests/unit/test_uploads.py` — parse CSV/Excel, sha256 dedup, row-error capture, upload_id propagation onto claims, supersede semantics |
| **Unit (backend — hash chain sync verifier)** | `modules/core-platform/tests/unit/test_verify_chain_sync.py` — verified, broken, empty cases |
| **Integration (BFF ↔ backend)** | Each BFF route in `packages/modules/paysync/src/bff/` against docker-compose backend; RBAC matrix per route (3 roles × N endpoints) |
| **E2E (the round trip per S5)** | Playwright: as Operator → upload CSV → validate; as Approver → cycle close → invoice send → payment run release → NACHA + 835 download; as Auditor → journal hash-chain verify. Runs against full docker-compose stack |
| **QA harness additions** | PaySync fixture seed button, role-switcher chip, request inspector overlay (per SP-0 §6.4) |

### 9.2 Coverage gates

Per `.claude/rules/testing.md`:
- 100% on financial logic (money, Decimal, payment amounts, journal entries)
- 100% on PHI paths (masking, access logging, encryption, tenant isolation)
- 100% on security paths (auth, RBAC enforcement, input validation)
- ≥95% branch coverage on all other active SP-1 code

### 9.3 Synthetic fixtures (`fixtures/paysync/`)

| File | Contents |
|---|---|
| `uploads/upload-001-healthy.csv` | 20 valid claims, single batch flow |
| `uploads/upload-002-validation-fail.csv` | 20 rows with intentional schema violations (bad NDC, bad date format) |
| `uploads/upload-003-half-bad.csv` | 30 rows, ~10 with row-level errors that should be reportable but not block the rest |
| `seeds/tenant.json` | 1 demo tenant — non-PHI synthetic |
| `seeds/cycles.json` | ~5 cycles in mixed states (open, closing, closed) |
| `seeds/invoices.json` | ~10 invoices across cycles |
| `seeds/payment-runs.json` | ~5 payment runs in mixed states |
| `seeds/reconciliations.json` | 1 reconciliation case with intentional discrepancy |
| `seeds/users.json` | 3 users — one each Operator/Approver/Auditor |

All fixtures generated to be **demonstrably non-PHI** per `.claude/rules/phi-compliance.md` — synthetic names from a public test-data corpus, synthetic addresses, no real NPIs (use 80840 + Luhn-valid invented suffix).

### 9.4 Performance posture

Per SP-0 D2:
- Inbox + list views = lightning (<150ms transition; <100ms search-as-you-type via virtualization)
- Cycle close report, journal viewer with full chain verify, period reports = honest first-paint + loading states

---

## 10. Open questions / plan-time decisions

These are intentionally deferred to the writing-plans phase. Listed here so the plan-writer knows to resolve them:

1. **Plan phasing strategy** — Approach C (Inbox-centric hybrid) locks the philosophy but not the per-plan sequence. Plan-writer should propose: Plan 1 (Inbox spine + Upload resource), Plan 2 (uploads + cycles wiring), Plan 3 (batches + AR/AP wiring), Plan 4 (files + journal), Plan 5 (reports + setup + E2E). Or similar; this is illustrative.
2. **Upload file storage strategy** — local disk for SP-1 (per §5.5); S3/blob backend deferred. Plan-writer chooses a directory layout + retention policy.
3. **CSV/Excel schema mapping** — SP-1 needs a minimum mandatory schema. Plan-writer defines it from existing claim model + a "source_platform" hint that lets future exports declare their dialect.
4. **Hash chain verifier perf budget** — for a journal with N entries, how long is "acceptable" for sync verification? Plan-writer should pick a bound (e.g., 5s for 10k entries) and decide whether long chains must use the existing job-based verifier instead.
5. **Inbox cache strategy specifics** — exact TTLs per item kind, websocket vs polling. Plan-writer decides; default polling at 10s with revalidate-on-focus.
6. **Module-extraction sequence** — wrapping the 11 existing surfaces is mechanical but per-surface. Plan-writer decides whether to bulk-extract or extract-per-surface as that surface is wired.

---

## 11. Cross-references

- SP-0 spec: `docs/superpowers/specs/2026-05-14-sp0-integration-foundation-design.md`
- SP-0 auth contract: `docs/superpowers/specs/2026-05-15-sp0-decision-spike-auth-interface.md` (SD-1)
- SP-0 composition: `docs/superpowers/specs/2026-05-15-sp0-decision-spike-composition.md` (SD-4)
- Project rules: `.claude/rules/{financial-precision,phi-compliance,security,tenant-isolation,event-bus,architecture,error-handling,testing,code-standards,hipaa-2026}.md`
- CLAUDE.md (root) — project status, principles, environment architecture
- Existing PaySync scaffolding: `portal/operator/app/admin/paysync/`, `portal/operator/app/accounting/`, `portal/operator/app/billing/`, `portal/operator/app/payments/`, `portal/operator/components/paysync/`, `portal/shared/lib/paysync-api.ts`
- Existing backend: `modules/billing/src/services/{ap,ar,journal,nacha,remittance_835,claims,routing,budget}.py`, `modules/payment-processing/src/services/nacha_generator.py`, `modules/edi-compliance/src/x12/generators/gen_835.py`, `modules/core-platform/src/jobs/verify_audit_chain_job.py`
