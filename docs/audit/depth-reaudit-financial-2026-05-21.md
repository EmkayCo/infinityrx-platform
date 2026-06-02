# Financial Core Depth Re-Audit — 2026-05-21

**Scope:** billing module portal surfaces, payment-processing portal surfaces, paysync package surfaces, and portal sections /accounting, /billing, /admin/paysync.  
**Designed-scope sources:** prd-operator-portal.md §6/§7/§9, prd-billing.md, prd-payment-processing.md.  
**Auditor methodology:** read PRD sections for designed spec, read every built file, classify each designed surface.

---

## Surface Classification Table

| Surface | Designed? (PRD ref) | Build State | Effort | Note |
|---|---|---|---|---|
| **BILLING SECTION — /billing/** | | | | |
| /billing (cycles list) | §7.2, prd-billing §3.4 | SCAFFOLD | M | DataTable present, CSV export, status badges. Missing: TanStack virtual scroll, per-column filters, bulk actions bar (§9.2), multi-sort (§9.1), column reordering/visibility, share-link export, density toggle. Uses simpler `DataTable` not `ConfigurableDataTable`. |
| /billing/cycles/new (6-step wizard) | §7.1, §7.2 | BUILT_WIRED | S | All 6 steps exist (Upload→Map→Validate→Preview→Approve→Generate). Auto-save to localStorage, draft resume, two-person approval threshold at $1M, anomaly flags in preview, NACHA transmit in step 6. Missing: "Save Draft" to server (localStorage only), second-approver notification API call uses STUB_APPROVERS not live /users endpoint. |
| /billing/cycles/[id] (cycle detail) | §7.2 step 5/6, prd-billing | SCAFFOLD | M | Shows timeline, financial summary (AP/AR/fees), artifact download + NACHA transmit button. Missing: full tabbed view (claims/AR/AP/journal/SaaSant/835/NACHA preview tabs) — these exist in /accounting/cycles/[id] but NOT here; approve/reject/generate/settle mutations absent; anomaly flags absent. Two parallel implementations exist — this one (dark theme) is reachable from /billing, the /accounting version is the complete one. |
| /billing/claims | prd-billing §3.1 | SCAFFOLD | M | Page file exists. Not read in detail but nav routes here. Likely claims list without full §9.1 table spec. |
| /billing/invoices | prd-billing §3.5 | SCAFFOLD | M | Invoice list with status badges, DollarCell, export CSV. Missing: §9 table features, send-invoice action, AR aging view, client payment recording. |
| /billing/invoices/[id] | prd-billing §3.5 | SCAFFOLD | M | Detail page exists. Full invoice workflow (mark paid, send, void) not confirmed built. |
| **ACCOUNTING SECTION — /accounting/** (nav-config canonical) | | | | |
| /accounting/cycles (cycles list) | §7.2, prd-billing | BUILT_WIRED | S | Full ConfigurableDataTable with pinned columns, KPI cards (total, pending approval, AP, AR), column show/hide, date format, status format. Calls /billing/v1/cycles. Better than /billing equivalent. |
| /accounting/cycles/[id] (cycle detail) | §7.2 steps 4–6, prd-billing | BUILT_WIRED | M | 7 tabs (claims/AR/AP/journal/SaaSant preview/835 preview/NACHA preview), approve/reject/generate/settle mutations, anomaly flags, comparison delta (prev cycle), InfoCard layout. SaaSant/835/NACHA previews use computed mock ratios, not real artifact data. Missing: real artifact download links in tabs (only in artifact list), two-person MFA re-verify on high-value approve. |
| /accounting/payments (payment batches) | §7.3, prd-payment-processing | BUILT_WIRED | S | ConfigurableDataTable, KPI summary cards, vendor/status/amount columns, settled_at. Missing: §9 bulk actions, new-batch entry point absent from this page (links to /payments for wizard). |
| /accounting/nacha | prd-payment-processing | SCAFFOLD | M | NACHA file list with filename/status/amounts/transmit/download. Transmit button via apiPost. Missing: §9 table features, ACH return processing UI, bank ack status detail. |
| /accounting/journal-entries | prd-billing §3.6 | SCAFFOLD | M | ConfigurableDataTable with date/type/description/debit/credit/amount/QB-class columns, KPI summary cards. Missing: hash chain integrity indicator, export to QuickBooks/NetSuite flow, period filtering, §9 bulk actions. |
| /accounting/invoices | prd-billing §3.5 | NOT_BUILT | S | nav-config lists it (/accounting/invoices) but no page file exists. The /billing/invoices page exists under a different path — the nav-config canonical path is dead. |
| **PAYMENTS SECTION — /payments/** | | | | |
| /payments (batch list) | §7.3, prd-payment-processing | SCAFFOLD | M | DataTable with status/vendor/amounts/ack. Missing: §9 table features (virtual scroll, bulk, multi-sort, column config), settlement detail drill-down, return code display. Older dark-theme `DataTable` not `ConfigurableDataTable`. |
| /payments/batches/new (batch wizard) | §7.3 | BUILT_UNWIRED | M | 5-step PaymentBatchWizard exists (select claims → review routing → generate files → approve → transmit). "New Batch" button on /payments page routes to /payments/batches/new but no page file exists at that path. Wizard component built but mount page missing. |
| /payments/nacha | prd-payment-processing | SCAFFOLD | L | Hand-rolled static HTML table (no DataTable component, no TanStack Query, no real data fetch). Shell placeholder — no data wiring at all. |
| **PAYSYNC PACKAGE — packages/modules/paysync/src/** | | | | |
| Uploads list + dropzone | prd-operator-portal §7.2 step 1 | BUILT_WIRED | S | UploadsListPage + UploadDropzone mounted at /admin/paysync/uploads. SHA-256 dedup, 409 banner, progress bar, RBAC disabled state, CSV/XLSX only. TanStack Query wired. Complete. |
| Upload detail + claim viewer | prd-operator-portal §7.2 step 3 | BUILT_WIRED | S | UploadDetailPage + UploadClaimViewer mounted at /admin/paysync/uploads/[id]. Validation result display, row errors. |
| Cycles list | prd-billing §3.4 | BUILT_UNWIRED | L | CyclesListPage component exists in paysync package (plain HTML table, MoneyDisplay, status badge). Exported from index.ts. NO mount page at /admin/paysync/cycles — nav-config links to this route but it 404s. Paysync CyclesListPage is also far below spec: no KPI cards, no ConfigurableDataTable, no pagination controls beyond basic. |
| Cycle detail | prd-billing §3.4 | BUILT_UNWIRED | L | CycleDetailPage in paysync package. ProvenanceBreadcrumb, RbacGate on close button, MoneyDisplay. No mount page. Also presentational-only — no data fetching built into component (caller must supply props). |
| Batches list | prd-payment-processing | BUILT_UNWIRED | L | BatchesListPage + BatchDetailPage in paysync package. No mount page at /admin/paysync/batches — nav-config links to this route but 404s. |
| Invoices list + detail | prd-billing §3.5 | BUILT_UNWIRED | L | InvoicesListPage + InvoiceDetailPage in paysync package. No mount page at /admin/paysync/invoices — nav-config links to this but 404s. |
| Reconciliations list + detail | prd-billing | BUILT_UNWIRED | L | ReconciliationsListPage + ReconciliationDetailPage in paysync package. No mount page at /admin/paysync/reconciliations — nav-config links to this but 404s. |
| Carryovers list + detail | prd-billing | BUILT_UNWIRED | L | CarryoversListPage + CarryoverDetailPage in paysync package. No mount page at /admin/paysync/carryovers — nav-config links to this but 404s. |
| Bank Settlements list + detail | prd-payment-processing | BUILT_UNWIRED | L | BankSettlementsListPage + BankSettlementDetailPage in paysync package. No mount page at /admin/paysync/bank-settlements — nav-config links to this but 404s. |
| Payment Runs (manual AP) | prd-billing §3.3 | BUILT_UNWIRED | L | PaymentRunsListPage + PaymentRunDetailPage + ManualApForm in paysync package. No mount page at /admin/paysync/manual-ap — nav-config links to this but 404s. |
| Files (generated output files) | prd-billing, §7.2 step 6 | BUILT_UNWIRED | M | FilesListPage + FileDetailPage + FileGenerateForm in paysync package. Not mounted. |
| Journal (paysync journal view) | prd-billing §3.6 | BUILT_UNWIRED | M | JournalListPage + JournalDetailPage + HashChainVerifyButton in paysync package. Not mounted. The /accounting/journal-entries is a separate implementation without hash chain verify. |
| **ADMIN/PAYSYNC SURFACE — /admin/paysync/** | | | | |
| /admin/paysync (dashboard) | §6.1 Billing Operations preset | BUILT_WIRED | M | KPI cards (open cycles, pending close, pending reconciliation, banking discrepancies, open carryovers), quick-action cards, recent activity feed. Links go to routes that 404. Missing: widget drag-resize (§6.2), SSE activity feed (§6.3), preset selection. |
| /admin/paysync/echo | prd-payment-processing vendor adapters | BUILT_WIRED | S | Echo Spec 400 operations page — lists runs, sha256 hashes, manual trigger. Wired. |
| /admin/paysync/reports | prd-billing §3.6 | BUILT_WIRED | S | ReportsListPage from paysync package — mounted and reachable. |
| /admin/paysync/reports/cycles | prd-billing | BUILT_WIRED | S | CycleReportsPage mounted. |
| /admin/paysync/reports/journal | prd-billing §3.6 | BUILT_WIRED | S | JournalEntriesReportPage mounted. |
| /admin/paysync/reports/period | prd-billing | BUILT_WIRED | S | PeriodSummaryPage mounted. |
| /admin/paysync/setup | §7.4 client onboarding config | BUILT_WIRED | S | SetupHomePage from paysync package — thin shell, but mounted. |
| /admin/paysync/setup/cycle-schedules | prd-billing §3.8 | BUILT_WIRED | S | CycleSchedulesPage mounted. |
| /admin/paysync/setup/export-templates | prd-billing | BUILT_WIRED | S | ExportTemplatesPage mounted. |
| /admin/paysync/setup/email-templates | prd-billing | BUILT_WIRED | S | EmailTemplatesPage mounted. |
| /admin/paysync/setup/email-recipients | prd-billing | BUILT_WIRED | S | EmailRecipientsPage mounted. |
| /admin/paysync/setup/gl-account-mappings | prd-billing §3.6 | BUILT_WIRED | S | GlAccountMappingsPage mounted. |
| /admin/paysync/setup/invoice-sequences | prd-billing §3.5 | BUILT_WIRED | S | InvoiceSequencesPage mounted. |
| **DESIGNED FRAMEWORK SURFACES (§6/§7/§9)** | | | | |
| Dashboard — customizable widget grid (§6.2) | §6.2 | NOT_BUILT | L | No drag-resize widget grid exists. /admin/paysync dashboard has fixed KPI cards only. |
| Dashboard — SSE activity feed (§6.3) | §6.3 | NOT_BUILT | L | No SSE connection in any financial dashboard page. |
| Dashboard presets — 4 layouts (§6.1) | §6.1 | NOT_BUILT | M | No preset selection UI. Single fixed layout. |
| Universal wizard framework (§7.1) | §7.1 | BUILT_WIRED | — | WizardContainer + useWizard + WizardConfig in @shared/components/wizard. Step sidebar, auto-save, back nav, validation gates all implemented. Used by billing-cycle-wizard and payment-batch-wizard. Missing: server-side draft persistence (localStorage only). |
| Two-person approval flow (§8.1) | §8.1 | SCAFFOLD | M | ApprovalFlow component imported in step 5. Threshold check at $1M exists. STUB_APPROVERS hardcoded — not fetched from /users API. MFA re-verification on approve not implemented. No rejection reason flow. |
| Undo/rollback toasts (§8.2) | §8.2 | NOT_BUILT | M | No toast-undo pattern on any financial operation. Standard toasts used but without undo action or 30s window. |
| Dollar amount confirmation dialogs (§8.3) | §8.3 | SCAFFOLD | S | DollarDisplay with showScale prop exists. Large-font verbal description ("thirteen million...") absent. Color scale on >$1M not implemented. |
| TanStack Table §9.1 full spec | §9.1 | SCAFFOLD | L | ConfigurableDataTable exists and used on accounting pages. Missing from all financial tables: virtual scrolling, column reordering via drag, density toggle. Filtering is pagination-only. Multi-sort absent. |
| Bulk actions bar (§9.2) | §9.2 | NOT_BUILT | L | No floating bulk action bar on any financial table. Checkbox columns absent. |
| Export menu full spec (§9.3) | §9.3 | SCAFFOLD | M | ExportMenu exists with CSV. Excel/PDF/Clipboard/Share-link not implemented. |
| Client onboarding wizard (§7.4) | §7.4 | SCAFFOLD | L | client-onboarding-wizard/index.tsx exists but not read in depth. 7-step spec. Likely skeleton. |
| Investigation wizard (§7.5) | §7.5 | SCAFFOLD | — | investigation-wizard/index.tsx exists. ReclaimRx scope — out of financial core. |

---

## Key Structural Findings

### Nav Duplication / Structural Rot

The portal has **three parallel navigation sources** in conflict:

1. **`nav-config.ts`** — canonical sidebar source, references `/admin/paysync/cycles`, `/admin/paysync/batches`, `/admin/paysync/reconciliations`, `/admin/paysync/carryovers`, `/admin/paysync/bank-settlements`, `/admin/paysync/manual-ap` — all of which **404 in production** (no page.tsx exists).

2. **`packages/shell/src/_generated/manifest.json`** — generated shell manifest (modified per git status). Separate from nav-config.

3. **`packages/modules/paysync/module.config.js`** — module navTree (generated artifact per git status, `.js` + `.d.ts` files untracked). Not integrated into nav-config.ts per observation 2845.

4. **`/billing/**` vs `/accounting/**` drift** — two complete but divergent implementations of billing cycles exist. `/billing/cycles` uses the older dark-theme DataTable + DollarCell pattern. `/accounting/cycles` uses ConfigurableDataTable + KpiCardRow + the correct nav-config path. Nav-config routes to `/accounting/*` but the billing wizard at `/billing/cycles/new` routes back to `/billing` on completion — operators finish a wizard and land on a page the sidebar doesn't highlight.

5. **No `/admin/paysync/uploads` in nav-config** — the uploads route is implemented and working but absent from nav-config's PaySync children list. Operators cannot discover it via sidebar.

### Wizard Framework Assessment

The §7.1 universal wizard framework **does exist** as a shared component (`WizardContainer`/`useWizard`). The billing cycle wizard is the most complete implementation — all 6 steps built and wired. The payment batch wizard has 5 steps built but its mount page is missing. The framework is real infrastructure, not throwaway.

### Paysync Package Surfaces — Presentational Architecture

All paysync package surfaces (cycles, batches, invoices, reconciliations, carryovers, bank-settlements, payment-runs, journal) are **purely presentational** — they accept data via props and fire callbacks. Data fetching must be done in the portal mount page. This is a clean architecture (testable, portable) but means each unmounted surface requires both a mount page AND a BFF handler to become reachable. The uploads surface is the reference pattern: portal page does TanStack Query + BFF fetch, passes data to the paysync component.

---

## Reusability Assessment

**Paysync package primitives (MoneyDisplay, HashChainBadge, MoneyInput, ProvenanceBreadcrumb, RbacGate):** Genuinely reusable. Correctly typed, prop-based, tested. These are salvageable in any rebuild.

**Paysync inbox cards (12 cards):** Well-structured, purpose-built. Reusable.

**Paysync surface page components (CyclesListPage, BatchDetailPage, etc.):** Reusable as presentational shells but currently below §9.1 table spec — they render plain HTML tables, not ConfigurableDataTable. A rebuild to spec would need to replace their inner table with ConfigurableDataTable or accept that paysync surfaces use a different table pattern than accounting pages.

**Portal billing wizard (BillingCycleWizard, PaymentBatchWizard):** Reusable — built on the shared wizard framework. The step components are substantial implementations worth keeping.

**Portal accounting pages (/accounting/cycles, /accounting/cycles/[id]):** The most complete financial surface implementations. Worth keeping as the canonical pattern.

**Portal /billing/** pages:** Lower quality than /accounting/ equivalents — older component pattern, no KPI cards, less feature-complete. If /accounting/ is the canonical path (per nav-config), the /billing/ pages are redundant drift.

---

## Summary Counts

```
COUNTS: NOT_BUILT=7, SCAFFOLD=16, BUILT_UNWIRED=11, BUILT_WIRED=15  (out of 49 designed surfaces)

EFFORT_TOTAL: ~38–52 person-days to reach designed state for this cluster
  Breakdown:
  - Mount 8 unmounted paysync surfaces (cycles/batches/invoices/reconciliations/
    carryovers/bank-settlements/payment-runs/journal): ~8d
  - Fix /payments/batches/new missing mount page: ~0.5d
  - Fix /accounting/invoices missing mount page: ~0.5d
  - Add uploads to nav-config: ~0.25d
  - Fix nav-config dead links (6 routes): ~1d after mounts done
  - §9.1 TanStack table full spec (virtual scroll, column drag, density): ~5d
  - §9.2 Bulk actions bar: ~3d
  - §9.3 Export full spec (Excel/PDF/clipboard/share-link): ~3d
  - §6.1–6.3 Dashboard presets + widget grid + SSE feed: ~8d
  - §8.1 Two-person approval real approver fetch + MFA re-verify: ~2d
  - §8.2 Toast undo pattern: ~2d
  - Resolve /billing/ vs /accounting/ drift (deprecate or redirect): ~1d
  - paysync surface table upgrade to ConfigurableDataTable: ~3d
  - Client onboarding wizard (§7.4) full 7-step: ~6d (if skeleton only)
  - Draft server persistence (wizard localStorage → server): ~2d

REUSABILITY: YES — existing components are salvageable, not throwaway.
  Paysync primitives (MoneyDisplay, HashChainBadge, RbacGate, ProvenanceBreadcrumb,
  MoneyInput) are well-structured and tested. The BillingCycleWizard and
  PaymentBatchWizard are substantial implementations built on a real shared wizard
  framework worth preserving. The /accounting/cycles and /accounting/cycles/[id]
  pages are the highest-quality financial surfaces and should be the canonical
  pattern. Rebuilding from scratch would discard ~60% of the work; patching to
  designed state is clearly the right call.

STRUCTURAL_ROT:
  1. THREE nav sources in conflict: nav-config.ts, manifest.json, module.config navTree.
     nav-config is canonical but has 6+ dead links to unmounted paysync routes.
  2. /billing/** vs /accounting/** DRIFT: parallel implementations of billing cycles
     exist under both paths. Nav-config routes to /accounting/ but the billing wizard
     redirects to /billing/ on completion. Operators are in the wrong section after
     finishing a cycle. Both sections should not coexist.
  3. EIGHT paysync surfaces built but unreachable: cycles, batches, invoices,
     reconciliations, carryovers, bank-settlements, payment-runs, journal all have
     complete paysync package components + nav-config entries + dashboard links but
     zero mount pages. The /admin/paysync dashboard links to all of these and all 404.
  4. /admin/paysync/uploads is WIRED but ABSENT from nav-config — undiscoverable
     unless you know the URL.
  5. paysync surface components use plain HTML tables, not ConfigurableDataTable.
     Creates visual inconsistency with /accounting/ pages which use the richer component.

REPORT_PATH: docs/audit/depth-reaudit-financial-2026-05-21.md
```
