# Portal Surface Inventory — 2026-05-21

Read-only audit. No code was changed. Goal: enumerate what the operator portal
actually exposes, identify module-package surfaces that are built but not wired
into a portal page and/or not reachable from the nav.

---

## 1. Portal Pages (`portal/operator/app/**/page.tsx`)

### Auth
| Route | What it renders |
|---|---|
| `/(auth)/login` | Login form |
| `/(auth)/mfa` | MFA challenge / TOTP entry |

### Accounting
| Route | What it renders |
|---|---|
| `/accounting/cycles` | Billing cycle list |
| `/accounting/cycles/[id]` | Billing cycle detail |
| `/accounting/journal-entries` | Journal entries list |
| `/accounting/nacha` | NACHA file management |
| `/accounting/payments` | Payment list |
| `/accounting/payments/[id]` | Payment detail |

### Admin
| Route | What it renders |
|---|---|
| `/admin/audit-log` | Audit log viewer |
| `/admin/config` | Program config home |
| `/admin/config/change-sets` | Scheduled change sets |
| `/admin/encryption` | Encryption key management |
| `/admin/government-programs` | Part-D / government program config |
| `/admin/network/banking-discrepancies` | Banking discrepancy queue |
| `/admin/network/chain-membership` | Chain membership management |
| `/admin/network/pay-to-entities` | Pay-to entity list |
| `/admin/network/pay-to-entities/[entityId]` | Pay-to entity detail |
| `/admin/network/tenant-ach-origination` | Tenant ACH origination config |
| `/admin/paysync` | PaySync dashboard (KPI cards + recent activity; hand-rolled, NOT the UploadsSurface) |
| `/admin/paysync/echo` | Echo Spec 400 candor operations page (hand-rolled) |
| `/admin/paysync/reports` | ReportsListPage from `@infinityrx/module-paysync` |
| `/admin/paysync/reports/cycles` | CycleReportsPage from `@infinityrx/module-paysync` |
| `/admin/paysync/reports/journal` | JournalEntriesReportPage from `@infinityrx/module-paysync` |
| `/admin/paysync/reports/period` | PeriodSummaryPage from `@infinityrx/module-paysync` |
| `/admin/paysync/setup` | SetupHomePage from `@infinityrx/module-paysync` |
| `/admin/paysync/setup/cycle-schedules` | CycleSchedulesPage from `@infinityrx/module-paysync` |
| `/admin/paysync/setup/email-recipients` | EmailRecipientsPage from `@infinityrx/module-paysync` |
| `/admin/paysync/setup/email-templates` | EmailTemplatesPage from `@infinityrx/module-paysync` |
| `/admin/paysync/setup/export-templates` | ExportTemplatesPage from `@infinityrx/module-paysync` |
| `/admin/paysync/setup/gl-account-mappings` | GlAccountMappingsPage from `@infinityrx/module-paysync` |
| `/admin/paysync/setup/invoice-sequences` | InvoiceSequencesPage from `@infinityrx/module-paysync` |
| `/admin/system-health` | System health dashboard |
| `/admin/tenants` | Tenant management |
| `/admin/users` | User management |

### Analytics
| Route | What it renders |
|---|---|
| `/analytics` | Analytics home |
| `/analytics/adherence` | Adherence analytics |
| `/analytics/claims` | Claims analytics |
| `/analytics/data-quality` | Data quality analytics |
| `/analytics/drug-trend` | Drug trend analytics |
| `/analytics/fills` | Fill analytics |
| `/analytics/financial` | Financial analytics |
| `/analytics/geography` | Geography analytics |
| `/analytics/member` | Member analytics |
| `/analytics/network` | Network analytics |
| `/analytics/pharmacies` | Pharmacy analytics |
| `/analytics/trends` | Trends analytics |

### Billing
| Route | What it renders |
|---|---|
| `/billing` | Billing home |
| `/billing/claims` | Billing claims list |
| `/billing/cycles/[id]` | Billing cycle detail |
| `/billing/cycles/new` | New billing cycle wizard |
| `/billing/invoices` | Invoice list |
| `/billing/invoices/[id]` | Invoice detail |

### Claims
| Route | What it renders |
|---|---|
| `/claims` | Claims list |
| `/claims/[id]` | Claim detail |
| `/claims/lookup` | Claim lookup |
| `/claims/manual` | Manual claim entry |
| `/claims/pa-override` | PA override management |

### Clients
| Route | What it renders |
|---|---|
| `/clients` | Client list |
| `/clients/[id]` | Client detail |
| `/clients/cardholders` | Cardholder management |
| `/clients/exceptions` | Client exceptions |
| `/clients/fees` | Fee schedule management |
| `/clients/networks` | Network assignments |
| `/clients/new` | New client wizard |
| `/clients/portal-access` | Client portal access management |
| `/clients/programs` | Program assignments |
| `/clients/states` | State coverage |

### Directories (`@infinityrx/module-directories`)
| Route | What it renders |
|---|---|
| `/directories/audit` | AuditLogPage from module |
| `/directories/codes/hcpcs` | HcpcsListPage from module |
| `/directories/codes/icd10` | Icd10ListPage from module |
| `/directories/drugs` | DrugsListPage from module |
| `/directories/drugs/[ndc]` | DrugDetailPage from module |
| `/directories/exclusions` | ExclusionsPage from module |
| `/directories/ingestion` | IngestionConsolePage from module |
| `/directories/members` | Member list |
| `/directories/members/[id]` | Member detail |
| `/directories/members/eligibility` | Eligibility check |
| `/directories/members/enroll` | Member enrollment |
| `/directories/pharmacies` | PharmaciesListPage from module |
| `/directories/pharmacies/[npi]` | PharmacyDetailPage from module |
| `/directories/prescribers` | PrescribersListPage from module |
| `/directories/prescribers/[npi]` | PrescriberDetailPage from module |
| `/directories/pricing` | PricingPage from module |
| `/directories/quality` | QualityDashboardPanel from module |

### EDI
| Route | What it renders |
|---|---|
| `/edi` | EDI home |
| `/edi/certs` | Certificate management |
| `/edi/monitor` | EDI transaction monitor |
| `/edi/partners` | Trading partner list |
| `/edi/partners/[id]` | Trading partner detail |
| `/edi/transactions` | Transaction list |
| `/edi/transactions/[id]` | Transaction detail |

### Medical Claims
| Route | What it renders |
|---|---|
| `/medical-claims` | Medical claims home |
| `/medical-claims/340b` | 340B management |
| `/medical-claims/claims/[id]` | Medical claim detail |
| `/medical-claims/crosswalk` | NDC-J-code crosswalk |
| `/medical-claims/site-of-care` | Site of care management |
| `/medical-claims/unified-spend` | Unified spend dashboard |

### Network
| Route | What it renders |
|---|---|
| `/network/credentialing` | Pharmacy credentialing |
| `/network/locator` | Pharmacy locator |

### Payments
| Route | What it renders |
|---|---|
| `/payments` | Payments home |
| `/payments/nacha` | NACHA management |

### Programs
| Route | What it renders |
|---|---|
| `/programs` | Program list |
| `/programs/[id]` | Program detail |
| `/programs/budget` | Budget management |
| `/programs/config` | Program config |
| `/programs/enrollment` | Enrollment management |

### ReclaimRx
| Route | What it renders |
|---|---|
| `/reclaimrx` | GTN Protection Dashboard (hand-rolled, live API calls to reclaimrx backend) |
| `/reclaimrx/dashboard` | ComingSoonPage — "FWA Detection Dashboard" (Plan D placeholder) |
| `/reclaimrx/investigations` | InvestigationsTable + InvestigationsKanban (hand-rolled, live) |
| `/reclaimrx/investigations/[id]` | Investigation detail (hand-rolled, live) |
| `/reclaimrx/holds` | ComingSoonPage — "Payment Holds" (Plan D placeholder) |
| `/reclaimrx/fraud-rings` | ComingSoonPage — "Fraud Ring Visualization" (Plan E placeholder) |
| `/reclaimrx/graph-runs` | ComingSoonPage — "Graph Run History" (Plan E placeholder) |
| `/reclaimrx/thresholds` | ComingSoonPage — "Threshold Config Editor" (Plan C placeholder) |
| `/reclaimrx/accumulator-anomalies` | ComingSoonPage — "Anomaly Detection Dashboard" (Plan E placeholder) |
| `/reclaimrx/leakage` | Leakage monitor (hand-rolled, live) |
| `/reclaimrx/recovery` | Recovery dashboard (hand-rolled, live) |
| `/reclaimrx/risk` | Risk scoring page (hand-rolled, live) |
| `/reclaimrx/wizard` | New case wizard (hand-rolled, live) |

### Reporting
| Route | What it renders |
|---|---|
| `/reporting` | Reporting home |
| `/reporting/builder` | Report builder |
| `/reporting/generate` | Report generation |
| `/reporting/library` | Report template library |
| `/reporting/library/[templateId]` | Template detail |
| `/reporting/scheduled` | Scheduled reports |
| `/reporting/viewer/[reportId]` | Report viewer |

### Settings
| Route | What it renders |
|---|---|
| `/settings` | Settings home |
| `/settings/dashboard` | Dashboard settings |
| `/settings/notifications` | Notification preferences |
| `/settings/profile` | User profile |
| `/settings/shortcuts` | Keyboard shortcuts |

### Root
| Route | What it renders |
|---|---|
| `/` | Operator home / landing dashboard |

**Total portal pages: 131**

---

## 2. Nav Structure

### `packages/shell/src/_generated/nav.ts` (auto-generated by build-manifest.ts)

The nav contains exactly **3 entries**:

| Label | Icon | Order | Route Prefix |
|---|---|---|---|
| Directories | database | 3 | `/directories` |
| Prescribers | user-md | 10 | `/prescribers` |
| PaySync | credit-card | 20 | `/admin/paysync` |

### `packages/shell/src/_generated/module-imports.ts`

Three modules are loaded at runtime: `prescriber-directory`, `directories`, `paysync`.

### `packages/shell/src/_generated/manifest.json`

The manifest lists only `["prescriber-directory", "directories", "paysync"]` under `modules`.

### Key implication

**ReclaimRx is entirely absent from the nav.** Its module config (`packages/modules/reclaimrx/module.config.ts`) declares `navEntry: { label: "ReclaimRx", icon: "shield-check", order: 4 }` but the module is NOT listed in `manifest.json` and NOT in `module-imports.ts`. Consequently it has no nav entry. All 13 `/reclaimrx/*` portal pages are reachable only by typing the URL directly.

The following large portal sections also have **no nav entry at all** because they are built entirely outside the module system (hand-rolled portal pages, not module-package surfaces):

`/accounting`, `/analytics`, `/billing`, `/claims`, `/clients`, `/edi`, `/medical-claims`, `/network`, `/payments`, `/programs`, `/reporting`, `/settings`, and the entire `/admin/*` tree outside `/admin/paysync`.

These sections presumably rely on a separate portal-level nav component (not the shell `NAV_ENTRIES` array) or are reached from the dashboard. The shell `NAV_ENTRIES` only governs the three module-registered sections.

---

## 3. BFF Routes (`portal/operator/app/api/**/route.ts`)

| BFF Path | Backend / Handler |
|---|---|
| `/api/auth/[...nextauth]` | NextAuth session handling (no backend proxy) |
| `/api/b10-canary` | Canary probe — resolves `@infinityrx/portal-shared` package name at Next runtime |
| `/api/claims` | In-memory store (`@/lib/data/store`) — **not** a live backend proxy |
| `/api/claims/stats` | Same in-memory store |
| `/api/directories/audit` | `@infinityrx/module-directories/bff` → `handleAuditQuery` |
| `/api/directories/ingest/[source]/cancel` | `@infinityrx/module-directories/bff` → `cancelRun` |
| `/api/directories/ingest/[source]/history` | `@infinityrx/module-directories/bff` → `listRunHistory` |
| `/api/directories/ingest/[source]/trigger` | `@infinityrx/module-directories/bff` → `triggerRun` |
| `/api/directories/ingest/runs/[runId]` | `@infinityrx/module-directories/bff` → `getRun` |
| `/api/directories/ingest/status` | `@infinityrx/module-directories/bff` → `getIngestionStatus` |
| `/api/directories/pharmacies` | `@infinityrx/module-directories/bff` → `handlePharmacySearch` |
| `/api/directories/prescribers/[npi]/exclusion-check` | `@infinityrx/module-directories/bff` → `handleExclusionCheck` |
| `/api/directories/quality` | `@infinityrx/module-directories/bff` → `handleQualityAlerts` |
| `/api/directories/quality/dismiss/[source]` | `@infinityrx/module-directories/bff` → `handleDismissAlert` |
| `/api/directories/search` | `@infinityrx/module-directories/bff` → `handleFederatedSearch` |
| `/api/v1/claims/manual` | Portal-local BFF → adjudication-engine (manual claim submission) |
| `/api/v1/dashboard/activity` | `@/lib/bff` → multiple backends (activity feed) |
| `/api/v1/dashboard/alerts` | `@/lib/bff` → multiple backends (alert feed) |
| `/api/v1/dashboard/kpi` | `@/lib/bff` → multiple backends (KPI aggregation with tenant injection) |
| `/api/v1/dashboard/program-health` | `@/lib/bff` → multiple backends (program health) |

**Notable gap:** There are **no BFF routes** for paysync surfaces other than what is embedded inside `@shared/lib/paysync-api` (called directly from client components). There are **no BFF routes** for reclaimrx at all — reclaimrx pages call `API_URLS.reclaimrx` directly via `apiGet`/`buildUrl`. There are no BFF routes for `/admin/paysync/uploads`, `/admin/paysync/cycles`, `/admin/paysync/batches`, etc.

---

## 4. Module-Package Surfaces vs Portal Mounting

### 4.1 `@infinityrx/module-directories`

**Declared routes in module.config.ts:** 13 routes  
**Surfaces in `src/surfaces/`:** codes (HCPCS, ICD-10), drugs, exclusions, pharmacies, prescribers, pricing  
**Other surfaces in `src/`:** ingestion, quality, audit, search, components  
**Public exports (dist/src/index.d.ts):** `surfaces/*`, `ingestion/*`, `quality/*`, `audit/*`, `search/*`, `components/*`

| Surface | Exported? | Portal page path | In nav? |
|---|---|---|---|
| DrugDetailPage | Yes | `/directories/drugs/[ndc]` | Yes (under Directories) |
| DrugsListPage | Yes | `/directories/drugs` | Yes |
| HcpcsListPage | Yes | `/directories/codes/hcpcs` | Yes |
| Icd10ListPage | Yes | `/directories/codes/icd10` | Yes |
| ExclusionsPage | Yes | `/directories/exclusions` | Yes |
| PharmaciesListPage | Yes | `/directories/pharmacies` | Yes |
| PharmacyDetailPage | Yes | `/directories/pharmacies/[npi]` | Yes |
| PrescribersListPage | Yes | `/directories/prescribers` | Yes |
| PrescriberDetailPage | Yes | `/directories/prescribers/[npi]` | Yes |
| PrescriberMonitoringPanel | Yes (in detail page) | — | — |
| PricingPage | Yes | `/directories/pricing` | Yes |
| IngestionConsolePage | Yes | `/directories/ingestion` | Yes (under Directories) |
| QualityDashboardPanel | Yes | `/directories/quality` | Yes |
| AuditLogPage | Yes | `/directories/audit` | Yes |
| DirectoriesCommandPalette | Yes | Global (command palette) | — |

**Verdict: directories module is fully wired.** All declared routes have portal pages, all pages import from the module package, BFF routes are in place.

---

### 4.2 `@infinityrx/module-paysync`

**Declared routes in module.config.ts:** 13 routes  
**Surfaces in `src/surfaces/`:** uploads, cycles, batches, carryovers, invoices, payment-runs, files, bank-settlements, reconciliations, journal, reports, setup, echo  
**Public exports (src/index.ts):** 13 SurfaceConfig objects + page components for reports and setup sub-pages  
**In nav:** Yes — "PaySync" entry at `/admin/paysync`

| Surface | Exported? | Portal page path | In nav? | Notes |
|---|---|---|---|---|
| UploadsSurface + UploadsListPage + UploadDropzone + UploadDetailPage + UploadClaimViewer | **Yes** | **NONE** | **No** | No `/admin/paysync/uploads/page.tsx` exists |
| CyclesSurface + CyclesListPage + CycleDetailPage | Yes | **NONE** | **No** | No `/admin/paysync/cycles/page.tsx` exists |
| BatchesSurface + BatchesListPage + BatchDetailPage | Yes | **NONE** | **No** | No `/admin/paysync/batches/page.tsx` exists |
| CarryoversSurface + CarryoversListPage + CarryoverDetailPage | Yes | **NONE** | **No** | No `/admin/paysync/carryovers/page.tsx` exists |
| InvoicesSurface + InvoicesListPage + InvoiceDetailPage | Yes | **NONE** | **No** | No `/admin/paysync/invoices/page.tsx` exists |
| PaymentRunsSurface + PaymentRunsListPage + PaymentRunDetailPage + ManualApForm | Yes | **NONE** | **No** | No `/admin/paysync/payment-runs/page.tsx` exists |
| FilesSurface + FilesListPage + FileDetailPage + FileGenerateForm | Yes | **NONE** | **No** | No `/admin/paysync/files/page.tsx` exists |
| BankSettlementsSurface + BankSettlementsListPage + BankSettlementDetailPage | Yes | **NONE** | **No** | No `/admin/paysync/settlements/page.tsx` exists |
| ReconciliationsSurface + ReconciliationsListPage + ReconciliationDetailPage | Yes | **NONE** | **No** | No `/admin/paysync/reconcile/page.tsx` exists |
| JournalSurface + JournalListPage + JournalDetailPage + HashChainVerifyButton | Yes | **NONE** | **No** | No `/admin/paysync/journal/page.tsx` exists |
| ReportsSurface + ReportsListPage | Yes | `/admin/paysync/reports` | Yes (sub-nav via Setup/Reports links) | Mounted, working |
| CycleReportsPage | Yes | `/admin/paysync/reports/cycles` | Via reports page | Mounted, working |
| JournalEntriesReportPage | Yes | `/admin/paysync/reports/journal` | Via reports page | Mounted, working |
| PeriodSummaryPage | Yes | `/admin/paysync/reports/period` | Via reports page | Mounted, working |
| SetupSurface + SetupHomePage | Yes | `/admin/paysync/setup` | Yes (via PaySync nav) | Mounted, working |
| CycleSchedulesPage | Yes | `/admin/paysync/setup/cycle-schedules` | Via setup page | Mounted, working |
| EmailRecipientsPage | Yes | `/admin/paysync/setup/email-recipients` | Via setup page | Mounted, working |
| EmailTemplatesPage | Yes | `/admin/paysync/setup/email-templates` | Via setup page | Mounted, working |
| ExportTemplatesPage | Yes | `/admin/paysync/setup/export-templates` | Via setup page | Mounted, working |
| GlAccountMappingsPage | Yes | `/admin/paysync/setup/gl-account-mappings` | Via setup page | Mounted, working |
| InvoiceSequencesPage | Yes | `/admin/paysync/setup/invoice-sequences` | Via setup page | Mounted, working |
| EchoSurface | Yes (descriptor only) | `/admin/paysync/echo` | Not in paysync navTree (hand-rolled page) | Mounted but hand-rolled |
| InboxQueue + inbox cards | Yes | `/admin/paysync` (dashboard references cycles/reconcile/invoices links only) | Yes | Inbox card components are exported but InboxQueue is NOT mounted in the dashboard page |

**What `/admin/paysync` (the index page) actually renders:** A hand-rolled KPI card dashboard (`PaysyncDashboardPage`) that directly calls `@shared/lib/paysync-api`. It does NOT mount the `UploadsSurface` or `InboxQueue`, even though `paysyncComposition.routeSurfaces` maps `/admin/paysync` to the `"uploads"` surface and the navTree primary item is labeled "Inbox".

**Summary: 10 of 13 paysync surfaces are built and exported but have zero portal pages.**

---

### 4.3 `@infinityrx/module-reclaimrx`

**Declared routes in module.config.ts:** 10 routes  
**Surfaces in `src/`:** investigations, holds, recovery, graph, ml, rules, rbac, bff, components  
**Public exports (src/index.ts):** `export { config as default } from "../module.config.js"` — **only the config is exported; no surface components are exported at all**  
**In nav:** **No** — reclaimrx is NOT listed in `manifest.json` and NOT in `module-imports.ts`; its `navEntry` declaration in `module.config.ts` is ignored

| Surface | Exported? | Portal page path | In nav? | Notes |
|---|---|---|---|---|
| Investigations (src/investigations/) | **No** | `/reclaimrx/investigations` (hand-rolled) | No (no nav entry) | Portal page exists but imports nothing from module package |
| Holds (src/holds/) | **No** | `/reclaimrx/holds` (ComingSoonPage) | No | Portal page is a placeholder |
| Recovery (src/recovery/) | **No** | `/reclaimrx/recovery` (hand-rolled) | No | Portal page exists but hand-rolled |
| Graph analysis (src/graph/) | **No** | `/reclaimrx/graph-runs` (ComingSoonPage) | No | Placeholder |
| ML scoring (src/ml/) | **No** | `/reclaimrx/risk` (hand-rolled) | No | Portal page exists but hand-rolled |
| Rules (src/rules/) | **No** | No portal page | No | No page of any kind |
| RBAC (src/rbac/) | **No** | No portal page | No | No page of any kind |
| FWA Dashboard | **No** | `/reclaimrx/dashboard` (ComingSoonPage) | No | Placeholder; plan D |
| Fraud rings | **No** | `/reclaimrx/fraud-rings` (ComingSoonPage) | No | Placeholder; plan E |
| Thresholds | **No** | `/reclaimrx/thresholds` (ComingSoonPage) | No | Placeholder; plan C |
| Accumulator anomalies | **No** | `/reclaimrx/accumulator-anomalies` (ComingSoonPage) | No | Placeholder; plan E |
| Leakage monitor | **No** | `/reclaimrx/leakage` (hand-rolled) | No | Entirely outside the module package |
| New case wizard | **No** | `/reclaimrx/wizard` (hand-rolled) | No | Entirely outside the module package |

**Verdict: reclaimrx module package exports nothing usable.** All working reclaimrx UI is hand-rolled directly in the portal. The module is not registered in the manifest, so it contributes no nav entry. The only route to reclaimrx pages is via the `/reclaimrx` root dashboard's inline links ("+ New Case" → `/reclaimrx/wizard`, "Leakage Monitor" → `/reclaimrx/leakage`) or the `/reclaimrx/investigations` links on the GTN dashboard. **There is no top-level nav entry for ReclaimRx under any circumstance.**

---

### 4.4 `@infinityrx/module-prescriber-directory`

**Declared routes in module.config.ts:** `/prescribers`, `/prescribers/:npi`, `/prescribers/search`  
**In nav:** Yes — "Prescribers" entry at `/prescribers`  
**Portal pages for `/prescribers`:** None found at `portal/operator/app/prescribers/` — the module is loaded in `module-imports.ts` and has a nav entry, but there are no corresponding `page.tsx` files in the portal under `/prescribers`. Prescriber pages exist under `/directories/prescribers` (mounted via the directories module), NOT under the `/prescribers` prefix that this module declares.

| Surface | Exported? | Portal page path | In nav? | Notes |
|---|---|---|---|---|
| `/prescribers` | Unknown (module exports not checked — dist not inspected) | **NONE at `/prescribers`** | Yes (nav entry exists) | Nav points to `/prescribers` but no page exists there; directories has `/directories/prescribers` separately |
| `/prescribers/:npi` | Unknown | **NONE** | No | No page at this path |
| `/prescribers/search` | Unknown | **NONE** | No | No page at this path |

**Verdict: prescriber-directory module has a nav entry pointing to `/prescribers` but no portal pages exist at that route.** Clicking "Prescribers" in the nav would 404. Prescriber browsing works only via `/directories/prescribers` (the directories module).

---

## 5. Upload / Ingestion Flows — Specific Analysis

### 5.1 PaySync Uploads

**Package code status:**

`packages/modules/paysync/src/surfaces/uploads/` contains:
- `UploadsListPage.tsx` — full list view with dedup banner
- `UploadDropzone.tsx` — file drop zone for uploading paysync data files
- `UploadDetailPage.tsx` — upload detail with row-level error display
- `UploadClaimViewer.tsx` — per-upload claim viewer
- `bff/uploads.ts` — BFF handlers: `handleListUploads`, `handleGetUpload`, `handleGetUploadClaims`, `handleCreateUpload`

All four components are exported from `src/surfaces/uploads/index.ts` and re-exported from `src/index.ts` as named exports.

**Portal page status:**

`portal/operator/app/admin/paysync/uploads/page.tsx` — **does not exist**.

The directory `portal/operator/app/admin/paysync/` contains only: `echo/`, `page.tsx`, `reports/`, `setup/`. The `/uploads` route is listed in `paysyncComposition.routeSurfaces` (maps to surface `"uploads"`) and in `module.config.ts` routes, but no portal page was ever created for it.

**BFF route status:**

`portal/operator/app/api/` has no route under `paysync/uploads/`. The BFF handlers (`handleCreateUpload`, `handleListUploads`, etc.) are exported from the module package but not mounted in any `app/api/**/route.ts` file.

**Nav status:**

PaySync appears in the nav at `/admin/paysync`. The paysync `navTree.primary` array labels the index as "Inbox" and lists "History" at `/admin/paysync/uploads`. But the portal index page (`/admin/paysync/page.tsx`) is a hand-rolled KPI dashboard that does not render the `InboxQueue` component or link to uploads. There is no `/admin/paysync/uploads` page to navigate to.

**Why a user cannot find the upload entry point:**

1. The "PaySync" nav entry lands at `/admin/paysync`, which renders a hand-rolled KPI overview — not the `UploadsSurface` that `paysyncComposition.routeSurfaces` designates for that route.
2. There is no `/admin/paysync/uploads/page.tsx`, so navigating to that URL returns a 404.
3. The `UploadDropzone` and `UploadsListPage` components exist in the package and are exported, but they are never imported anywhere in the portal.
4. No BFF route exposes `handleCreateUpload`.

---

### 5.2 ReclaimRx Data Upload / Ingestion

**Package code status:**

`packages/modules/reclaimrx/src/` contains: `bff/`, `components/`, `graph/`, `holds/`, `investigations/`, `ml/`, `rbac/`, `recovery/`, `rules/`.

There is **no `uploads/` or `ingest/` surface** in the reclaimrx module package. The module does not define any upload or data-ingestion surface in its source tree.

`src/index.ts` exports only `config` from `module.config.ts`. None of the internal subdirectories (investigations, holds, recovery, graph, ml, rules, rbac) are exported from the public barrel.

**Portal page status:**

All working reclaimrx portal pages (`/reclaimrx/investigations`, `/reclaimrx/leakage`, `/reclaimrx/recovery`, `/reclaimrx/risk`, `/reclaimrx/wizard`) are hand-rolled and call the reclaimrx backend directly. None import from `@infinityrx/module-reclaimrx`.

There is no upload or data-ingestion page anywhere under `/reclaimrx/*`.

**Nav status:**

ReclaimRx has no nav entry. The module is not in `manifest.json`. Users reach reclaimrx only via inline links on the GTN dashboard or by typing the URL.

**Why a user cannot find an upload entry point for reclaimrx:**

There is no upload surface — not in the package code and not in the portal. The module config declares backend event queues (`reclaimrx.accumulator_updated`, `reclaimrx.fwa_events`) suggesting data enters via event bus from the adjudication engine, not via direct user uploads. No operator-facing upload flow was designed or built for reclaimrx.

---

## 6. Summary Gap Table

| Built-not-wired surface | Package | Surface built? | Exported? | Portal page? | In nav? |
|---|---|---|---|---|---|
| UploadsListPage + UploadDropzone (file upload UI) | paysync | Yes | Yes | No | No |
| UploadDetailPage + UploadClaimViewer | paysync | Yes | Yes | No | No |
| CyclesListPage + CycleDetailPage | paysync | Yes | Yes | No | No |
| BatchesListPage + BatchDetailPage | paysync | Yes | Yes | No | No |
| CarryoversListPage + CarryoverDetailPage | paysync | Yes | Yes | No | No |
| InvoicesListPage + InvoiceDetailPage | paysync | Yes | Yes | No | No |
| PaymentRunsListPage + ManualApForm | paysync | Yes | Yes | No | No |
| FilesListPage + FileDetailPage + FileGenerateForm | paysync | Yes | Yes | No | No |
| BankSettlementsListPage + BankSettlementDetailPage | paysync | Yes | Yes | No | No |
| ReconciliationsListPage + ReconciliationDetailPage | paysync | Yes | Yes | No | No |
| JournalListPage + JournalDetailPage | paysync | Yes | Yes | No | No |
| InboxQueue + 11 inbox item cards | paysync | Yes | Yes | No | No |
| All internal surfaces (investigations/holds/recovery/graph/ml/rules/rbac) | reclaimrx | Yes (src files) | No (index.ts exports only config) | Partial (some hand-rolled) | No (module not in manifest) |
| reclaimrx module nav entry | reclaimrx | navEntry declared | N/A | N/A | No (module not in manifest.json) |
| prescriber-directory routes (/prescribers, /prescribers/:npi, /prescribers/search) | prescriber-directory | Unknown | Unknown | No (no pages at /prescribers) | Nav entry exists → 404 |
| FWA Dashboard (reclaimrx/dashboard) | reclaimrx | No (placeholder) | No | ComingSoonPage | No |
| Payment Holds UI (reclaimrx/holds) | reclaimrx | No (placeholder) | No | ComingSoonPage | No |
| Fraud Ring Visualization | reclaimrx | No (placeholder) | No | ComingSoonPage | No |
| Threshold Config Editor | reclaimrx | No (placeholder) | No | ComingSoonPage | No |
| Accumulator Anomaly Dashboard | reclaimrx | No (placeholder) | No | ComingSoonPage | No |
| Graph Run History | reclaimrx | No (placeholder) | No | ComingSoonPage | No |

---

*Generated 2026-05-21. Read-only audit — no code changes made.*
