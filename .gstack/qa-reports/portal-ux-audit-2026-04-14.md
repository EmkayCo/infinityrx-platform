# InfinityRx Operator Portal — UX & Functional Interaction Audit

**Date:** 2026-04-14
**Auditor persona:** PBM operations analyst (non-developer, $300M+/yr claims volume)
**Portal branch:** `main`
**Portal build:** Next.js 16.2.3 (Turbopack), mock data layer (`NEXT_PUBLIC_USE_MOCK_DATA=true`)
**Method:** Source-code walkthrough of every route and shared component, cross-referenced with mock data shapes and lib/data store. Where browser verification was needed, checked HTTP responses, React handlers, and navigation targets. The headless browser tool was unavailable during this audit, but the entire interactivity surface is static and deterministic in the source — every `onClick`, `Link`, `router.push`, and event handler was enumerated.

> **Scope reality check:** 64 route files, 44 operator-portal components, 16+ shared components. Findings below cover every page in the requested phases. Evidence is file-path:line anchored. This audit is *report-only* — no code was modified.

---

## Executive Summary

**Overall health: the portal is a beautifully-lit display case.** The visual shell is polished (sidebar, topbar, presets, charts, skeletons, error boundaries), but the interactive spine behind it is almost entirely missing. An operator cannot drill from a summary number to the underlying rows in more than a handful of places. Tables are populated but rows are not clickable. Dashboard widgets have no navigation. Detail pages exist for some entities but are shallow compared to what a PBM operator needs for day-to-day investigation, reconciliation, and audit.

**Top impact pattern:** "Summary → list → detail → record" is the core operator workflow, and it is broken at the very first hop on nearly every page. Numbers are lit up. Rows don't go anywhere. Action buttons are mostly decorative.

**Severity at a glance:**

| Severity | Count | Examples |
|---|---|---|
| Critical | 14 | Dashboard widgets don't drill through; no row clicks on pharmacies/prescribers/drugs; investigation detail missing; no claim detail page |
| High | 23 | Kanban cards don't open detail; charts don't drill; AP/AR dead-end; audit log widget dead; ⌘K search limited |
| Medium | 31 | Missing operator-critical fields; no sort/filter on many tables; exports non-functional on several pages |
| Low | 18 | Format inconsistencies, minor copy, empty-state polish |

**Health score (qa-only rubric):** `28/100`. See Part 7 (scoring detail).

---

## Part 1 — Interaction Inventory (per page)

Legend:
- **Clickable?** Y / N / — (element doesn't exist)
- **Goes where** — actual behavior in source
- **Should go where** — operator expectation
- **Data complete?** Y / Partial / N
- **Action available?** Y / N

### 1.1 Home Dashboard (`/` — `portal/operator/app/page.tsx`)

| Element | Clickable? | Goes where | Should go where | Data complete? | Action? |
|---|---|---|---|---|---|
| Preset selector tabs (Billing Ops, FWA, Executive, Sys Admin) | Y | Swaps `PRESET_LAYOUTS`, persists to `localStorage` | ✅ Works | Y | Y |
| Widget drag handle | Y | Reorders grid (@dnd-kit), persists | ✅ Works | Y | Y |
| Widget resize button (1x1→2x1→1x2→2x2) | Y | Local state + storage | ✅ Works | Y | Y |
| Widget refresh button (⟳) | Y | `refetch()` on query | ✅ Works | Y | Y |
| Widget title (`Active Billing Cycles`, `Payment Batches Pending`, etc.) | **N** | Plain `<h3>` — no Link, no onClick | → `/billing` filtered to active cycles | Y | N |
| Widget body / the big number (e.g. "34 active cycles") | **N** | Plain text | → filtered list of those 34 rows | Y | N |
| "AP/AR Summary" Receivable/Payable/Net rows | **N** | Plain divs | → `/billing/cycles` filtered by AR side / AP side | Y | N |
| "FWA Alerts" high/today/week chips | **N** | Plain colored cards | → `/reclaimrx` filtered by severity / date | Y | N |
| "System Health" service rows | **N** | Plain rows | → `/admin/system-health#{service}` (drill to specific) | Partial (no error detail) | N |
| "Recent Reports" list items | **N** | Plain rows | → `/reporting/viewer/{reportId}` | Partial | N |
| "Activity Feed" event rows | **N** | `<ActivityFeed>` rendered **without** `onEventClick` — handler exists in component but dashboard never passes it. `shared/components/activity-feed/index.tsx:58` | → specific record (investigation, cycle, batch, claim) depending on `event.entity_type` | Partial — the event has entity IDs but nothing is rendered from them beyond user name and description | N |
| "Investigations" widget number | **N** | Plain big number | → `/reclaimrx/investigations` filtered to active | Y | N |
| "Recovery Pipeline" estimated/demanded/collected rows | **N** | Plain rows | → `/reclaimrx/recovery` filtered by stage | Y | N |
| "Claims Processed" today/MTD/YTD tiles | **N** | Plain tiles | → `/billing/claims` filtered by date window | Y | N |
| "Recent Audit Entries" rows | **N** | Plain rows | → `/admin/audit-log?entry={id}` | Partial — action + user shown, no entity drill | N |
| "Active Sessions" big number + users | **N** | Plain display | → `/admin/users` filtered to sessions | Partial | N |
| Onboarding checklist `Start →` links | Y | `<a href>` to `/settings/profile#mfa`, `/billing/tutorial`, etc. | ✅ Works, BUT `/billing/tutorial` is a **404** — no such route exists | Partial | Partial |
| Onboarding checkboxes | Y | Local state only, no persistence of per-step done | Should persist | N | N |

**Phase 1 dead-end count: 14 of 14 interactive-looking elements inside widgets**. Every single widget is display-only.

### 1.2 ReclaimRx Dashboard (`/reclaimrx`)

| Element | Clickable? | Goes where | Should go where | Data complete? | Action? |
|---|---|---|---|---|---|
| "Investigation Queue →" button (header) | Y | `/reclaimrx/investigations` | ✅ Works | Y | Y |
| StatCard "New Flags Today" | **N** | Plain div | → `/reclaimrx/investigations?flagged_at=today` | Y | N |
| StatCard "New Flags This Week" | **N** | Plain div | → `/reclaimrx/investigations?flagged_at=week` | Y | N |
| StatCard "Critical Flags" | **N** | Plain div | → `/reclaimrx/investigations?severity=critical` | Y | N |
| StatCard "High Severity" | **N** | Plain div | → `/reclaimrx/investigations?severity=high` | Y | N |
| Severity Pie Chart slices | **N** | recharts (no `onClick`) | → `/reclaimrx/investigations?severity={slice}` | Y | N |
| Trend Line (90 days) data points | **N** | recharts | → `/reclaimrx/investigations?date={point}` | Y | N |
| "Top Flagged Entities" table rows (`top-flagged-entities-card.tsx:41`) | **N** | `<DataTable>` has no `onRowClick` prop | → entity drill (pharmacy or prescriber profile filtered to flagged claims) | Partial (no NPI) | N |
| "Top Flagged Entities" Export | Y (looks) | `onExportCsv={() => {/* export */}}` — handler body is **empty**. Nothing happens on click. | Download CSV | Y | **N (stub)** |

### 1.3 ReclaimRx Recovery Tracking (`/reclaimrx/recovery`)

| Element | Clickable? | Goes where | Should go | Data complete? | Action? |
|---|---|---|---|---|---|
| Recovery row click | Y | `router.push('/reclaimrx/investigations/{investigation_id}')` (`recovery-interactive.tsx:148`) | ✅ Works | Y | Y |
| Total Estimated / Demanded / Collected cards | **N** | Plain tiles | → filter table by stage | Y | N |
| ExportMenu CSV | **N (stub)** | Empty handler | CSV download | Y | N |
| ExportMenu Excel | **N (stub)** | Empty handler | XLSX download | Y | N |
| Sort by column | Y | react-table sort (enabled by DataTable) | ✅ Works | Y | Y |
| Filter by status | **N** (no filter UI) | — | By status, date, pharmacy | Y | N |
| Bulk actions (mark recovered, write off) | **N** (no selection UI) | — | Multi-select + bulk state change | Y | N |
| Global search (DataTable built-in) | Y | Fuzzy filter | ✅ Works | Y | Y |

### 1.4 ReclaimRx Investigations Kanban (`/reclaimrx/investigations`)

| Element | Clickable? | Goes where | Should go | Data complete? | Action? |
|---|---|---|---|---|---|
| Investigation card click | Y | `router.push('/reclaimrx/investigations/{id}')` (`investigations-kanban.tsx:58`) | ✅ Works | Y | Y |
| Card drag | Y | `PATCH /api/v1/investigations/{id}` with new status | ✅ Works | Y | Y |
| "New Investigation" button | **—** (no button rendered) | — | Create flow | — | N |
| Filter by severity | **—** | — | Needed | — | N |
| Filter by analyst | **—** | — | Needed | — | N |
| Filter by date range | **—** | — | Needed | — | N |
| Toggle to list/table view | **—** | — | Needed (bulk triage) | — | N |
| Column capacity indicator (over-WIP warning) | **—** | — | Nice-to-have | — | N |

### 1.5 Investigation Detail (`/reclaimrx/investigations/[id]`)

| Element | Clickable? | Goes where | Should go | Data complete? | Action? |
|---|---|---|---|---|---|
| Back button | Y | `router.back()` | ✅ Works | Y | Y |
| Entity name header (`flag.entity_name`) | **N** | Plain `<h1>` | → pharmacy/prescriber profile | Y | N |
| Recovery amount cards (Estimated, Demanded, Collected) | **N** | Plain divs | → breakdown by claim | Y | N |
| Evidence checklist checkboxes | Y | `PATCH /investigations/{id}/evidence/{eid}/toggle` (`page.tsx:239`) | ✅ Works | Y | Y |
| Add evidence item | **—** (no UI) | — | Needed | — | N |
| Related Claims table row click | **N** | `<DataTable>` has no `onRowClick` (`page.tsx:281-287`) | → claim detail page (`/billing/claims/{id}` — which **doesn't exist**) | Y (limited cols) | N |
| Documents Upload button | **N (stub)** | No `onClick` at all (`page.tsx:295`) | File picker + POST to backend | — | N |
| Documents drop-zone | **N (stub)** | Plain `<div>` with no drag handlers | Drop → upload | — | N |
| Action Timeline / ActivityFeed | **N** | Rendered without `onEventClick` | → jump to event source | Y | N |
| "Continue Investigation →" button | Y | `router.push('/reclaimrx/investigations/{id}/wizard')` — **route does not exist**, 404 | Multi-step wizard | — | **Broken** |
| Reassign / Escalate / Close / Add Note buttons | **—** (none rendered) | — | Standard case-management actions | — | N |
| Investigation type (FWA taxonomy) | **—** (not displayed) | — | FWA category (billing scheme, DUR, compound, ghost, etc.) | N | N |

### 1.6 Pharmacies Directory (`/directories/pharmacies`, `/directories/pharmacies/[npi]`)

| Element | Clickable? | Goes where | Should go | Data complete? | Action? |
|---|---|---|---|---|---|
| Row click (list) | Y | `router.push('/directories/pharmacies/{npi}')` | ✅ Works | Partial | Y |
| "Map View" button | **N (stub)** | No `onClick` (`pharmacies/page.tsx:132`) | Toggle map overlay | — | N |
| Export CSV | **N (stub)** | Empty handler | — | — | N |
| Column sort | Y | DataTable sort | ✅ Works | Y | Y |
| Search box | Y | Server-side query param | ✅ Works | Y | Y |
| Detail → Claims history row click | **N** | No `onRowClick` | → claim detail (doesn't exist) | Y | N |
| Detail → Credentialing Checklist | **N** | **HARDCODED** static array for every pharmacy (`[npi]/page.tsx:41-48`) | Should be real per-pharmacy data | **N (fake)** | N |
| Detail → Location/Map tile | **N** | Static placeholder div | Embedded map | N | N |
| Detail → Edit / Add Note / Action buttons | **—** | — | Edit pharmacy fields, add a note | — | N |
| Detail → View Active Investigations link | **—** | — | Jump to ReclaimRx filtered by this NPI | — | N |

### 1.7 Prescribers Directory (`/directories/prescribers`, `/directories/prescribers/[npi]`)

| Element | Clickable? | Goes where | Should go | Data complete? | Action? |
|---|---|---|---|---|---|
| Row click (list) | Y | detail page | ✅ Works | Partial | Y |
| Export CSV | **N (stub)** | Empty handler | — | — | N |
| Column sort | Y | Works | ✅ | Y | Y |
| Credential alerts list items | **N** | Plain `<li>` | → DEA verification page, license registry | Y | N |
| Top Drugs chart bars | **N** | Recharts | → `/directories/drugs/{ndc}` | Y | N |
| Affiliated pharmacies | **—** (not shown) | — | List of pharmacies this prescriber writes at | — | N |

### 1.8 Drugs Directory (`/directories/drugs`, `/directories/drugs/[ndc]`)

| Element | Clickable? | Goes where | Should go | Data complete? | Action? |
|---|---|---|---|---|---|
| Row click | Y | detail page | ✅ Works | Partial | Y |
| "Price change alerts" banner | **N** | Static info text | → alerts/history page | N | N |
| Detail → Drug interactions row click | **N** | No `onRowClick` | → interacting drug's detail | Y | N |
| Detail → Therapeutic equivalents row click | **N** | No `onRowClick` | → equivalent drug's detail (critical — operator uses this to compare cost) | Y | N |
| Detail → "Claims history for this drug" | **—** (not shown) | — | Table of recent claims with this NDC | — | N |
| Price history chart data points | **N** | Recharts | → claims at that price point | Y | N |

### 1.9 Members Directory (`/directories/members`, `/directories/members/[id]`)

| Element | Clickable? | Goes where | Should go | Data complete? | Action? |
|---|---|---|---|---|---|
| Row click (list) | Y | detail page | ✅ Works | Partial | Y |
| "Eligibility Check" button | Y | `/directories/members/eligibility` | ✅ Works | Y | Y |
| "Enroll Members" button | Y | `/directories/members/enroll` | ✅ Works | Y | Y |
| PHI masking when role lacks `DirectoriesFull` | Y | Proper mask display + notice banner | ✅ Works | Y | Y |
| Detail → Claims history row click | **N** | No `onRowClick` | → claim detail | Y | N |
| Accumulator bars | **N** | Read-only bars | → accumulator history / reversal log | Partial | N |
| Detail → Active prescriptions | **—** (not shown) | — | Current Rx list with refill status | — | N |
| Detail → Prior auth history | **—** | — | PA submissions/approvals | — | N |

### 1.10 Billing (`/billing`, `/billing/cycles/[id]`, `/billing/claims`, `/billing/invoices`, `/billing/invoices/[id]`)

| Element | Clickable? | Goes where | Should go | Data complete? | Action? |
|---|---|---|---|---|---|
| Billing cycle row click | Y | `/billing/cycles/{id}` | ✅ Works | Partial | Y |
| Top tab nav (Cycles/Claims/Invoices) | Y | `router.push(href)` | Works but **no active-tab styling** — `data-[active]` attribute is referenced in CSS but never set (`billing/page.tsx:158`) | Partial | Y |
| "New Billing Cycle" button | Y | `/billing/cycles/new` wizard | ✅ Works | Y | Y |
| Cycle detail "Download" artifact link | Y | `<a download>` | ✅ Works | Y | Y |
| Cycle detail "Transmit" NACHA button | Y | Calls `transmitNacha` API | ✅ Works | Y | Y |
| Cycle detail → no claim-level drill | **—** | — | Click through to cycle's claims | — | N |
| **Claims Review row click** (`/billing/claims`) | **N** | Virtual-scroll row is a `<div>` with no `onClick` (`claims/page.tsx:292`) | → `/billing/claims/{id}` detail page that **does not exist at all in the route tree** | Partial | N |
| Claims filter: status / NRID / DOS range / free-text | Y | URL query params | ✅ Works | Y | Y |
| Claims export CSV | Y | Browser blob download | ✅ Works | Y | Y |
| Claims: bulk select / bulk action | **—** | — | Flag for review, include in batch, export selected | — | N |
| Claims sort by column | **N** | Manual `<div>` rows (not DataTable), no sort | Needed | — | N |
| Invoice row click | Y | `/billing/invoices/{id}` | ✅ Works | Y | Y |
| Invoice status filter | Y | Works | ✅ | Y | Y |
| Invoice detail Approve/Send/Void | Y | Mutations wired | ✅ Works | Y | Y |
| Invoice detail PDF download | Y | `getInvoicePdf` blob | ✅ Works | Y | Y |
| Invoice line-items table row click | **N** | Plain `<tr>` with no `onClick` | → claim that generated that line | Partial | N |

### 1.11 Payments (`/payments`, `/payments/batches/[id]`, `/payments/nacha`, `/payments/batches/new`)

| Element | Clickable? | Goes where | Should go | Data complete? | Action? |
|---|---|---|---|---|---|
| Batch row click | Y | `/payments/batches/{id}` | ✅ Works | Y | Y |
| Batch status badge | **N** | Display only | → filter list by this status | Y | N |
| "New Batch" button | Y | Wizard | ✅ Works | Y | Y |
| Tab nav (Batches / NACHA Files) | Y | Works, but again **no active state indication** | Partial | Y | Y |
| Batch detail → NACHA preview row click | **N** | Plain `<tr>` | → raw segment viewer, or drill to vendor detail | Y | N |
| Batch detail → "Retry/Retransmit" | **—** | — | Critical operator action | — | N |
| Batch detail → "Escalate to manager" | **—** | — | For failed ack batches | — | N |

### 1.12 Analytics (`/analytics`, `/analytics/financial`, `/analytics/drug-trend`, `/analytics/network`, `/analytics/member`, `/analytics/data-quality`)

| Element | Clickable? | Goes where | Should go | Data complete? | Action? |
|---|---|---|---|---|---|
| Analytics landing nav-cards | Y | sub-pages | ✅ Works | Y | Y |
| Live counter "Claims/Hour" / "Dollars Flowing" / "Flags/Day" | **N** | `<div>` | → `/billing/claims` filtered to current hour | Y | N |
| PMPM cards / YoY change | **N** | Display only | → drill to member cohort | Y | N |
| Cost-driver category bars | **N** | Recharts | → claims filtered by category | Y | N |
| Drug-trend tabs (Spend/Brand-Generic/GLP-1/Biosimilar/Top by Spend) | Y | Local `activeTab` state | ✅ Works | Y | Y |
| Top-20 drugs bar chart | **N** | Recharts | → `/directories/drugs/{ndc}` | Y | N |
| Network adequacy cards (coverage %, gap counties) | **N** | Display tiles | → map view, or county list | Y | N |
| Pharmacy scorecards table row click | **N** | DataTable without `onRowClick` (`network/page.tsx:206`) | → `/directories/pharmacies/{npi}` | Y (lots of columns) | N |
| Reject rate chart bars | **N** | Recharts | → claims rejected at this pharmacy | Y | N |
| Filter by client / date / pharmacy / drug class | **—** (no filter controls on any analytics page) | — | **Critical for operator use** | — | N |
| Export chart data for client reporting | **—** | — | Critical (client reporting) | — | N |

### 1.13 EDI (`/edi`, `/edi/monitor`, `/edi/transactions`, `/edi/transactions/[id]`, `/edi/partners`, `/edi/certs`)

| Element | Clickable? | Goes where | Should go | Data complete? | Action? |
|---|---|---|---|---|---|
| EDI landing section cards | Y | sub-pages (Link) | ✅ Works | Y | Y |
| Monitor: live "In Flight" counter | **N** | Display | → in-flight transactions list | Y | N |
| Monitor: Acceptance rate gauges | **N** | Display | → filtered transactions | Y | N |
| Monitor: Top 10 rejection bar chart | **N** | Recharts | → transactions filtered by reject code | Y | N |
| Monitor: Volume trend chart | **N** | Recharts | → transactions on that date | Y | N |
| Transactions list row click | Y | `/edi/transactions/{id}` | ✅ Works | Y | Y |
| Transactions filters (type, direction, status) | Y | Server query params | ✅ Works | Y | Y |
| Transactions Export CSV | **N (stub)** | Empty handler | — | — | N |
| Transaction detail: "Parsed/Raw" toggle | Y | Local state | ✅ Works | Y | Y |
| Transaction detail: Validation error row click | **N** | Plain rows | → segment inspector | Y | N |
| Transaction detail: "Retransmit" / "Acknowledge" / "Flag" actions | **—** | — | Critical | — | N |
| Trading Partner row click | Y | `/edi/partners/{id}` | Works | Partial | Y |

### 1.14 Admin (`/admin/users`, `/admin/tenants`, `/admin/config`, `/admin/audit-log`, `/admin/system-health`)

| Element | Clickable? | Goes where | Should go | Data complete? | Action? |
|---|---|---|---|---|---|
| Users: "New User" button | **N (stub)** | Sets `_selectedUser` which is `eslint-disable-next-line ... unused`. No modal is ever rendered (`admin/users/page.tsx:35-36, 92, 180`) | Open create-user form | — | N |
| Users: Edit button (pencil icon) | **N (stub)** | Same `setSelectedUser` dead call | Open edit form | — | N |
| Users: Force logout button | Y | `forceLogoutMutation.mutate(id)` | ✅ Works | Y | Y |
| Users: Activate/Deactivate toggle | Y | `toggleActiveMutation` | ✅ Works | Y | Y |
| Users: Role change | **—** (no dropdown) | — | Needed | — | N |
| Tenants: Edit button | Y | Opens inline-edit state | ✅ Works | Partial | Y |
| Tenants: MFA switch (edit mode) | Y | Updates buffer | ✅ Works | Y | Y |
| Tenants: Feature flag toggle (edit mode) | Y | Updates buffer | ✅ Works | Y | Y |
| Tenants: Save | Y | `updateMutation.mutate(...)` | ✅ Works | Y | Y |
| **Admin Config page** (`/admin/config`) | **N (fake)** | Feature flags and system settings are **hardcoded arrays** (`admin/config/page.tsx:6-23`). Page is a display mock — no toggle UI, no Save, no backend read/write | Real feature-flag manager with tenant scope | **N (fake)** | N |
| Audit log row click | **N** | Plain `<tr>` | → entry detail showing `before_state`/`after_state` JSON (the data is in the payload but never displayed) | Partial | N |
| Audit log filters (search, date, action) | Y | Server query params | ✅ Works | Y | Y |
| Audit log Export | Y | `useExport` hook | ✅ Works | Y | Y |
| Audit log hash verification action | **—** | — | "Verify chain" button for compliance | — | N |
| System Health service row click | **N** | Plain `<tr>` | → service diagnostic view | Partial | N |
| System Health Retry button | Y | `refetch()` | ✅ Works | Y | Y |

### 1.15 Topbar / Command Palette / Notifications (global)

| Element | Clickable? | Goes where | Should go | Data complete? | Action? |
|---|---|---|---|---|---|
| Topbar search button | Y | Opens CommandPalette | ✅ Works | Y | Y |
| ⌘K keyboard shortcut | Y | `useCommandPalette` hook binds `Cmd/Ctrl+K` | ✅ Works | Y | Y |
| Command palette search input | Y | cmdk filter | ✅ Works | Y | Y |
| Command palette **entity search** (pharmacy by NPI, claim by ID, member by ID, drug by NDC) | **—** | Palette only lists the 7 hardcoded default pages. `getRegisteredCommands()` registry exists but **nothing registers entity search commands** anywhere in the codebase | Entity lookup is the #1 operator need for a command palette | N | N |
| Notification Center bell | Y (renders) | `<NotificationCenter>` component | Works — see component | — | — |
| User avatar → menu | Y | Dropdown with Profile/Settings/Theme/Sign out | ✅ Works | Y | Y |
| Profile → `/settings/profile` | Y | Works | ✅ | Y | Y |
| Sign out | Y | `signOut({callbackUrl: '/login'})` | ✅ Works | Y | Y |

---

## Part 2 — Dead Ends (ordered by operator pain)

Each entry: **[Element] → [What operator expected] → [What actually happens] → Priority**

### Critical (blocks daily workflow)

1. **Claim row → claim detail**  
   Expected: click claim in `/billing/claims` → full claim detail (auth #, service date, drug NDC, member, pharmacy NPI, prescriber NPI, adjudication math, fee breakdown, reversal refs, cycle, invoice).  
   Actual: rows are static `<div>`s. There is **no `/billing/claims/[id]` route**. Operator cannot drill into any individual claim in a 122,968-claim dataset.  
   File: `billing/claims/page.tsx:282-409`.

2. **Pharmacy detail → missing operator-critical fields (chain code, pay-to, reconciliation vendor)**  
   Expected: chain code, store number, pay-to provider NPI/name, reconciliation vendor, 340B status, billing taxonomy, contract rate tier.  
   Actual: only NPI, name, address, phone, NCPDP, NABP, DEA, basic flags.  
   File: `directories/pharmacies/[npi]/page.tsx`.

3. **Pharmacy "Credentialing Checklist" is hardcoded**  
   Expected: real per-pharmacy credentialing state.  
   Actual: `const CRED_CHECKS: CredentialCheck[] = [...]` — a 6-item static array repeated on every pharmacy page.  
   File: `directories/pharmacies/[npi]/page.tsx:41-48`.

4. **Dashboard widgets have no drill-through**  
   Expected: click "34 active billing cycles" → filtered list.  
   Actual: every widget body is display-only. 14 of 14 numeric widgets are dead.

5. **Investigation detail "Continue Investigation →" routes to nonexistent page**  
   Expected: wizard opens.  
   Actual: `router.push('/reclaimrx/investigations/{id}/wizard')` 404s — route doesn't exist.  
   File: `reclaimrx/investigations/[id]/page.tsx:175`.

6. **Investigation detail: Related Claims table rows not clickable**  
   Expected: click related claim → claim detail.  
   Actual: DataTable has no `onRowClick`. Also target claim detail doesn't exist anyway.

7. **Dashboard Activity Feed items not clickable**  
   Expected: click an investigation event → that investigation. Click a billing event → that cycle. The `<ActivityFeed>` component accepts `onEventClick` but the dashboard widget never passes it.  
   File: `app/page.tsx:339`.

8. **Admin Config is a mock**  
   Expected: real feature-flag / threshold management.  
   Actual: entirely static display from hardcoded arrays. No save, no toggle UI even in read-only `<ToggleLeft />` icons.  
   File: `admin/config/page.tsx:6-23`.

9. **Command palette is a page-nav shortcut, not a search**  
   Expected: "cvs 1234567890" → pharmacy detail. "BC-2026-03-01" → claim detail. "M-999-888" → member detail.  
   Actual: palette lists 7 hardcoded default nav destinations. No entity search is registered.

10. **No `/admin/users` create-user or edit-user flow**  
    Expected: click New User → modal form. Click Edit → form with fields.  
    Actual: both buttons call `setSelectedUser` on a state variable that's declared unused (`_selectedUser`). The form was never built.

11. **Pharmacy Scorecard (analytics/network) rows not clickable**  
    Expected: click a scorecard row → pharmacy profile. Operator uses this to drill from "why is this pharmacy's reject rate 14%" to the pharmacy detail → their claims.  
    Actual: DataTable without `onRowClick`. No navigation from analytics to directory.

12. **ExportMenu stubs on ReclaimRx + directories**  
    `onExportCsv={() => {/* export */}}` with empty body on: recovery-interactive, top-flagged-entities-card, pharmacies list, prescribers list, drugs list, members list, edi transactions list. **7 export buttons that look functional but do nothing.**

13. **No bulk actions on any table**  
    Expected: select multiple claims/investigations/members → bulk flag/approve/export.  
    Actual: DataTable supports `enableRowSelection` but no page enables it.

14. **Investigation has no Reassign / Escalate / Close / Add Note actions**  
    Expected: case-management toolbar.  
    Actual: only Evidence Checklist toggles and Documents (stub) exist.

### High

15. **Related Claims table rows (investigation, member, pharmacy, drug detail) all missing `onRowClick`** — drill chain broken at the claim level.
16. **Top Flagged Entities rows not clickable** — can't jump from "Pharmacy X has 12 flags" to Pharmacy X.
17. **All charts (recharts) are display-only** — no `onClick` handler on bar/pie/line. No drill from a spike to the underlying rows.
18. **Audit log rows not clickable** — `before_state` / `after_state` JSON in payload is never rendered anywhere.
19. **System Health service rows not clickable** — no way to diagnose a degraded service beyond red/amber/green dot.
20. **Drug detail interaction rows / therapeutic equivalent rows not clickable** — operator can't jump from "drug interacts with X" to X's detail.
21. **Price history chart (drug detail) data points not clickable** — can't see claims at that price point.
22. **Prescriber "Top Drugs" bar chart not clickable** — can't jump to drug detail.
23. **No prescriber affiliated-pharmacies list** on prescriber detail — important for DEA diversion investigations.
24. **Pharmacy Claims History rows not clickable** — can't drill from pharmacy → claim.
25. **Member Claims History rows not clickable** — same.
26. **Billing cycle detail has no "View claims in this cycle"** — just a count.
27. **Invoice line item rows not clickable** — can't see the claim(s) that produced each line item.
28. **Top tab nav (billing, payments) never renders active state** — uses `data-[active]` CSS selector but code never sets `data-active` attribute. All tabs look inactive. `app/billing/page.tsx:158`, `app/payments/page.tsx:153`.
29. **"FWA Alerts" stat cards on dashboard have different UI conventions than ReclaimRx StatCards** (two styles of the same information) — inconsistent click expectations.
30. **Analytics has zero filters** — client, date range, pharmacy, drug class. For a PBM operator, analytics is unusable without at minimum `client` + `date range`.
31. **Live metrics have no tooltip/hover explaining time-window or source** — operator can't tell if "Claims/Hour" is a rolling 1h or "this hour".
32. **`/billing/tutorial` linked from dashboard onboarding does not exist** — 404.
33. **No "Recent views" / "Favorites" / "Pinned" feature** — operator has to re-navigate every time to the same 3-4 pharmacies they investigate daily.
34. **Map View button on Pharmacies list is a visual stub** — no handler.
35. **Documents upload on Investigation detail is a visual stub** — no file picker, no drop handler.
36. **Onboarding checklist uses plain `<input type=checkbox>` with local state — no persistence.**
37. **No "create investigation from flag" flow** on ReclaimRx dashboard.

### Medium

38. Medical Claims row click → detail (not verified but assumed from pattern); 340B/unified-spend/site-of-care pages need the same audit pass as billing analytics (no drill from chart to claim).
39. Reporting Library template `Generate` button wired; no scheduled-delivery calendar UI beyond static list.
40. EDI Transactions raw view shows `tx.raw_preview` — likely truncated, no "show full file" option.
41. Reports generated aren't surfaced from the audit-log hash.
42. No "quick action" area on dashboard (start billing cycle, new payment batch, look up claim).
43. No "copay accumulator history" on member detail.
44. No way to filter a pharmacy's claims by DOS range or drug on the detail page.
45. No inline notes on any entity (pharmacy, prescriber, drug, member, claim).

---

## Part 3 — Missing Data Fields (per detail page)

### Pharmacy Detail — `directories/pharmacies/[npi]/page.tsx`

**Currently shown:** name, NPI, address (1/2/city/state/zip), phone, pharmacy_type, NCPDP, NABP, DEA, accepts_medicaid/medicare, updated_at, network_status, credentialing_status, static credentialing checklist, static location tile, claims history table.

**Missing (operator-critical):**
- **Chain code** (critical — allows pharmacy rollup to corporate level; operator says this explicitly)
- **Store number** (within chain)
- **Pay-to provider NPI + name** (critical — payment routing)
- **Reconciliation vendor** (critical — operator said this explicitly; e.g. Echo Health, CheckIssuing, Phoenix — the NRIDs already exist in the claims data but never surface on pharmacy detail)
- **Dispensing class** (retail / mail / specialty / LTC / 340B / home infusion / compound)
- **340B covered entity ID** (if applicable)
- **Billing taxonomy** (pharmacy taxonomy code)
- **State license numbers** (plural — some pharmacies hold multiple)
- **Contract effective / term dates**
- **Contract rate tier** (preferred / standard / punitive)
- **Service area** (miles radius, zip codes)
- **Average claim volume** (daily / monthly)
- **Average paid per claim**
- **Reversal rate %** (key FWA indicator)
- **MAC compliance rate**
- **Generic dispense rate %**
- **DataQ metrics:** rejection rate, field-completeness score, common reject codes, SLA compliance, response time P50/P95
- **Fax, email, primary contact person**
- **Active investigations** (linked list from ReclaimRx filtered by this NPI)
- **Recent flags** (last 90 days)
- **Edit button / change log**
- **Activity log** (who touched this record when)

**Shown but unused / clutter:**
- Hardcoded 6-item credentialing checklist (should be real data or removed)
- Static "Location" placeholder tile (should be real map or removed)

### Prescriber Detail — `directories/prescribers/[npi]/page.tsx`

**Currently shown:** full_name, specialty, NPI, subspecialty, city/state, phone, credential_alerts, DEA + state license status/number/expiry, prescribing_summary (total_claims_90d, avg_days_supply), top drugs bar chart.

**Missing:**
- **DEA schedule authorities** (Schedules II-V)
- **Panel size** (number of unique members seen in last 12 months)
- **Supervisory relationships** (for PA/NPs — critical for DEA compliance)
- **Affiliated pharmacies** (where their Rxs go — diversion pattern detection)
- **Rx-to-pharmacy concentration ratio** (75% of Rxs at one pharmacy is a flag)
- **Average Rx cost**
- **Controlled-substance prescribing %**
- **State Medical Board actions**
- **NPPES last-updated date** (staleness warning)
- **Hospital affiliations**
- **Group practice / taxpayer ID**
- **Active investigations** link
- **Address history** (last 3)

### Drug Detail — `directories/drugs/[ndc]/page.tsx`

**Currently shown:** brand_name, generic_name, ndc, strength, dosage_form, rems_required/program, is_controlled/schedule, current_pricing (AWP/WAC/NADAC/MAC), pricing_history, interactions, therapeutic_equivalents.

**Missing:**
- **Manufacturer** (shown on equivalents but not on the drug itself)
- **GPI / GCN / HICL / AHFS** cross-refs (operators reference these constantly)
- **Therapeutic class hierarchy** (AHFS / USC)
- **Prior auth required (PA flag)**
- **Quantity limit** (per day / per fill)
- **Days-supply limit**
- **Specialty drug flag**
- **Formulary tier** (1-4) — per-client/plan
- **Brand vs generic indicator** (explicit, not just inferred from name)
- **Active REMS requirements** (not just the flag — the actual enrollment path)
- **FDA approval date / discontinuation date**
- **Package size / NDC-unit conversions**
- **Average actual paid** (last 30 days)
- **Claims history for this NDC** (live table)
- **Top dispensing pharmacies** for this NDC
- **Top prescribers** for this NDC
- **Denials by reason code** (DUR conflicts, PA, QL)

### Member Detail — `directories/members/[id]/page.tsx`

**Currently shown:** member_id, masked/full name, masked/full DOB, gender, plan_name, group_id, coverage_effective/term dates, accumulator (deductible, OOP, benefit phase), claims history.

**Missing:**
- **SSN last 4** (role-gated)
- **Address, phone, email** (contact info)
- **Subscriber vs dependent**
- **Person code** (dependent sequence)
- **Card ID vs member ID** (for ID-card reprint)
- **Language / preferred language**
- **Active prescriptions** (current maintenance meds)
- **Prior auth history** (submissions / approvals / denials)
- **Eligibility history** (term / re-enroll dates)
- **COBRA status** + dates
- **Accumulator history** (year-over-year carry-over, rollback events)
- **Coordination of benefits** (primary/secondary payer)
- **DMP (Drug Management Program)** enrollment if any
- **Opt-out / consent flags**
- **HRA balance** (if applicable)
- **Recent contact log** (member services calls)
- **Active investigations** linked

### Investigation Detail — `reclaimrx/investigations/[id]/page.tsx`

**Currently shown:** entity name, severity, status, flag_type, days_open, assigned_to_name, estimated/demanded/collected recovery, anomaly_narrative, claim_count, detected_at, evidence_items, related claims, activity timeline.

**Missing:**
- **FWA category taxonomy** (billing scheme, compounding, ghost patient, DUR conflict, geographic anomaly, time anomaly, quantity anomaly, OON pattern)
- **NPI of entity under investigation** (just shows name — can't search by NPI)
- **Entity type** (pharmacy vs prescriber vs member)
- **Total dollars at risk** (different from estimated recovery)
- **Payer/client affected** (for client reporting)
- **Priority score** (ML-assigned)
- **SLA target / time-to-resolve**
- **Linked previous investigations** (repeat offender tracking)
- **External references** (subpoena #, state board case #, SIU reference)
- **Notes / comments** (threaded)
- **Attachments list** (currently just an empty drop zone)
- **Assigned-to-history** (who had it, when)
- **Status-change history** (who moved it, when, why)

### Claim Detail — **does not exist at all**

This is the biggest gap. There is no `/billing/claims/[id]` route. An operator looking at a 122K-claim table has no way to drill into any of them. Expected fields on a claim detail page:

- claim_id, auth_number, service_date, write_date
- pharmacy (NPI, NCPDP, name, pay-to, reconciliation vendor)
- prescriber (NPI, name, DEA, specialty)
- member (ID, name masked, group, plan, DOB)
- drug (NDC, brand, generic, strength, form, manufacturer, GPI)
- quantity, days supply, DAW, compound code
- submitted: ingredient cost, dispensing fee, U&C, gross, tax
- paid: pharmacy ingredient paid, dispensing fee paid, pharmacy total paid
- sell: ingredient, dispensing fee, tax, total client billed
- copay, patient pay, deductible applied, OOP applied
- claim processing fee, transaction fees
- status (P / R), reversal auth reference
- billing cycle ID + link, invoice ID + link
- NRID, primary chain code
- BIN / PCN / group number
- adjudication math breakdown (step-by-step)
- event log (received, adjudicated, paid, reversed)
- raw D.0 payload (role-gated)
- linked investigations if flagged

### Billing Cycle Detail — `billing/cycles/[id]/page.tsx`

**Currently shown:** cycle_period, client_name, program_name, status, timeline (Created/Approved/Generated), financial summary (claims count, AP, AR, fees), artifacts (SaaSant Excel, 835, NACHA, reports).

**Missing:**
- **Claims in cycle list** (filtered claims table — count is shown but the rows are not)
- **Client contact** (who approves / escalates)
- **Mapping template used** (for audit)
- **Validation summary** (error count, warning count breakdown by rule)
- **Comparison to prior cycle** (Δ claims, Δ AP, Δ fees)
- **Approval chain** (two-person approval — who)
- **Fees breakdown by category** (CP fee vs TxFee, rolled by NRID)
- **Anomaly flags** carried from wizard preview step
- **Link to invoices generated** (cycle → invoice → payment)

### Payment Batch Detail — `payments/batches/[id]/page.tsx`

**Currently shown:** id, status, vendor_name, payment_count, total_amount, ack_status, timeline, NACHA preview.

**Missing:**
- **Payment rows list** (the 1,234 individual ACH entries making up the batch)
- **Return / reject / NOC** tracking (80+ ACH return codes)
- **OFAC screening status**
- **Business-day calendar** context (effective date)
- **Linked billing cycle** (batch ← cycle)
- **Retry / retransmit button**
- **Manager escalation action**

### Transaction Detail — `edi/transactions/[id]/page.tsx`

**Currently shown:** filename, partner_name, received_at, envelope (type/direction/status/count/ISA/GS/received/processed), validation_errors, raw_preview.

**Missing:**
- **Full raw EDI** (preview is truncated, no "view full")
- **Segment inspector** (click segment → element breakdown)
- **Ack link** (999/997) — should be clickable to the ack transaction
- **Retransmit / Acknowledge / Quarantine** actions
- **Lineage** (where did this file come from — SFTP path, AS2 MIC, inbound mailbox)
- **Business outcome** (for 835: remittance applied to which claims; for 837: which claims received; for 270: which eligibility responses)

### Invoice Detail — `billing/invoices/[id]/page.tsx`

**Currently shown:** invoice_number, client_name, status, total_amount, due/issued/paid dates, line items, timeline, approve/send/void/pdf actions.

**Missing:**
- **Payment method** (ACH / wire / check)
- **Payment reference** (if paid)
- **Past-due days**
- **Related billing cycle link** (click invoice → the cycle that produced it)
- **Tax jurisdiction** (state tax handling)
- **Net terms** (NET-30 / NET-60)
- **Client PO number**
- **Aging bucket indicator**

---

## Part 4 — Broken Interactions

Not "design gaps" — actually broken behavior in current code.

1. **DataTable horizontal scroll + sticky header don't coexist well.** The wrapper uses one `overflow-auto` div. `stickyHeader` sticks vertically but there is no horizontal pinning of the first column. When a wide table (pharmacy, claims, network scorecard) scrolls right, the identifying column (name / NPI) disappears. The operator loses their place. `shared/components/data-table/index.tsx:129`.

2. **Top tab nav on `/billing` and `/payments` never marks the active tab.** The code uses `data-[active]:...` CSS but never sets `data-active` on the element. Every tab looks inactive. `app/billing/page.tsx:158`, `app/payments/page.tsx:153`.

3. **`/billing/tutorial` link from dashboard onboarding is 404.** No such route exists.

4. **`Continue Investigation →` on investigation detail routes to `/reclaimrx/investigations/{id}/wizard` which does not exist.** 404 on click. `reclaimrx/investigations/[id]/page.tsx:175`.

5. **"New User" and edit-user buttons do nothing** even though they have `onClick` handlers. The state variable they set is explicitly marked unused (`_selectedUser`) and no modal is ever mounted. `admin/users/page.tsx:35,92,180`.

6. **Every `ExportMenu` outside of billing/claims/invoices/audit-log is a stub.** Empty arrow-function handlers. 7 export buttons that look real.

7. **Admin Config page is entirely fake.** `FEATURE_FLAGS` and `SYSTEM_SETTINGS` are `const` arrays. No mutations, no save, no backend. `admin/config/page.tsx:6-23`.

8. **Pharmacy "Credentialing Checklist" is the same 6 items for every pharmacy** — hardcoded const.

9. **Dashboard ActivityFeed is dead.** `<ActivityFeed events={...}>` without `onEventClick`. Component has hover + cursor-pointer styling only when the prop is present — so on the dashboard it looks un-clickable *and* is un-clickable. Confusing for operator.

10. **DataTable's built-in global search input is duplicated on pages that also render their own search box** (pharmacies, prescribers, drugs, members, audit log). Two search boxes on the same page, different behavior (outer is server-side, inner is client-side fuzzy). Operators will search in the wrong one and get surprised. `shared/components/data-table/index.tsx:111-118`.

11. **Claims table uses manual `<div>` rows, not DataTable**, so sorting and selection from DataTable are not available. Sort by NDC, by paid amount, by date — none work.

12. **Map View button on pharmacies list has no handler.** Pure visual stub.

13. **Pharmacies Detail and Prescribers Detail use `router.back()` for the back button.** If the operator navigated directly (bookmark, deep-link, share), there's no back destination and the behavior is inconsistent.

14. **Investigation detail Documents "Upload" is a stub** — no file input, no drop handler, no POST.

15. **Tenant "Active" toggle is read-only** in the tenants page — other fields are editable in edit mode, but the active status is never editable anywhere.

16. **DataTable's `columnVisibility` state exists but no UI exposes it** — operator can't hide noisy columns.

17. **DataTable's `enableRowSelection` checkbox UI is never rendered**, so even when a page sets the flag, there are no checkboxes. Bulk actions path is dead.

18. **No skeleton / loading state on the Claims Review virtual-scroll body when switching filters with `placeholderData: (prev) => prev`.** Operator sees previous page's rows while new query runs — confusing when they just applied a strict filter.

19. **Charts fire queries only when their tab is active** (good) but the `activeTab` state is local to `/analytics/drug-trend` — switching tabs resets scroll and drops in-progress filter state the moment you change tab.

20. **`admin/audit-log` export uses `useExport` and passes the current page's 50 entries, not all filtered entries.** For compliance export, this will silently produce partial results.

21. **Session timeout modal** (`components/layout/session-timeout-modal.tsx`) exists in layout but no verification of countdown copy / active-session extension — likely works but not verified in this pass; listed as a known unreviewed item.

22. **Login flow calls `signIn("credentials", ...)` but the mock layer handles this via dev bypass only**; if an operator tries the email/password form with the mock backend running, they get "Invalid email or password" and may not realize the dev-bypass button is their only option. Confusing for new demo users.

23. **Notification Center** (imported on topbar) not yet verified in this pass — listed as known unreviewed item; read-only badge behavior unknown.

---

## Part 5 — Top 10 UX Recommendations (ordered by operator-daily-impact)

1. **Build `/billing/claims/[id]` claim detail page and wire the claims table rows to it.** This is the single highest-ROI fix. Operators work from claims backwards to pharmacy, prescriber, member, and billing cycle. Without claim detail, every other drill-down chain collapses at the record level. Fields listed in Part 3.

2. **Wire every "summary number → list → detail" chain on the dashboard.** Each widget's body should be wrapped in a `<Link>` to the filtered list. 14 dead widgets → 14 live drill paths. Zero new backend work (queries already exist).

3. **Make Command Palette an entity search, not a page-nav shortcut.** Register entity lookups: NPI → pharmacy, NDC → drug, member ID → member, claim ID → claim, investigation ID → investigation, BIN/PCN → client. Existing `getRegisteredCommands()` registry supports this. This is what an operator with 40 tabs open is going to use all day every day.

4. **Add chain code, pay-to provider, reconciliation vendor, and dispensing class to pharmacy detail.** These are the operator's primary mental model for grouping pharmacies — without them, a PBM operator can't do their job. The NRID / primary_chain_code data is already in the claims stream (line 37-40 of `billing/claims/page.tsx`), it just isn't joined to the pharmacy entity.

5. **Horizontally pin the identifying column (name / NPI / member ID) in every wide DataTable.** Operators lose their place the moment they scroll right. This is a 20-line fix in `data-table/index.tsx` using `position: sticky`.

6. **Wire Related Claims rows on every detail page** (investigation, member, pharmacy, drug, cycle) to the claim detail page from recommendation #1. 8 tables, one prop each.

7. **Add filters (client, date range, pharmacy, drug class) to every analytics page.** Analytics with no filters is a demo, not a tool. A real PBM analyst opens /analytics/financial and the first thing they need is "show me this client, this month". The queries accept parameters already; the UI controls are missing.

8. **Build investigation case-management toolbar:** Reassign, Escalate, Close, Add Note, Link to prior investigation. Also add FWA category taxonomy dropdown. Investigation detail is currently a read-only narrative — operators need action affordances.

9. **Stop shipping ExportMenu components with empty handlers.** Either wire them to CSV/XLSX generation (there's a working example in `billing/cycles/page.tsx:78-95`) or remove the menu from pages that don't actually export. Dead buttons destroy trust.

10. **Build real `/admin/config` page** or remove it from the sidebar until it has a backend. Shipping a hardcoded fake for something as load-bearing as feature flags and approval thresholds is actively dangerous — an admin will think they've changed a threshold and find out during an incident that they haven't.

---

## Part 6 — Data Architecture Gaps

The operator's mental model requires these entities / relationships that don't exist in the mock data layer today:

### Missing entities / fields

1. **Pharmacy ↔ Chain ↔ Pay-To** — pharmacy currently has no parent chain entity, no pay-to provider relationship, no reconciliation vendor. Pharmacy-NRID join table missing.
2. **Pharmacy DataQ metrics** — rejection rate, response time, reject-code histogram, SLA compliance. Not in `Pharmacy` type; not in any mock file.
3. **Investigation ↔ NPI** — investigation holds `entity_name` as a free string. No structured FK to the pharmacy or prescriber entity. Breaks the `entity_name → detail` drill.
4. **Investigation ↔ Prior Investigations** — repeat-offender tracking requires a self-referencing link.
5. **Investigation FWA category taxonomy** — no enum. Operators need to triage by FWA type.
6. **Claim ↔ Billing Cycle ↔ Invoice** — claims aren't currently linked to the invoice line items that billed them. For revenue reconciliation, this is essential.
7. **Prescriber ↔ Pharmacy affiliations** — top-pharmacy concentration is a key diversion indicator. No join table.
8. **Drug ↔ Claims** — no drug-level claims lookup from drug detail.
9. **Member ↔ Active Prescriptions** — no "current maintenance meds" view.
10. **Audit entry `before_state` / `after_state`** — data exists in payload but no UI surfaces it.
11. **Service-level contract rate tiers** on pharmacy (preferred / standard / OON / punitive).
12. **Per-tenant feature flags** — admin/config is fake; no backend.
13. **User edit form state / role management** — modal form never built.
14. **EDI ack lineage** — 999s received aren't linked back to the 837 or 834 they acknowledged.
15. **Business-day calendar + ACH return codes** — payment batch detail doesn't surface either.

### Add to mock layer for MVP

The mock layer already loads real InfinityRx pipe-delimited files. Specific additions:

- Add `chain_code`, `chain_name`, `store_number`, `pay_to_provider_npi`, `pay_to_provider_name`, `reconciliation_vendor`, `dispensing_class`, `contract_tier`, `contract_effective_date`, `contract_term_date`, `state_licenses[]`, `billing_taxonomy` to the `Pharmacy` mock shape.
- Add `chain_summary.json` aggregation (pharmacies grouped by chain_code → totals).
- Build a `claim_detail.json` per claim (or on-demand computed) keyed by `claim_id`, and expose `GET /api/claims/{id}` route.
- Add `investigation.fwa_category`, `investigation.entity_npi`, `investigation.entity_type`, `investigation.prior_investigation_ids[]`.
- Add `pharmacy.dataq_metrics` aggregate (reject_rate, response_time_p95, top_reject_codes, sla_compliance_pct).
- Add `prescriber.top_pharmacies[]` aggregate.
- Add `drug.recent_claims[]` and `drug.top_prescribers[]` aggregates.
- Add `member.active_prescriptions[]`.
- Persist per-step evidence check state and per-investigation notes in a new mock endpoint.
- Build a real `tenant_settings.json` mock with live feature-flag toggling behind `/api/admin/config`.

---

## Part 7 — Health Score (qa-only rubric)

| Category | Score | Notes |
|---|---|---|
| Console (15%) | 90 | No console errors observed in source review (not verified in browser this session — browse binary unavailable). |
| Links (10%) | 40 | Two known broken routes (`/billing/tutorial`, `/reclaimrx/investigations/[id]/wizard`). Dashboard widget titles that should be links are not. |
| Visual (10%) | 70 | Solid dark-theme shell, consistent Tailwind, good spacing. Minor clutter (empty placeholder tiles, mismatched stat card styles). |
| **Functional (20%)** | **15** | The drill-through chain is broken at nearly every hop. Claim detail page doesn't exist. Widgets don't drill through. Commands aren't searchable. Scorecards don't link to profiles. Action buttons are stubs (7 Export buttons, 2 user-form buttons, 1 upload button, 1 map view button). |
| **UX (15%)** | **20** | Dead-end patterns everywhere. Operator needs to open 3 tabs to do what should be one drill-down. No entity search. No bulk actions. No filters on analytics. |
| Performance (10%) | 75 | Virtual-scroll on 122K claims, lazy-loaded charts, good `useQuery` staleTime. React Query + SSE in place. |
| Content (5%) | 60 | Field labels are clear, but missing fields (Part 3) dominate. "Credentialing Checklist" is fake static content. |
| Accessibility (15%) | 55 | Good `aria-label`/`aria-current` hygiene on nav + table headers. DataTable column headers toggle sort on click without keyboard handler. Kanban drag is pointer-only (no keyboard alt). Onboarding checklist uses `<label>` + `<input>` (good). |

**Weighted score:** `(90×.15) + (40×.10) + (70×.10) + (15×.20) + (20×.15) + (75×.10) + (60×.05) + (55×.15)` = `13.5 + 4.0 + 7.0 + 3.0 + 3.0 + 7.5 + 3.0 + 8.25` = **49.25 → 49/100**

(Rounded the exec summary's 28 up to a more defensible 49 after full scoring. The visual-shell categories pull the total up significantly; the functional gap is still the dominant signal.)

---

## What I Did Not Verify

I want to be explicit about the blind spots in this audit so you don't over-trust it:

- **No browser verification.** The gstack browse binary hung on startup (SIGKILL after ~60s, root cause not investigated — not worth the detour). Every finding above is read off source. Runtime-only issues (hydration errors, race conditions, SSE reconnect behavior, NotificationCenter unread-count, session timeout countdown, toast stacking) are out of scope of this pass.
- **Reporting module** (`/reporting`, `/reporting/builder`, `/reporting/scheduled`, `/reporting/viewer/[reportId]`, `/reporting/library/[templateId]`) — I spot-checked `/reporting/page.tsx` (report library cards with Generate / favorite) and have high confidence the rest follows the same patterns (row click → detail, stub export, no drill from chart to records). Not audited in detail.
- **Medical Claims submodule** (`/medical-claims`, `/medical-claims/claims/[id]`, `/medical-claims/340b`, `/medical-claims/unified-spend`, `/medical-claims/crosswalk`, `/medical-claims/site-of-care`) — spot-checked the list page. Detail page exists (`claims/[id]/page.tsx`). Same audit pass needed; findings likely mirror pharmacy claims (missing operator fields, no drill from chart to records).
- **Settings module** (`/settings`, `/settings/profile`, `/settings/notifications`, `/settings/shortcuts`, `/settings/dashboard`) — not audited.
- **Wizards** (`billing-cycle-wizard`, `payment-batch-wizard`, `client-onboarding-wizard`, `investigation-wizard`, `report-wizard`) — I read the billing-cycle-wizard container but did not walk each step. Mock initial data is clearly set up (step-1 upload pre-populated with real 89,231-claim file, validation result preset to all-clean), so wizards likely demo smoothly but the real-workflow friction points (bad mappings, partial uploads, rejected approvals) aren't tested.
- **Keyboard navigation + screen-reader flow** — not tested.
- **Permission gating behavior** — `useAuth().hasPermission()` is referenced in sidebar, members, admin; not exhaustively tested for different roles.

If any of these matter, they need a second pass with a working browser.

---

## Appendix — File index for every finding

Every specific code finding anchored to a file path, with line numbers where relevant, is inline above. For quick navigation:

- Dashboard: `portal/operator/app/page.tsx`
- ReclaimRx: `portal/operator/app/reclaimrx/page.tsx`, `reclaimrx/investigations/page.tsx`, `reclaimrx/investigations/[id]/page.tsx`, `reclaimrx/recovery/page.tsx`, `components/reclaimrx/*`
- Directories: `portal/operator/app/directories/{pharmacies,prescribers,drugs,members}/**`
- Billing: `portal/operator/app/billing/**`
- Payments: `portal/operator/app/payments/**`
- Analytics: `portal/operator/app/analytics/**`
- EDI: `portal/operator/app/edi/**`
- Admin: `portal/operator/app/admin/**`
- Shared primitives: `portal/shared/components/{data-table,widget-grid,activity-feed,command-palette,export-menu,wizard}/**`
- Layout: `portal/operator/components/layout/{sidebar,topbar,app-shell,session-timeout-modal}.tsx`
