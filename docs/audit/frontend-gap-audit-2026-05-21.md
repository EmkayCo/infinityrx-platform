# Frontend Gap Audit — Operator Portal — 2026-05-21

**Trigger:** Operator report — "things don't work as we scoped and designed; e.g. no way to upload data to paysync or reclaimrx; paysync vs invoicing/accounting confusing."

**Method:** 3 parallel read-only sub-audits. Detail in:
- `docs/audit/portal-surface-inventory-2026-05-21.md` — what the portal actually mounts + nav.
- `docs/audit/designed-scope-matrix-2026-05-21.md` — what the PRDs scoped, per module.
- `docs/audit/architecture-answers-2026-05-21.md` — paysync/billing/accounting boundary + upload-flow analysis.

---

## Headline finding

The module **packages were built** — surfaces, components, BFF handlers, inbox cards — and **exported**, but the **portal mounting layer was never completed** for large swaths. Mounting layer = `app/**/page.tsx` (mount the surface) + `app/api/**/route.ts` (call the BFF) + nav manifest entry + `src/index.ts` export. Mike's "no upload" is one instance of a systemic "built-but-not-wired" pattern.

Three failure shapes:
1. **Built-but-not-mounted** — package surface exists + exported, but no `page.tsx`/`route.ts` mounts it (paysync: 11 surfaces).
2. **Built-but-not-exported** — surface source exists in the package but not in `src/index.ts`, so nothing can import it; module absent from manifest (reclaimrx surface layer).
3. **Nav-to-nowhere** — nav entry points at a route with no `page.tsx` → 404 on click (prescriber-directory `/prescribers`).

---

## Architecture answers (Mike's questions)

### Q: Why are paysync and invoicing/accounting separate?
They are **not separate domains.** One billing domain, one brand name, one subsystem:
- **paysync** = IFX product/brand name for the operator UI surface. Not a backend module. `module.config.ts` bridges backends `billing` + `payment-processing`.
- **billing** (backend) = engine: AP, AR, claims ingest, invoices, financial **journal**, NACHA, 835.
- **payment-processing** (backend) = vendor wire-format execution only (Echo/Zelis/NACHA/check). Billing decides who gets paid; payment-processing does the paying.
- **accounting** = subsystem of billing (journal + GL exports to QuickBooks/NetSuite/etc.). Surfaced via paysync Journal + Reports screens. No separate accounting module.

**The confusion is real and is DRIFT:** the portal has standalone `/accounting/*` and `/billing/*` `page.tsx` trees that call the billing backend **directly**, bypassing paysync's RBAC / audit / inbox layer, duplicating surfaces (cycles, journal, NACHA, payments) that paysync already owns. Correct mental model: **billing = backend domain, payment-processing = vendor adapter, paysync = the single operator UI, `/accounting/*` + `/billing/*` = drift to consolidate into paysync or delete.**

### Q: Why no way to upload data to paysync / reclaimrx?
- **paysync upload:** fully built + exported (`UploadsListPage`, `UploadDropzone`, `UploadDetailPage`, `UploadClaimViewer`, `handleCreateUpload` BFF). **Not mounted** — no `page.tsx`, no `route.ts`, no nav link. Built-but-not-wired.
- **reclaimrx upload:** **by design, none.** reclaimrx is an event-bus consumer (`claim.adjudicated`, `claim.reversed`, `ap.created`, `ap.settled`). Claim files enter via **billing** ingestion (the paysync uploads surface) → emit events → reclaimrx consumes. Manual surface = investigation wizard, not upload. No missing wiring for upload.

---

## Gap matrix — built-but-not-wired

### paysync (`packages/modules/paysync`) — 11 surfaces built + exported, NOT mounted
| Surface | Components (built+exported) | Missing portal mount |
|---|---|---|
| Uploads | UploadsListPage, UploadDropzone, UploadDetailPage, UploadClaimViewer | `/admin/paysync/uploads` page + `[id]` + `api/paysync/uploads` route |
| Cycles | CyclesListPage, CycleDetailPage | `/admin/paysync/cycles` (+`[id]`) |
| Batches | BatchesListPage, BatchDetailPage | `/admin/paysync/batches` (+`[id]`) |
| Carryovers | CarryoversListPage, CarryoverDetailPage | `/admin/paysync/carryovers` (+`[id]`) |
| Invoices | InvoicesListPage, InvoiceDetailPage | `/admin/paysync/invoices` (+`[id]`) |
| Payment Runs | PaymentRunsListPage, ManualApForm | `/admin/paysync/payment-runs` |
| Files | FilesListPage, FileDetailPage, FileGenerateForm | `/admin/paysync/files` (+`[id]`) |
| Settlements | BankSettlementsSurface | `/admin/paysync/settlements` |
| Reconcile | ReconciliationsSurface | `/admin/paysync/reconcile` |
| Journal | JournalListPage, JournalDetailPage, HashChainVerifyButton | `/admin/paysync/journal` |
| Inbox | InboxQueue + 11 inbox cards | `/admin/paysync` index is a hand-rolled KPI dash; does not mount InboxQueue |

All 11 declared in `paysync/module.config.ts`; only `echo`, `reports/*`, `setup/*` exist as actual pages.

### reclaimrx (`packages/modules/reclaimrx`) — surface layer built, NOT exported
- `src/{investigations,holds,recovery,graph,ml,rules,rbac}/` exist as source.
- **None exported from `src/index.ts`.** Module **absent from `manifest.json`** → no nav entry.
- Any working reclaimrx UI today is hand-rolled outside the package (NEEDS VERIFICATION: confirm what `/reclaimrx/*` routes actually render and whether reachable in nav).

### prescriber-directory — nav-to-nowhere
- Nav entry → `/prescribers`, but no `portal/operator/app/prescribers/page.tsx`. Clicking 404s. (Note: prescriber lookup also exists under consolidated `/directories/prescribers` — the standalone `/prescribers` config is likely dead/duplicate.)

### Architecture drift — duplicate billing surfaces
- `/accounting/*` (cycles, journal-entries, nacha, payments) and `/billing/*` call billing backend directly, bypassing paysync RBAC/audit. Duplicate paysync's owned surfaces.

---

## Designed-but-unverified upload flows (from PRDs — wiring not yet checked)
PRDs scope upload UIs also for: billing cycle wizard (claims file), member-management (834/CSV enrollment), medical-claims (OCR paper claims), plan-design (bulk plan import), program-config (BRD docs + bulk NDC), prior-auth (appeal docs), rules-engine (BRD config file), pharmacy-directory (credentialing docs), directories (`/directories/ingestion` reference feeds). Each needs the same built-vs-wired check paysync got.

---

## Recommended fix waves (audit-first → approved waves)

**Wave G1 — paysync wiring (highest impact, lowest risk).** Mount the 11 built paysync surfaces: add `page.tsx` + `route.ts` per surface, point at existing BFF handlers, add nav entries. No new business logic — pure wiring of already-built+tested code. Unblocks uploads, cycles, invoices, journal, etc.

**Wave G2 — reclaimrx package wiring.** Export surfaces from `src/index.ts`, register in `manifest.json`, add nav + pages. Bigger (verify hand-rolled vs package UI first; decide consolidate vs keep).

**Wave G3 — drift cleanup.** Decide `/accounting/*` + `/billing/*`: consolidate into paysync or delete. Architecture decision, needs Mike.

**Wave G4 — prescriber `/prescribers` 404.** Either point nav to `/directories/prescribers` or mount the page. Small.

**Wave G5 — sweep remaining modules.** Run the built-vs-wired check on the 9 PRD-scoped upload flows + all Phase-5 "Coming Soon" modules.

---

_Generated 2026-05-21 from 3 read-only sub-audits. No code modified._
