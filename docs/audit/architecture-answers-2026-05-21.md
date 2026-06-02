# Architecture Q&A — 2026-05-21

Investigator: sub-agent read-only audit
Scope: Q1 paysync/billing/accounting split; Q2 upload surfaces for paysync and reclaimrx

---

## Q1: Why are paysync and invoicing/accounting separate?

### 1a. The `billing` backend module (`modules/billing/`)

Source of truth: `docs/prd/prd-billing.md`

The billing backend is a Python/FastAPI service that owns ALL financial domain logic:

- Claims ingestion from three sources: adjudication engine events, external file upload, REST API
- AP (accounts payable): what the platform owes pharmacies — claim routing, payment batches, 835 remittances, NACHA files, settlement tracking, carryovers
- AR (accounts receivable): what clients owe the platform — invoicing cycles, invoice PDF generation, AR records, aging, client payment recording
- Financial journal: append-only ledger for every financial event, source of truth for accounting exports (QuickBooks, NetSuite, Sage, Xero, generic GL)
- Program budget monitoring, fee configs, funding/prefund ledger, bank accounts, payment vendor configs, SFTP configs

The billing module exposes `/api/v1/billing/` with ~50 endpoints. It does NOT know vendor-specific wire formats — that is payment-processing's job.

The `payment-processing` backend (`modules/payment-processing/`) is a second Python/FastAPI service that is the adapter layer only: receives `payment_batch.submitted` events from billing, formats them into NACHA/Echo Spec 400/Zelis JSON/check files, submits to vendors, tracks settlement, processes ACH returns (R01–R85), and emits settlement events back to billing. It knows zero billing logic. It generates zero invoices. (PRD: `docs/prd/prd-payment-processing.md`, §1 "What this module does NOT do".)

### 1b. The `paysync` frontend package (`packages/modules/paysync/`)

Paysync is the **operator-facing UI module** that surfaces billing + payment-processing data in the portal. It is not a backend. It is a React/Next.js package that:

- Declares 13 surfaces: uploads, cycles, batches, carryovers, invoices, payment-runs, files, bank-settlements, reconciliations, journal, reports, setup, echo
- Ships BFF route handlers (thin Next.js proxies) for each surface that forward auth tokens and call the billing/payment-processing backends
- Ships an inbox/approval-queue system (11 card types: `upload_pending_review`, `batch_drafted`, `ar_invoice_draft`, `ap_payment_run_held`, `banking_discrepancy`, etc.)
- Declares RBAC matrix for three roles: operator, approver, auditor
- Is registered in `packages/shell/src/_generated/manifest.json` as the module named `"paysync"`

`module.config.ts` makes the backend dependency explicit:
```
requires.backends: ["billing", "payment-processing", "core-platform"]
```

All 13 surfaces mount under `/admin/paysync/*`. The paysync navTree has five primary entries: Inbox, History, Journal, Reports, Setup.

### 1c. The portal `/accounting/*` pages vs `/admin/paysync/*` pages vs `/billing/*` pages

**Three separate sets of portal pages exist that all touch billing data:**

| Route prefix | What it is | Backend called | Status |
|---|---|---|---|
| `/admin/paysync/*` | Paysync module — full-featured operator workflow UI with approval inbox, RBAC, hash-chain audit, BFF proxies | `billing` + `payment-processing` via paysync BFF | Active — modules registered in manifest |
| `/accounting/*` | Standalone pages: cycles, journal-entries, nacha, payments | Direct `apiGet()` calls to billing/nacha endpoints | Active — parallel implementation |
| `/billing/*` | Older billing pages: cycles list/detail, claims, invoices | `@shared/lib/billing-api` → billing backend | Active — parallel implementation |

Evidence for the `/accounting/*` pages:
- `/accounting/cycles/page.tsx` calls `/api/v1/accounting/cycles/summary` and `/billing/v1/cycles`. Header reads "Billing Cycles" with breadcrumb "Accounting".
- `/accounting/journal-entries/page.tsx` calls `/api/v1/accounting/journal-entries`. Header reads "Journal Entries" with breadcrumb "Accounting".
- `/accounting/nacha/page.tsx` calls `/nacha` and `/nacha/{id}/transmit`. Header reads "NACHA Files" with breadcrumb "Accounting".
- `/accounting/payments/page.tsx` calls `/api/v1/payments/dashboard` and `/batches`. Header reads "Payments & Batches" with breadcrumb "Accounting".

Evidence for the `/billing/*` pages:
- `/billing/page.tsx` — billing cycles DataTable, calls `@shared/lib/billing-api:listCycles`, links to `/billing/cycles/new`.
- `/billing/invoices/` and `/billing/claims/` are also present.

### Verdict: Intentional Domain Separation + Accidental UI Drift

The **backend split (billing vs payment-processing) is intentional design** — a clean adapter pattern documented in both PRDs. Billing owns financial logic; payment-processing owns vendor wire formats. This is architecturally sound.

The **paysync frontend module is intentional design** — it is the approved operator workflow layer with RBAC, approval inbox, BFF proxies, and hash-chain audit badge. It surfaces billing + payment-processing under a single operator-facing nav entry.

The **`/accounting/*` and `/billing/*` portal pages are unintentional drift** — they are standalone page.tsx files that call billing endpoints directly, bypassing the paysync BFF, bypassing the paysync RBAC matrix, and duplicating UI that paysync already has (cycles, journal entries, NACHA, payments). The `/accounting/cycles` page and `/admin/paysync/cycles` surface both show billing cycles from the same backend. The `/accounting/journal-entries` page and `/admin/paysync/journal` surface both show journal entries. There is no PRD or blueprint reference that justifies a separate `/accounting/*` nav tree.

**Correct mental model:**

- **billing** = the financial domain backend (AP, AR, journal, invoicing, NACHA, 835, routing rules). One Python service.
- **payment-processing** = the vendor adapter backend (formats payment files, submits to Echo/Zelis/ACH, tracks settlement/returns). One Python service. Downstream of billing.
- **paysync** = the operator portal UI module that wraps both backends with RBAC, approval inbox, BFF, and hash-chain audit. All operator financial workflow should flow through `/admin/paysync/*`.
- **`/accounting/*` and `/billing/*`** = drift — these pages call the same backends directly without the paysync RBAC/audit layer. They should be consolidated into paysync surfaces or deleted.

---

## Q2: "I don't see a way to upload data to paysync or reclaimrx"

### 2a. Paysync uploads

**Build state of the uploads surface:**

The uploads surface is fully built in the paysync package:

- `packages/modules/paysync/src/surfaces/uploads/UploadsListPage.tsx` — complete list view with status badges, dedup banner, MoneyDisplay, linked rows
- `packages/modules/paysync/src/surfaces/uploads/UploadDropzone.tsx` — drag-and-drop file uploader
- `packages/modules/paysync/src/surfaces/uploads/UploadDetailPage.tsx` — detail view with row-level error display
- `packages/modules/paysync/src/surfaces/uploads/UploadClaimViewer.tsx` — claim row viewer for a parsed upload
- `packages/modules/paysync/src/surfaces/uploads/bff/uploads.ts` — four BFF handlers: `handleListUploads`, `handleGetUpload`, `handleGetUploadClaims`, `handleCreateUpload` (with 409/dedup handling)
- `packages/modules/paysync/src/surfaces/uploads/index.ts` — exports all four components and all four BFF handlers; declares `UploadsSurface = { id: "uploads", path: "/admin/paysync/uploads" }`

**Export state:**

`packages/modules/paysync/src/index.ts` line 50 explicitly exports `UploadsSurface`. All four page components and four BFF handlers are re-exported from the surface index. The surface is fully exported from the package public API.

The paysync `module.config.ts` `routeSurfaces` map includes:
```
"/admin/paysync/uploads": "uploads"
"/admin/paysync":         "uploads"   // Inbox at index also maps to uploads surface
```

The paysync inbox includes `upload_pending_review` and `upload_validated_awaiting_batching` card kinds, registered in `paysyncComposition.inboxItemKinds`.

**Mounted state — MISSING:**

The route `/admin/paysync/uploads` is declared in `module.config.ts` routes array but there is **no `portal/operator/app/admin/paysync/uploads/` directory and no `page.tsx` file** for it. The portal filesystem at `portal/operator/app/admin/paysync/` contains only:

```
page.tsx          (dashboard — mounts getPaysyncDashboard, links to /admin/paysync/cycles etc.)
echo/             (page.tsx present)
reports/          (page.tsx + cycles/ + journal/ + period/ subdirs)
setup/            (page.tsx + 5 subdirs)
```

There is no `uploads/` subdirectory and no `page.tsx` mounting `UploadsListPage` or `UploadDropzone`.

Additionally, the paysync `navTree.primary` in `module.config.ts` lists five entries (Inbox, History, Journal, Reports, Setup) — "History" links to `/admin/paysync/uploads`, but that page does not exist.

**Exact missing wiring:**

1. Create `portal/operator/app/admin/paysync/uploads/page.tsx` — a Next.js page that imports `UploadsListPage` and `UploadDropzone` from `@infinityrx/module-paysync`, wires the four BFF handlers into `/app/api/paysync/uploads/route.ts` and `/app/api/paysync/uploads/[id]/route.ts`, and uses TanStack Query to call them.
2. Create `portal/operator/app/admin/paysync/uploads/[id]/page.tsx` mounting `UploadDetailPage` and `UploadClaimViewer`.
3. Create the corresponding `/app/api/paysync/uploads/` API route files that call `handleListUploads`, `handleGetUpload`, `handleGetUploadClaims`, `handleCreateUpload` from the BFF module.

The nav entry ("History" → `/admin/paysync/uploads`) is already declared in `module.config.ts` — no nav change needed.

### 2b. ReclaimRx uploads

**Surface inventory:**

`packages/modules/reclaimrx/module.config.ts` declares routes:
```
/reclaimrx, /reclaimrx/dashboard, /reclaimrx/investigations, /reclaimrx/investigations/[id],
/reclaimrx/holds, /reclaimrx/fraud-rings, /reclaimrx/fraud-rings/[id],
/reclaimrx/graph-runs, /reclaimrx/thresholds, /reclaimrx/accumulator-anomalies
```

There is no `packages/modules/reclaimrx/src/surfaces/` directory (the reclaimrx package has only `module.config.ts` at its root — no surface package like paysync). The portal pages at `portal/operator/app/reclaimrx/` include: accumulator-anomalies, dashboard, fraud-rings, graph-runs, holds, investigations, leakage, page.tsx (GTN dashboard), recovery, risk, tests, thresholds, wizard. No upload page exists there.

**By-design verdict — no upload UI, and the PRD explicitly explains why:**

`docs/prd/prd-reclaimrx.md` §1 states ReclaimRx operates at two speeds:

1. **Real-time detection** — during adjudication (Module 8), via a direct API call `/api/v1/reclaimrx/evaluate`. Claims flow in from the adjudication engine automatically.
2. **Post-adjudication detection** — batch analysis of historical claims from the claims pipeline.

The consumed events in the PRD (§9) are: `claim.adjudicated`, `claim.reversed`, `ap.created`, `ap.settled`, `exclusion.match_found`, `pharmacy.application_submitted`, `pharmacy.ownership_changed`. All are event-bus driven from the claims pipeline — not from manual file upload.

The PRD's data-entry model is explicit: "Claims enter from three configurable sources: Internal (adjudication), External upload, API" — and that "External upload" entry point belongs to the **billing** module's claims ingestion pipeline (billing PRD §3.1), not to reclaimrx directly. Once claims are ingested into billing (via the billing upload surface — which is the paysync `UploadsSurface` described above), they emit `claim.ingested` → `claim.adjudicated` events that reclaimrx consumes.

ReclaimRx has no need for its own upload UI because it sits downstream of billing's ingestion pipeline. The "upload" for external claims data goes through paysync (`/admin/paysync/uploads`), which feeds the billing backend, which emits events that reclaimrx consumes. This is by-design, not missing wiring.

The reclaimrx portal does have the `wizard` page (`/reclaimrx/wizard`) for manually opening new FWA cases/investigations — that is its data-entry surface.

---

## Summary Table

| Concept | Backend | Portal Route | State |
|---|---|---|---|
| Claims ingestion + AP + AR + journal | `modules/billing` | `/admin/paysync/*` (via paysync BFF) | Correct home |
| Payment vendor submission | `modules/payment-processing` | `/admin/paysync/*` (via paysync BFF) | Correct home |
| `/accounting/*` pages | Same billing backend, direct calls | `/accounting/cycles`, `/accounting/journal-entries`, `/accounting/nacha`, `/accounting/payments` | DRIFT — duplicate, no RBAC |
| `/billing/*` pages | Same billing backend, direct calls | `/billing`, `/billing/cycles`, `/billing/invoices`, `/billing/claims` | DRIFT — duplicate, no RBAC |
| Paysync uploads surface | billing uploads API | `/admin/paysync/uploads` (declared, inbox cards present) | BUILT + EXPORTED, page.tsx MISSING |
| ReclaimRx uploads | N/A — event-bus consumer only | None | BY DESIGN — no upload UI needed |

---

Q1_VERDICT: The billing/payment-processing backend split is intentional and clean — billing owns all financial logic (AP, AR, journal, invoicing, NACHA, 835), payment-processing is a pure vendor-adapter layer downstream. Paysync is the intentional operator UI module that wraps both backends under `/admin/paysync/*` with RBAC, approval inbox, BFF, and audit. The `/accounting/*` and `/billing/*` portal pages are accidental drift — standalone page.tsx files that call the same billing backend directly, bypassing paysync's RBAC and audit layer, and duplicating surfaces (cycles, journal entries, NACHA, payments) that paysync already owns. The correct mental model: billing = financial domain backend, payment-processing = vendor wire-format adapter, paysync = the one operator UI that surfaces both, `/accounting/*` and `/billing/*` = drift to be consolidated into paysync or deleted.

Q2_PAYSYNC_UPLOAD: Fully built and exported — UploadsListPage, UploadDropzone, UploadDetailPage, UploadClaimViewer, and four BFF handlers all exist in `packages/modules/paysync/src/surfaces/uploads/`, are exported from `src/index.ts`, and the route `/admin/paysync/uploads` is declared in `module.config.ts` with a nav entry ("History"). The exact missing wiring: (1) `portal/operator/app/admin/paysync/uploads/page.tsx` mounting UploadsListPage + UploadDropzone; (2) `portal/operator/app/admin/paysync/uploads/[id]/page.tsx` mounting UploadDetailPage + UploadClaimViewer; (3) corresponding `portal/operator/app/api/paysync/uploads/route.ts` and `[id]/route.ts` calling the four BFF handlers. No nav or package changes needed — the nav entry and exports are already in place.

Q2_RECLAIMRX_UPLOAD: By design — no upload UI is missing. ReclaimRx is an event-bus consumer: it ingests `claim.adjudicated`, `claim.reversed`, `ap.created`, and `ap.settled` events from the claims pipeline (prd-reclaimrx.md §9). The PRD explicitly describes two data paths — real-time adjudication API calls and post-adjudication batch analysis — both fed by the claims pipeline, not by manual upload. External claim file uploads enter through the billing module's ingestion pipeline (prd-billing.md §3.1) via the paysync uploads surface, emit `claim.ingested` events, and reclaimrx consumes downstream. ReclaimRx's own data-entry surface is the investigation wizard (`/reclaimrx/wizard`) for opening FWA cases manually.

REPORT_PATH: docs/audit/architecture-answers-2026-05-21.md
