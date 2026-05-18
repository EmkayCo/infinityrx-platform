# SP-2 Plan B — 6 Browse Clusters, Per-Dataset Surfaces, CommandPalette Extension

**Status:** DRAFT  
**Date:** 2026-05-17  
**Vertical:** SP-2 Directories Portal / Reference Data Control Plane  
**Spec ref:** `docs/superpowers/specs/2026-05-16-sp2-directories-portal-design.md` §6.3, §6.2  
**Depends on:** Plan A (module scaffold, search spine, FederatedSearchClient, schemas)  

---

## Purpose

Plan B wires the 6 browse clusters into the search spine and extends the existing
`portal/operator/app/directories/` pages into the SP-2 module package. It also
extends the existing `packages/ui/src/command/CommandPalette.tsx` to accept
grouped results and integrates `useDirectoriesSearch`.

**Migration decision (§10.4):**
SP-2 wraps and migrates existing pages from `portal/operator/app/directories/`
into the module package rather than duplicating them. The existing pages use
`@shared/lib/api-client.apiGet` with `API_URLS.*` constants directly. SP-2
moves these calls through the contract-layer BFF (SP-0 SD-4 pattern).
The old paths (`portal/operator/app/directories/prescribers/page.tsx`, etc.)
become thin re-export shells pointing to the new module pages — preserving
Next.js routing while isolating logic in the module package.

`members/` is explicitly excluded from SP-2. It is a member-management surface
and belongs in a future member-management UI vertical.

---

## Verified backend routes (pre-write grep confirmed)

All routes below confirmed against HEAD. Line numbers are the `@router.*` decorator lines.

### prescriber-directory (`modules/prescriber-directory/src/api/router.py`)

| Route | Line | Handler |
|---|---|---|
| `GET /api/v1/prescribers/lookup/{npi}` | 58 | `lookup_by_npi` |
| `GET /api/v1/prescribers/lookup/dea/{dea_number}` | 71 | `lookup_by_dea` |
| `GET /api/v1/prescribers/search` | 87 | `search_prescribers` |
| `GET /api/v1/prescribers/monitoring/alerts` | 344 | `list_alerts` |
| `GET /api/v1/prescribers/stats` | 381 | `directory_stats` (no `x-tenant-id` param — uses `TenantId` dependency) |
| `GET /api/v1/prescribers/relationships/{npi}/pharmacies` | 402 | `prescriber_pharmacy_relationships` |
| `GET /api/v1/prescribers/relationships/{npi}/stats` | 439 | `prescriber_relationship_stats` |
| `POST /api/v1/prescribers/refresh` | 470 | `trigger_nppes_refresh` |

### pharmacy-directory (`modules/pharmacy-directory/src/api/router.py`)

| Route | Line | Handler |
|---|---|---|
| `GET /api/v1/pharmacies/lookup/{npi}` | 120 | `get_pharmacy_by_npi` |
| `GET /api/v1/pharmacies/lookup/nabp/{nabp}` | 139 | `get_pharmacy_by_nabp` |
| `GET /api/v1/pharmacies/search` | 153 | `search_pharmacies` |
| `GET /api/v1/pharmacies/stats` | 440 | `directory_stats` — **MANDATORY** `tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")]` at line 442; BFF MUST pass `?x-tenant-id={tid}` |

### drug-database (`modules/drug-database/src/api/router.py`)

| Route | Line | Handler |
|---|---|---|
| `GET /api/v1/drugs/lookup/{ndc}` | 71 | `lookup_drug` |
| `GET /api/v1/drugs/search` | 84 | `search_drugs` |
| `GET /api/v1/drugs/pricing/{ndc}` | 122 | `get_pricing` |
| `GET /api/v1/drugs/pricing/{ndc}/history` | 155 | `get_pricing_history` |
| `GET /api/v1/drugs/rems/{ndc}` | 307 | `get_rems` |
| `GET /api/v1/drugs/shortages` | 320 | `list_shortages` |
| `GET /api/v1/drugs/shortages/{ndc}` | 332 | `get_shortage` |
| `GET /api/v1/drugs/refresh/status` | 345 | `refresh_status` |

---

## Existing portal pages (verified at HEAD)

| Portal path | File | Direct API call pattern |
|---|---|---|
| `portal/operator/app/directories/prescribers/page.tsx` | exists | `apiGet` to `${API_URLS.prescriberDirectory}/api/v1/prescribers/...` |
| `portal/operator/app/directories/prescribers/[npi]/page.tsx` | exists | `apiGet` to `${API_URLS.prescriberDirectory}/api/v1/prescribers/${npi}` |
| `portal/operator/app/directories/pharmacies/page.tsx` | exists | `apiGet` to pharmacy-directory |
| `portal/operator/app/directories/pharmacies/[npi]/page.tsx` | exists | `apiGet` to pharmacy-directory |
| `portal/operator/app/directories/drugs/page.tsx` | exists | `apiGet` to `${API_URLS.drugDatabase}/api/v1/drugs` |
| `portal/operator/app/directories/drugs/[ndc]/page.tsx` | exists | `apiGet` to drug-database |

`portal/operator/app/directories/members/` — excluded from SP-2. Future member-management SP.

---

## `API_URLS` / `portal/shared/lib/constants.ts` (confirmed)

```
prescriberDirectory: process.env.NEXT_PUBLIC_PRESCRIBER_DIR_URL ?? "http://localhost:8010"
pharmacyDirectory:   process.env.NEXT_PUBLIC_PHARMACY_DIR_URL ?? "http://localhost:8009"
drugDatabase:        process.env.NEXT_PUBLIC_DRUG_DATABASE_URL ?? "http://localhost:8011"
```

New env vars needed for Plan B server-side BFF (these are server-only, not `NEXT_PUBLIC_`):

```
PRESCRIBER_DIRECTORY_URL=http://prescriber-directory:8010
PHARMACY_DIRECTORY_URL=http://pharmacy-directory:8009
DRUG_DATABASE_URL=http://drug-database:8011
```

These are already declared in `module.config.ts` `requires.env` (Plan A D2).

---

## CommandPalette extension

**Existing:** `packages/ui/src/command/CommandPalette.tsx` exports `CommandPalette`,
`CommandPaletteProps`, `CommandItem`. The component accepts `items: CommandItem[]`
(flat list, no grouping). It has no dataset awareness.

**SP-2 extension strategy:** Create a new `DirectoriesCommandPalette` component in
`packages/modules/directories/src/search/` that wraps the existing
`CommandPalette` from `@infinityrx/ui` and adds:
- Grouped result rendering by cluster (Prescribers / Pharmacies / Drugs / Codes / Pricing / Exclusions)
- Integration with `useDirectoriesSearch`
- Keyboard navigation (inherit from cmdk via existing `CommandPalette`)
- B9 pending pill on results with `b9_blocked: true`
- "See all N in [dataset]" overflow link per group (max 3 visible per group)

This avoids modifying `packages/ui` (which would affect all portal consumers)
while still reusing the cmdk wrapper.

---

## Deliverables

### Cluster A: Prescribers surface (`src/surfaces/prescribers/`)

**D-B1 — `PrescribersListPage.tsx`**

Wraps existing `portal/operator/app/directories/prescribers/page.tsx`.
Migrates direct `apiGet` call to use `useDirectoriesSearch` (for the search
input) and a separate `useQuery` for paginated list load. The NPI shortcut from
the existing page (`NPI_PATTERN` at page.tsx:87) is preserved via the BFF's
ID shortcut detection in Plan A.

**D-B2 — `PrescriberDetailPage.tsx`**

Wraps existing `portal/operator/app/directories/prescribers/[npi]/page.tsx`.
Adds:
- `ProvenanceBadge` (from Plan A `src/components/`)
- `FreshnessChip` for the NPPES source
- `ExclusionAlertBadge` when the prescriber NPI appears in `cms_opt_out`
  or `sam_exclusions` (checked via BFF cross-link query — see D-B-BFF1)
- `PrescriberMonitoringPanel` — read-only list from `GET /api/v1/prescribers/monitoring/alerts` (line 344);
  alert acknowledgment is NOT in SP-2 scope per spec §3

**D-B3 — BFF route `GET /api/directories/prescribers/[npi]/exclusion-check`**

Fan-out: checks `cms_opt_out` and `sam_exclusions` for a given NPI.
Backend: future query to prescriber-directory's exclusion data (or BFF-internal
check against the existing exclusion surface query). Returns
`{ sources: DatasetKey[] }` — which exclusion sources match.

**D-B4 — Thin re-export shells (keep Next.js routing)**

```typescript
// portal/operator/app/directories/prescribers/page.tsx (REPLACE content)
export { PrescribersListPage as default } from "@infinityrx/module-directories";
```

```typescript
// portal/operator/app/directories/prescribers/[npi]/page.tsx (REPLACE content)
export { PrescriberDetailPage as default } from "@infinityrx/module-directories";
```

### Cluster B: Pharmacies surface (`src/surfaces/pharmacies/`)

**D-B5 — `PharmaciesListPage.tsx`** — wraps existing `pharmacies/page.tsx`;
migrates direct call; adds freshness indicator for `ncpdp` source.

**D-B6 — `PharmacyDetailPage.tsx`** — wraps existing `pharmacies/[npi]/page.tsx`;
adds `ProvenanceBadge`, `FreshnessChip` for `ncpdp`. Cross-link to prescriber
relationships via `GET /api/v1/prescribers/relationships/{npi}/pharmacies` (line 402).

**D-B7 — BFF route `GET /api/directories/pharmacies/[nabp]/detail`** (optional
aggregation for pharmacy + relationships in one call).

**Note on `x-tenant-id`:** BFF MUST pass `?x-tenant-id={tid}` when calling
`GET /api/v1/pharmacies/stats` (router.py line 442 — mandatory param, 422 without it).
BFF extracts `tid` from JWT `claims.tid` via `verifyAccessToken` (per Plan A D6 pattern).

### Cluster C: Drugs surface (`src/surfaces/drugs/`)

**D-B8 — `DrugsListPage.tsx`** — wraps existing `drugs/page.tsx`; migrates
direct call; adds freshness chip for `fda_ndc` source.

**D-B9 — `DrugDetailPage.tsx`** — wraps existing `drugs/[ndc]/page.tsx`;
adds `ProvenanceBadge`, `FreshnessChip`, tabbed sub-sections:
- **Pricing tab:** CMS-ASP (`GET /api/v1/drugs/pricing/{ndc}` line 122),
  CMS-NADAC (`GET /api/v1/drugs/pricing/{ndc}/history` line 155),
  BPG (read-only reference — no ingestion; show "Live API" label)
- **REMS tab:** `GET /api/v1/drugs/rems/{ndc}` (line 307)
- **Shortages tab:** `GET /api/v1/drugs/shortages/{ndc}` (line 332)
- **Interactions tab:** `B9PendingBanner` (dataType="interactions") — mock until B9 lands
- **Formulary tab:** `B9PendingBanner` (dataType="formulary") — mock until B9 lands
- **RxNorm** cross-link: `rxnorm` is a drug classification/terminology source.
  Drug detail links to RxNorm ID if available. No separate RxNorm detail page in SP-2
  (data in drug-database module).

**D-B10 — `B9PendingBanner` usage** — already built in Plan A; imported here.

### Cluster D: Codes surface (`src/surfaces/codes/`)

**D-B11 — `HcpcsListPage.tsx`** — NEW (no existing portal page).
HCPCS codes browser. List + search by code or description.
Backend: drug-database `GET /api/v1/drugs/search?type=hcpcs` or a dedicated
HCPCS endpoint if available. **Verification needed at execution time:**
`grep -n "hcpcs" modules/drug-database/src/api/router.py` — if no dedicated
HCPCS route exists, the BFF aggregates from `GET /api/v1/data-ingestion/field-catalog`
to confirm available fields and implements BFF-internal filtering.

**D-B12 — `Icd10ListPage.tsx`** — NEW (no existing portal page).
ICD-10-CM codes browser. List + search by code or description.
Same backend determination as HCPCS.

Both pages: `FreshnessChip` showing last ingestion run date from quality dashboard.

### Cluster E: Pricing surface (`src/surfaces/pricing/`)

**D-B13 — `PricingPage.tsx`** — unified pricing browser with tabs:
- **CMS-ASP tab:** `GET /api/v1/drugs/pricing/{ndc}` filtered to `cms_asp` source
- **CMS-NADAC tab:** `GET /api/v1/drugs/pricing/{ndc}/history` filtered to `cms_nadac`
- **Medicaid BINs tab:** `state_medicaid_bins` — list of BIN entries from billing
  module (219 loaded per `data/reference/medicaid/coverage_report.md`). Backend:
  `GET /api/v1/billing/*` or BFF-internal from ingestion run data. **Execution-time
  verification:** `grep -n "medicaid\|state_medicaid\|BIN" modules/billing/src/api/router.py`
  to find the correct billing endpoint.
- **BPG tab:** Read-only reference card: "BPG PatientLens — Live API reference.
  No ingestion schedule." No trigger button. No freshness chip. Shows
  documentation link to `data/reference/bpg/BPG_Translator_API_Documentation.txt`.

### Cluster F: Exclusions surface (`src/surfaces/exclusions/`)

**D-B14 — `ExclusionsPage.tsx`** — unified exclusions browser with tabs:
- **CMS Opt-Out tab:** `cms_opt_out` records — prescribers excluded from Medicare
- **OFAC SDN tab:** `ofac_sdn` — Specially Designated Nationals
- **SAM Exclusions tab:** `sam_exclusions` — SAM.gov excluded entities
- **OIG LEIE tab:** `oig_leie` — OIG List of Excluded Individuals/Entities
- **DEA Registrations tab:** `dea_registrations` — DEA registrant data

Each tab: search by name, NPI, or entity ID. `FreshnessChip` per tab.
Cross-link: if a prescriber NPI matches CMS opt-out or SAM, prescriber detail
shows `ExclusionAlertBadge` (Plan A D8).

**Backend for exclusions:** The exclusions data lives across multiple modules:
- `cms_opt_out` → prescriber-directory (prescribers excluded from Medicare)
- `ofac_sdn` → payment-processing (`OfacSdnEntry` at `modules/payment-processing/src/models/tables.py:212`)
- `sam_exclusions` → prescriber-directory or core-platform
- `oig_leie` → core-platform or prescriber-directory
- `dea_registrations` → prescriber-directory

**Execution-time verification:** For each exclusion source, run
`grep -n "ofac\|sam_excl\|oig_leie\|dea_reg" modules/*/src/api/router.py`
to find the actual route. The BFF aggregates across owning modules into the
unified exclusions view.

### DirectoriesCommandPalette extension (`src/search/DirectoriesCommandPalette.tsx`)

```typescript
// src/search/DirectoriesCommandPalette.tsx
// Extends packages/ui/src/command/CommandPalette.tsx with grouped results
// and useDirectoriesSearch integration.
import { CommandPalette, type CommandItem } from "@infinityrx/ui";
import { useDirectoriesSearch } from "./useDirectoriesSearch.js";
import type { SearchResultRecord } from "./schemas.js";

const CLUSTER_LABELS: Record<string, string> = {
  nppes: "Prescribers",
  ncpdp: "Pharmacies",
  fda_ndc: "Drugs", fda_orange_book: "Drugs", fda_purple_book: "Drugs",
  fda_drug_shortages: "Drugs", fda_rems: "Drugs", rxnorm: "Drugs",
  hcpcs: "Codes", icd10_cm: "Codes",
  cms_asp: "Pricing", cms_nadac: "Pricing", state_medicaid_bins: "Pricing",
  cms_opt_out: "Exclusions", ofac_sdn: "Exclusions", sam_exclusions: "Exclusions",
  oig_leie: "Exclusions", dea_registrations: "Exclusions",
};

const DETAIL_PATHS: Record<string, (id: string) => string> = {
  nppes: (npi) => `/directories/prescribers/${npi}`,
  ncpdp: (nabp) => `/directories/pharmacies/${nabp}`,
  fda_ndc: (ndc) => `/directories/drugs/${ndc}`,
  hcpcs: (code) => `/directories/codes/hcpcs?code=${code}`,
  icd10_cm: (code) => `/directories/codes/icd10?code=${code}`,
  cms_opt_out: (id) => `/directories/exclusions?tab=cms_opt_out&id=${id}`,
  ofac_sdn: (id) => `/directories/exclusions?tab=ofac_sdn&id=${id}`,
  sam_exclusions: (id) => `/directories/exclusions?tab=sam_exclusions&id=${id}`,
  oig_leie: (id) => `/directories/exclusions?tab=oig_leie&id=${id}`,
  dea_registrations: (id) => `/directories/exclusions?tab=dea_registrations&id=${id}`,
};

function recordToCommandItem(r: SearchResultRecord): CommandItem {
  const cluster = CLUSTER_LABELS[r.dataset] ?? r.dataset;
  const path = DETAIL_PATHS[r.dataset]?.(r.id) ?? `/directories/${r.dataset}/${r.id}`;
  return {
    id: `${r.dataset}:${r.id}`,
    label: `${r.display}${r.b9_blocked ? " [B9 pending]" : ""} — ${cluster}`,
    // href is carried in the item's id for navigation; consumer handles routing
  };
}
```

---

## Tasks

### Task B-1: Prescribers cluster

**Files to create:**
- `packages/modules/directories/src/surfaces/prescribers/PrescribersListPage.tsx`
- `packages/modules/directories/src/surfaces/prescribers/PrescriberDetailPage.tsx`
- `packages/modules/directories/src/surfaces/prescribers/PrescriberMonitoringPanel.tsx`
- `packages/modules/directories/src/surfaces/prescribers/index.ts`

**Files to modify (thin re-export shells):**
- `portal/operator/app/directories/prescribers/page.tsx` — replace body with re-export
- `portal/operator/app/directories/prescribers/[npi]/page.tsx` — replace body with re-export

**Tests:**
- `tests/unit/surfaces/prescribers.test.tsx`:
  - `PrescribersListPage` renders list with mocked `useQuery`
  - `PrescriberDetailPage` shows `ProvenanceBadge` with run date
  - `PrescriberDetailPage` shows `ExclusionAlertBadge` when exclusion sources non-empty
  - `PrescriberMonitoringPanel` renders alerts; acknowledging alerts is NOT available (button absent)

### Task B-2: Pharmacies cluster

**Files to create:**
- `packages/modules/directories/src/surfaces/pharmacies/PharmaciesListPage.tsx`
- `packages/modules/directories/src/surfaces/pharmacies/PharmacyDetailPage.tsx`
- `packages/modules/directories/src/surfaces/pharmacies/index.ts`

**Files to modify (thin re-export shells):**
- `portal/operator/app/directories/pharmacies/page.tsx`
- `portal/operator/app/directories/pharmacies/[npi]/page.tsx`

**Critical:** BFF route that calls `GET /api/v1/pharmacies/stats` MUST pass
`?x-tenant-id={tid}` (mandatory per router.py:442). Test:
- Integration test: call BFF without `tid` in JWT → 422 propagated correctly
- Cross-tenant test: call with `tid_A` JWT and `tid_B` JWT for stats;
  assert global pharmacy counts identical, tenant-scoped fields (`total_networks`,
  `pending_credentialing`) differ.

### Task B-3: Drugs cluster

**Files to create:**
- `packages/modules/directories/src/surfaces/drugs/DrugsListPage.tsx`
- `packages/modules/directories/src/surfaces/drugs/DrugDetailPage.tsx`
- `packages/modules/directories/src/surfaces/drugs/index.ts`

**Files to modify (thin re-export shells):**
- `portal/operator/app/directories/drugs/page.tsx`
- `portal/operator/app/directories/drugs/[ndc]/page.tsx`

**Tests:**
- `DrugDetailPage` renders Pricing/REMS/Shortages tabs with mocked data
- `DrugDetailPage` Interactions tab renders `B9PendingBanner` (not an error state)
- `DrugDetailPage` BPG pricing section shows "Live API — no ingestion schedule" label

### Task B-4: Codes cluster (new pages)

**Files to create:**
- `packages/modules/directories/src/surfaces/codes/HcpcsListPage.tsx`
- `packages/modules/directories/src/surfaces/codes/Icd10ListPage.tsx`
- `packages/modules/directories/src/surfaces/codes/index.ts`

**No existing portal pages to wrap.** These are new routes registered in `module.config.ts`
(`/directories/codes/hcpcs`, `/directories/codes/icd10`).

**Execution-time verification required:** Before implementing backend calls,
run `grep -n "hcpcs\|icd10\|icd_10" modules/drug-database/src/api/router.py`
to find the actual endpoints. If none exist, codes data is served via the
ingestion field-catalog endpoint or requires a new BFF-internal query against
the ingestion run data.

### Task B-5: Pricing cluster

**Files to create:**
- `packages/modules/directories/src/surfaces/pricing/PricingPage.tsx`
- `packages/modules/directories/src/surfaces/pricing/index.ts`

**Execution-time verification required:** Before implementing Medicaid BINs tab,
run `grep -n "state_medicaid\|medicaid_bin\|BIN" modules/billing/src/api/router.py`
to find the actual route. If no dedicated route exists, BFF reads from ingestion
run data for the `state_medicaid_bins` source.

### Task B-6: Exclusions cluster

**Files to create:**
- `packages/modules/directories/src/surfaces/exclusions/ExclusionsPage.tsx`
- `packages/modules/directories/src/surfaces/exclusions/index.ts`

**Execution-time verification required:** For each exclusion dataset, run
`grep -n "ofac\|sam_excl\|oig_leie\|dea_reg\|opt_out" modules/*/src/api/router.py`
to locate actual backend routes before writing BFF calls.

### Task B-7: DirectoriesCommandPalette

**Files to create:**
- `packages/modules/directories/src/search/DirectoriesCommandPalette.tsx`
- `packages/modules/directories/src/search/DirectoriesCommandPaletteDialog.tsx`
  (wrapper that handles open/close state + keyboard shortcut Cmd+K/Ctrl+K)

**Tests:**
- `tests/unit/DirectoriesCommandPalette.test.tsx`:
  - Renders closed when `open=false`
  - Renders input when open
  - Results grouped by cluster (Prescribers, Pharmacies, Drugs, Codes, Pricing, Exclusions)
  - B9-blocked result shows "[B9 pending]" pill
  - Partial results show "Some datasets unavailable" notice
  - Enter on result navigates to correct detail path

### Task B-8: Surface barrel exports

**File:** `packages/modules/directories/src/surfaces/index.ts` — exports all cluster
index modules.

**File:** `packages/modules/directories/src/index.ts` — update to export surfaces,
search (CommandPalette), components.

---

## Testing requirements

| Test file | What | Coverage |
|---|---|---|
| `tests/unit/surfaces/prescribers.test.tsx` | list/detail/monitoring render, exclusion alert | 99% |
| `tests/unit/surfaces/pharmacies.test.tsx` | list/detail; x-tenant-id propagation | 99%; 100% on cross-tenant path |
| `tests/unit/surfaces/drugs.test.tsx` | list/detail tabs; B9 banner; BPG label | 99% |
| `tests/unit/surfaces/codes.test.tsx` | HCPCS/ICD10 render | 99% |
| `tests/unit/surfaces/pricing.test.tsx` | tabs; BPG live-API label; Medicaid BINs | 99% |
| `tests/unit/surfaces/exclusions.test.tsx` | all 5 tabs; search by NPI/entity | 99% |
| `tests/unit/DirectoriesCommandPalette.test.tsx` | grouped results; B9 pill; navigation; partial | 99% |
| Integration (Plan E) | cross-tenant pharmacy stats; search fan-out with backend down | 100% on auth/tenant paths |

---

## Notes on BFF routes added by Plan B

In addition to `GET /api/directories/search` (Plan A), Plan B adds:

| BFF Route | Purpose |
|---|---|
| `GET /api/directories/prescribers/[npi]/exclusion-check` | Cross-dataset: is NPI in any exclusion list? |
| `GET /api/directories/pharmacies/stats` | Proxies pharmacy stats with mandatory x-tenant-id |

All BFF route handlers follow Plan A's auth pattern:
- Extract JWT via `verifyAccessToken` from `@infinityrx/auth`
- Reject 401 if missing or invalid
- No role check (D7)
- Include `correlation_id` in all downstream calls

---

## Verified citations (pre-write grep results)

| Symbol / Path | Verification |
|---|---|
| `portal/operator/app/directories/prescribers/page.tsx:87` | `NPI_PATTERN = /^\d{10}$/` |
| `portal/operator/app/directories/prescribers/[npi]/page.tsx` | exists; uses `apiGet` |
| `portal/operator/app/directories/pharmacies/page.tsx` | exists |
| `portal/operator/app/directories/pharmacies/[npi]/page.tsx` | exists |
| `portal/operator/app/directories/drugs/page.tsx` | exists; `apiGet` to `${API_URLS.drugDatabase}/api/v1/drugs` |
| `portal/operator/app/directories/drugs/[ndc]/page.tsx` | exists |
| `portal/operator/app/directories/members/` | exists but NOT in SP-2 scope |
| `modules/prescriber-directory/src/api/router.py:344` | `GET /monitoring/alerts` — `list_alerts` |
| `modules/prescriber-directory/src/api/router.py:359` | `PUT /monitoring/alerts/{alert_id}/acknowledge` — out of SP-2 scope |
| `modules/prescriber-directory/src/api/router.py:381` | `GET /stats` — no `x-tenant-id` alias (uses `TenantId` dependency) |
| `modules/prescriber-directory/src/api/router.py:402` | `GET /relationships/{npi}/pharmacies` |
| `modules/pharmacy-directory/src/api/router.py:440-442` | `GET /stats` — MANDATORY `x-tenant-id: Annotated[uuid.UUID, Query(alias="x-tenant-id")]` |
| `modules/drug-database/src/api/router.py:307` | `GET /rems/{ndc}` |
| `modules/drug-database/src/api/router.py:320,332` | `GET /shortages`, `GET /shortages/{ndc}` |
| `modules/payment-processing/src/models/tables.py:212` | `OfacSdnEntry` ORM model |
| `packages/ui/src/command/CommandPalette.tsx` | exports `CommandPalette`, `CommandItem` (flat items, no grouping) |
| `portal/shared/lib/constants.ts:17-22` | `pharmacyDirectory: :8009`, `prescriberDirectory: :8010`, `drugDatabase: :8011` |

---

## Out of scope for Plan B

- Ingestion console trigger buttons (Plan C)
- Data-quality dashboard sidebar (Plan D)
- Audit log viewer (Plan D)
- E2E fixtures and round-trip tests (Plan E)
- Pharmacy credentialing workflow actions (`POST /credentialing/{id}/approve`) — per spec §3
- Prescriber monitoring alert acknowledgment (`PUT /monitoring/alerts/{id}/acknowledge`) — per spec §3
