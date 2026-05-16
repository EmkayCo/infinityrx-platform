# SP-2 — Directories Portal / Reference Data Control Plane

**Status:** Spec revised (r1+r2 codex NO-GO addressed); pending r3 codex review then plan-writing.
**Date:** 2026-05-16
**Owner:** Mike
**Sub-project of:** Operator Portal & Platform Frontend milestone
**Builds on:** SP-0 (`2026-05-14-sp0-integration-foundation-design.md`)
**Parallel track:** B9 (FDB Tier B–D ingestion) — closes independently; SP-2 mocks FDB surfaces until B9 lands.
**Replaces:** —

---

## 1. Problem statement

The InfinityRx platform consumes ~15–16 static reference datasets spanning
prescribers, pharmacies, drugs, procedure/diagnosis codes, pricing, and
exclusions/sanctions. These datasets power claim adjudication, eligibility
checks, and regulatory compliance on every transaction. Today:

- **No unified browser.** Each dataset is queried only through its owning
  module's narrow API. There is no single place an operator can search
  "prescriber NPI 1234567890," "NDC 00069-0010-83," or "SAM excluded entity
  ACME Corp" and get a coherent answer.
- **Ingestion is opaque.** All 15 loaders run on cron schedules in
  `shared/data_ingestion/`. When a loader fails, the operator sees nothing
  in the portal — no freshness timestamp, no record count, no error. They
  discover data rot through a downstream adjudication failure.
- **Provenance is missing.** There is no portal surface that tells an
  operator "this claim was adjudicated against NPPES data loaded on
  2026-05-10 with 9,494,438 records." That linkage exists in the DB but is
  invisible in the UI.
- **Cross-dataset navigation is absent.** An operator drilling into a
  prescriber record cannot jump to that prescriber's related pharmacy
  relationships, the drugs they commonly prescribe, or whether they appear
  on any exclusion list — the data is there, the navigation is not.

SP-2 delivers a Reference Data Control Plane: a unified search spine over
all 19 source datasets (6 browse clusters) plus an ingestion console that makes freshness, record
counts, and errors observable and actionable. It is the second vertical
built on the SP-0 spine, analogous to SP-1 (PaySync) in structure.

---

## 2. Goals

1. **Federated Cmd+K search** — typeahead across all 19 source datasets (6 browse clusters) in a single
   command palette. An operator can find any NPI, NDC, NPI, HCPCS code,
   ICD-10 code, SAM exclusion, OFAC entity, or Medicaid BIN in one keypress.
2. **Per-dataset browse surfaces** — every dataset is viewable, filterable,
   and drillable. Detail pages surface provenance (source, load date, record
   count of the containing run) and freshness indicators.
3. **Ingestion console** — operators can see the status of every ingestion
   run (`shared.ingestion_runs`), trigger a manual refresh via the existing
   `POST /{source}/trigger` API at `shared/data_ingestion/api/routes.py:127`,
   and watch it complete with a record-count delta.
4. **Data-quality dashboard** — sidebar showing freshness chips (last-loaded
   date per dataset), ingestion alerts (non-zero `records_errored`), and
   record counts. Surfaces actionable alerts: "NPPES last loaded 14 days ago,
   3 errors in last run."
5. **Cross-dataset claim-context links** — from a prescriber detail, jump to
   related pharmacy relationships, flag on any exclusion list. From a drug
   detail, jump to pricing history, REMS programs, shortage status.
6. **Shippable E2E round trip** on synthetic data — operator uses Cmd+K to
   find a result across datasets, drills to the detail page, sees provenance
   + freshness + audit log, triggers an ingestion refresh, watches it
   complete, sees the record-count delta, and dismisses or escalates an alert
   (D5).

---

## 3. Non-goals (explicitly out of SP-2)

- **No row-level edits.** Reference data is read-only in the portal. The
  only write operation is `POST /{source}/trigger` (ingestion refresh).
  Tenant-level overrides (e.g., MAC price overrides in drug-database) are a
  separate surface not in SP-2.
- **No network management.** Pharmacy network CRUD (add/remove pharmacies,
  set network tiers, PSAO management) is a separate later layer. SP-2 shows
  network membership as a read-only attribute on pharmacy records.
- **No per-dataset deep curation in SP-2.** The pharmacy credentialing
  workflow (`POST /credentialing/{id}/approve`) and prescriber monitoring
  alert acknowledgment (`PUT /monitoring/alerts/{id}/acknowledge`) are not
  in SP-2 scope. Those are operator actions on directory entries, not
  reference-data browsing. They belong in a future Directory Management SP.
- **No B9 closure.** B9 (FDB Tier B–D ingestion — FDB MedKnowledge
  formulary, interaction, and clinical data layers) is a parallel B-wave.
  SP-2 shows FDB-dependent surfaces with a "Pending B9 — mock data shown"
  banner. SP-2 does not wait for B9 and does not implement B9.
- **No client portal or provider portal.** Future SPs per SP-0 §3.
- **No medical EDI.** Separate track.
- **No 50-state compliance reporting.** Backend gap deferred per CLAUDE.md.

---

## 4. Locked decisions

| # | Decision | Choice | Source |
|---|---|---|---|
| D1 | Vertical | Directories portal (Reference Data Control Plane) | user brainstorm 2026-05-16 |
| D2 | B9 dependency posture | SP-2 is UI-only. B9 closes as a parallel B-wave. FDB surfaces show "pending B9" banner + mock data until B9 lands. | user 2026-05-16 |
| D3 | Datasets in scope | **15 confirmed loader sources → 6 browse clusters.** Confirmed ingestion source keys (from `_SOURCE_NAME` constants in `shared/data_ingestion/sources/`): `nppes` (prescribers), `ncpdp` (pharmacy — loaded by `ncpdp_dataq.py`), `fda_ndc`, `fda_orange_book`, `fda_purple_book`, `fda_drug_shortages`, `fda_rems` (drugs), `hcpcs`, `icd10_cm` (codes), `cms_asp`, `cms_nadac` (pricing), `cms_opt_out`, `ofac_sdn`, `sam_exclusions`, `state_medicaid_bins` (exclusions). **No confirmed loaders for:** `relay-health` (reference files only in `data/reference/relay-health/`), `fdb` (B9-blocked), `bpg` (live external API — no batch loader). These 3 are present in `data/reference/` but have no `_SOURCE_NAME` in `shared/data_ingestion/sources/`. Browse surfaces: prescribers / pharmacies / drugs / codes / pricing / exclusions. Format-only dirs excluded. | user + `ls data/reference/` + `_SOURCE_NAME` grep verified |
| D4 | IA shape | Search-First — Cmd+K command palette as centerpiece; federated typeahead across all datasets; data-quality dashboard as secondary spine in sidebar (freshness chips, ingestion alerts, record counts) | user 2026-05-16 |
| D5 | Shippable bar | Cross-dataset round trip on synthetic data: Cmd+K → search → drill → provenance/freshness/audit → trigger ingestion → watch complete → record-count delta → dismiss/escalate alert. Every dataset browsable. B9-dependent surfaces mocked with banner. | user 2026-05-16 |
| D6 | Build approach | Approach A — Search spine first (federated search infra + Cmd+K + ranking in Plan 1; per-dataset surfaces wired into search from day 1 in subsequent plans). | user 2026-05-16 |
| D7 | RBAC | **No RBAC.** All authenticated users can read all reference data and trigger ingestion refreshes. Reference data is not customer-specific. Auth (JWT) is still required; no role gates. | user 2026-05-16 |
| D8 | Deployable shape | Module inside `portal/operator` (same as SP-1). Standalone deployable deferred. | user 2026-05-16 |

These decisions are inputs to the plan. If any are revisited, this spec must
be revised first.

---

## 5. Architecture

### 5.1 Layering on SP-0

SP-2 is a **module package** consumed by `portal/operator` via the SP-0
composition mechanism (SD-4 generated artifact + manifest schema). Zero new
framework, zero new shared packages.

```
packages/modules/directories/          ← NEW: the SP-2 deliverable
  src/
    search/                             ← Federated search infra + Cmd+K host
    surfaces/                           ← One folder per dataset cluster
      prescribers/                        ← NPPES — wraps portal/operator/app/directories/prescribers/
      pharmacies/                         ← NCPDP + NCPDP-DataQ + Relay Health — wraps portal/operator/app/directories/pharmacies/
      drugs/                              ← FDB + FDA-NDC + FDA-OB + FDA-PB + FDA-shortages + FDA-REMS — wraps portal/operator/app/directories/drugs/
      codes/                              ← HCPCS + ICD-10-CM
      pricing/                            ← CMS-ASP + CMS-NADAC + BPG
      exclusions/                         ← CMS-opt-out + OFAC-SDN + SAM_exclusions + Medicaid BINs
    ingestion/                          ← Ingestion console (trigger, poll, history)
    quality/                            ← Data-quality dashboard (freshness chips, alert list)
    bff/                                ← Next.js route handlers per surface (module-owned, mounted by shell)
    components/                         ← Module-local primitives (FreshnessChip, IngestionAlert, ProvenanceBadge, etc.)
    module.config.ts                    ← Composition entry: routes + navEntry + commandPaletteScopes
  fixtures/                             ← Synthetic non-PHI seed data (~10 records per dataset)
  tests/                                ← Unit + integration; E2E lives at portal level
```

Composed via `infrastructure/manifests/operator-dev.yml` (the existing dev
manifest, verified at `infrastructure/manifests/operator-dev.yml`) adding
`directories` to the module list. The SP-0 composition scripts
(`scripts/generate-composition.ts`, `scripts/audit-composition.ts`) are built
as part of SP-0 execution — they do not exist yet in the repo; SP-2 depends on
SP-0 having shipped them before plan execution begins.

### 5.2 Dataset inventory and per-dataset attribute model

Each dataset has a canonical attribute model used by the federated search
index, the browse surface, and the freshness dashboard.

| # | Source key (`_SOURCE_NAME`) | `data/reference/` dir | Loader file | Owning module | Record identifier | Has batch loader? | B9-blocked? |
|---|---|---|---|---|---|---|---|
| 1 | `nppes` | `nppes/` | `sources/nppes.py` | prescriber-directory | `npi` (10-digit) | Yes | No |
| 2 | `ncpdp` | `ncpdp/` + `ncpdp-dataq/` | `sources/ncpdp_dataq.py` (`_SOURCE_NAME="ncpdp"`) | pharmacy-directory | `nabp` | Yes | No |
| 3 | _(no loader)_ | `relay-health/` + `RelayHealth/` | No `_SOURCE_NAME` found — reference files only | pharmacy-directory | `nabp` | **No — open question §10.7** | No |
| 4 | _(no loader — B9)_ | `fdb/` | B9-blocked (FDB Tier B–D) | drug-database | `ndc` | **No — B9 parallel track** | **Yes — B9** |
| 5 | `fda_ndc` | `fda-ndc/` | `sources/fda_ndc.py` | drug-database | `ndc` (11-digit) | Yes | No |
| 6 | `fda_orange_book` | `fda-orange-book/` | `sources/fda_orange_book.py` | drug-database | `ndc` | Yes | No |
| 7 | `fda_purple_book` | `fda-purple-book/` | `sources/fda_purple_book.py` | drug-database | `ndc` | Yes | No |
| 8 | `fda_drug_shortages` | `fda-drug-shortages/` | `sources/fda_drug_shortages.py` | drug-database | `ndc` | Yes | No |
| 9 | `fda_rems` | `fda-rems/` | `sources/fda_rems.py` | drug-database | `ndc` | Yes | No |
| 10 | `hcpcs` | `hcpcs/` | `sources/hcpcs.py` | drug-database | `hcpcs_code` | Yes | No |
| 11 | `icd10_cm` | `icd10-cm/` | `sources/icd10_cm.py` | drug-database | `icd10_code` | Yes | No |
| 12 | `cms_asp` | `cms-asp/` | `sources/cms_asp.py` | drug-database | `ndc` | Yes | No |
| 13 | `cms_nadac` | `cms-nadac/` | `sources/cms_nadac.py` | drug-database | `ndc` | Yes | No |
| 14 | _(no loader)_ | `bpg/` | No `_SOURCE_NAME` — live external API (`patientlens-api`); no batch ingestion | drug-database | `ndc` | **No — live API §10.6** | No |
| 15 | `cms_opt_out` | `cms-opt-out/` | `sources/cms_opt_out.py` | prescriber-directory | `npi` | Yes | No |
| 16 | `ofac_sdn` | `ofac-sdn/` | `sources/ofac_sdn.py` | payment-processing | entity name | Yes | No |
| 17 | `sam_exclusions` | `sam_exclusions/` | `sources/sam_exclusions.py` | prescriber-directory | SAM GUID | Yes | No |
| 18 | `state_medicaid_bins` | `medicaid/` | `sources/state_medicaid_bins.py` | billing | BIN | Yes | No |

> **Source key usage:** The `_SOURCE_NAME` value is what `IngestionSchedule.source` stores
> and what `POST /api/v1/data-ingestion/{source}/trigger` validates against. The ingestion
> console and trigger BFF routes MUST use these underscore-form keys (e.g., `fda_ndc`,
> `cms_opt_out`), NOT hyphenated directory names. Sources with "no loader" (relay-health,
> fdb, bpg) have no `IngestionSchedule` row and cannot be triggered; the ingestion console
> shows them as "No ingestion schedule" per §6.4.

> Note: D3 specifies **15 confirmed batch-loader sources → 6 browse clusters**.
> 3 additional `data/reference/` directories (`relay-health/`, `fdb/`, `bpg/`)
> have no confirmed `_SOURCE_NAME` in `shared/data_ingestion/sources/` —
> relay-health and bpg are open questions (§10.6, §10.7); fdb is B9-blocked.
> The 18-row table above is the authoritative inventory; the 6 browse clusters
> are the authoritative UI grouping. Sources 3, 4, 14 ("no loader") display
> in the portal browse surfaces but have no ingestion-console trigger row.

**Per-dataset attribute model (minimum fields for search index):**

```ts
interface DatasetRecord {
  dataset: DatasetKey;         // e.g. 'nppes', 'fda-ndc', 'ofac-sdn'
  id: string;                  // primary identifier (npi, ndc, hcpcs_code, etc.)
  display: string;             // human-readable label for search results
  secondary: string;           // secondary label (specialty, brand name, code desc, etc.)
  source_date: string | null;  // ISO date of the ingestion run that produced this record
  run_id: string | null;       // shared.ingestion_runs.id (provenance link)
  b9_blocked?: boolean;        // true if record is from FDB Tier B–D (mock shown)
}
```

### 5.3 Search spine — federation, ranking, typeahead

**Architecture decision:** The federated search is BFF-side fan-out, not a
separate search service. For SP-2, the BFF route `GET /api/directories/search`
fans out to up to N backend search endpoints in parallel, merges, and ranks.
A dedicated search index (e.g., Elasticsearch) is deferred — it would be
needed if cross-dataset fuzzy matching proves too slow at plan-time
performance testing. Flag in §10.

```
User types in Cmd+K (⌘K / Ctrl+K)
        │
        ▼
<CommandPalette> component (cmdk-based, in packages/ui per SP-0 §6.3)
  debounce 80ms → emit query
        │
        ▼
useDirectoriesSearch(query, { datasets: 'all' })  ← TanStack Query hook
        │
        ▼
GET /api/directories/search?q=...&datasets=all&limit=20
        │  (BFF route handler — packages/modules/directories/src/bff/)
        ▼
BFF fan-out (parallel, 300ms wall-time budget):
  ├── prescriberClient.search({ q, limit: 5 })         → GET /api/v1/prescribers/search (prescriber-directory:8010)
  ├── pharmacyClient.search({ q, limit: 5 })            → GET /api/v1/pharmacies/search (pharmacy-directory:8011)
  ├── drugClient.search({ q, limit: 5 })                → GET /api/v1/drugs/search (drug-database:8012)
  ├── codesClient.search({ q, limit: 5 })               → BFF-internal (HCPCS + ICD-10 in drug-database)
  ├── pricingClient.search({ q, limit: 3 })             → BFF-internal (CMS-ASP + NADAC)
  └── exclusionsClient.search({ q, limit: 3 })          → BFF-internal (OFAC + SAM + opt-out)
        │
        ▼
Merge → rank (exact-id matches first, then display-name prefix, then full-text)
        │
        ▼
Return ranked []DatasetRecord — max 20 results across datasets
        │
        ▼
CommandPalette renders grouped by dataset cluster, max 3 per group visible
  Each result: click → navigate to detail page
```

**Typeahead performance target:** <100ms perceived latency (per SP-0 D2).
BFF fans out with a 300ms server-side budget; results that miss the deadline
are omitted from the initial render and loaded in a follow-up. Partial results
are always better than a spinner.

**ID shortcut:** 10-digit NPI, 11-digit NDC, 5-char HCPCS code, and 3+
dot-digit ICD-10 code patterns bypass fan-out and route directly to the
corresponding backend lookup endpoint (faster exact match). This mirrors the
NPI shortcut already in `portal/operator/app/directories/prescribers/page.tsx:87`.

**Ranking layer:**
1. Exact identifier match (NPI, NDC, HCPCS, ICD-10 code)
2. Display-name prefix match
3. Display-name substring match
4. Secondary-field match

Ranking is BFF-side string comparison on the merged result set (no ML model
in SP-2). Flag in §10 if more sophisticated ranking is needed.

### 5.4 RBAC — explicitly none

Per D7: **no role gates on any SP-2 surface.** Every authenticated user (any
valid JWT from `packages/auth`, per SD-1) can:
- Read any dataset record or detail page
- View the ingestion console and run history
- Trigger a manual ingestion refresh
- Dismiss a data-quality alert

Rationale: reference data is not customer-specific or financially sensitive.
It is the same NPPES/FDA/CMS data that is publicly available. The risk of an
operator triggering a spurious NPPES refresh is operational (extra load), not
a security or PHI issue.

**Auth boundary:** The shared ingestion router (`shared/data_ingestion/api/routes.py`)
has **no auth dependency** — it carries no `Depends(get_current_user)`. Auth is
enforced exclusively at the BFF layer (`/api/directories/ingest/{source}/trigger`),
which validates the JWT via `packages/auth` before proxying to the backend. The
backend trigger endpoint prevents duplicate in-flight runs (409 if status=running,
`routes.py:158`) but relies on the BFF for auth gating. Plan-writer must ensure
the ingestion router is NOT exposed directly on a public-facing port without BFF
mediation.

The BFF route handler still validates the JWT (per SP-0 §6.5 auth contract)
and rejects unauthenticated requests with 401. No role check beyond
authentication.

### 5.5 Backend posture

**Wired now (no SP-2 backend work needed):**

| Endpoint | Path | Backend |
|---|---|---|
| Prescriber search | `GET /api/v1/prescribers/search` | prescriber-directory `router.py:87` |
| Prescriber lookup by NPI | `GET /api/v1/prescribers/lookup/{npi}` | prescriber-directory `router.py:58` |
| Prescriber lookup by DEA | `GET /api/v1/prescribers/lookup/dea/{dea}` | prescriber-directory `router.py:71` |
| Prescriber stats | `GET /api/v1/prescribers/stats` | prescriber-directory `router.py:381` |
| Prescriber refresh trigger | `POST /api/v1/prescribers/refresh` | prescriber-directory `router.py:470` |
| Pharmacy search | `GET /api/v1/pharmacies/search` | pharmacy-directory `router.py:153` |
| Pharmacy lookup by NPI | `GET /api/v1/pharmacies/lookup/{npi}` | pharmacy-directory `router.py:120` |
| Pharmacy lookup by NABP | `GET /api/v1/pharmacies/lookup/nabp/{nabp}` | pharmacy-directory `router.py:139` |
| Pharmacy stats | `GET /api/v1/pharmacies/stats` | pharmacy-directory `router.py:440` |
| Drug search | `GET /api/v1/drugs/search` | drug-database `router.py:84` |
| Drug lookup by NDC | `GET /api/v1/drugs/lookup/{ndc}` | drug-database `router.py:71` |
| Drug pricing | `GET /api/v1/drugs/pricing/{ndc}` | drug-database `router.py:122` |
| Drug pricing history | `GET /api/v1/drugs/pricing/{ndc}/history` | drug-database `router.py:155` |
| Drug REMS | `GET /api/v1/drugs/rems/{ndc}` | drug-database `router.py:307` |
| Drug shortages | `GET /api/v1/drugs/shortages` + `/{ndc}` | drug-database `router.py:320,332` |
| Drug refresh status | `GET /api/v1/drugs/refresh/status` | drug-database `router.py:345` |
| Ingestion trigger (generic) | `POST /api/v1/data-ingestion/{source}/trigger` | shared ingestion `routes.py:127` — `async def trigger_run` |
| Ingestion upload + trigger | `POST /api/v1/data-ingestion/upload/{source}` | shared ingestion `routes.py:202` — `async def upload_and_ingest` |
| All-sources status | `GET /api/v1/data-ingestion/status` | shared ingestion `routes.py:260` — `async def get_all_status` — returns list[SourceStatus] (schedule + last_run per source) |
| Source run history | `GET /api/v1/data-ingestion/{source}/history` | shared ingestion `routes.py:295` — `async def get_source_history` |
| Single run detail | `GET /api/v1/data-ingestion/runs/{run_id}` | shared ingestion `routes.py:333` — `async def get_run_detail` |
| Cancel run | `POST /api/v1/data-ingestion/{source}/cancel` | shared ingestion `routes.py:355` — `async def cancel_run` |
| Field catalog | `GET /api/v1/data-ingestion/field-catalog` | shared ingestion `routes.py:406` — `async def get_field_catalog` |

> Note: the router is defined without a prefix in `routes.py`; it is mounted by each
> module's `create_app()` with `prefix="/api/v1/data-ingestion"` per the docstring at
> `routes.py:3–6`. Plan-writer must verify which module(s) currently mount this router
> (see §10.3).

**Needs wiring in SP-2 (new BFF-level routes that aggregate existing backends):**

1. `GET /api/directories/search` — BFF fan-out aggregator (no new backend needed; BFF calls existing endpoints listed above).
2. `GET /api/directories/quality` — freshness dashboard aggregation: BFF reads `GET /api/v1/data-ingestion/status` plus each module's `/stats` endpoint, and returns the merged quality summary.
3. `GET /api/directories/audit` — audit log viewer: BFF reads `core-platform` audit log for ingestion-related events.

**Ingestion API mount — plan-writer action required (§10.3):** The shared ingestion
router (`shared/data_ingestion/api/routes.py`) is not confirmed mounted in any production
`create_app()` — the docstring shows the intended mount pattern but a repo search found
no `include_router(ingestion_router)` in any module's `main.py`. If no module currently
mounts it, SP-2 BFF calls to `/api/v1/data-ingestion/*` will fail. Plan-writer must either
confirm an existing mount or add mounting SP-2's backend work scope (a one-liner
`app.include_router(ingestion_router, prefix="/api/v1/data-ingestion")` in whichever
module is the appropriate host — likely `prescriber-directory` or a shared ingestion
service per §10.3).

**B9-blocked surfaces (mock until B9 lands):**

| Surface | Depends on | Mock behavior |
|---|---|---|
| FDB drug detail — interaction data | FDB Tier B | Banner: "Interaction data pending FDB B9 ingestion" |
| FDB drug detail — formulary placement | FDB Tier B | Banner: "Formulary data pending FDB B9 ingestion" |
| FDB drug detail — clinical data | FDB Tier B–D | Banner: "Clinical data pending FDB B9 ingestion" |

All other drug surfaces (FDA-NDC, FDA-OB, FDA-PB, REMS, shortages, pricing)
are not B9-blocked and render against real data.

### 5.6 Consumed from SP-0 (no rebuild)

- `packages/contract` — typed clients for prescriber-directory, pharmacy-directory, drug-database, and the shared ingestion API
- `packages/auth` — JWT validation per SD-1 (no role check, but auth required)
- `packages/ui` — cmdk command palette host (existing), Radix/shadcn components, TanStack Table + Virtual, recharts, react-hook-form + zod
- `packages/qa-harness` — fixture seeding buttons, mock/real toggle, services-health dashboard
- `packages/shell` — routing, layout, module mounting, top-nav command palette registration

---

## 6. Components

### 6.1 Search infrastructure (`src/search/`)

- `FederatedSearchClient` — BFF-side class: fans out to N backend clients in
  parallel, enforces 300ms wall-time budget, merges and ranks results.
  Lives in the BFF layer, not in the frontend.
- `useDirectoriesSearch(query, opts)` — TanStack Query hook; debounced 80ms;
  returns `{ results, isPartial, isLoading }`.
- `SearchResultRecord` — zod schema for a single federated result (validated
  at BFF boundary and client boundary).
- `rankResults(results)` — pure function: exact-id → prefix → substring →
  secondary sort. Unit-testable in isolation.

### 6.2 Command palette (`src/search/CommandPalette.tsx`)

Built on the existing `cmdk` integration in `packages/ui` (per SP-0 §6.3).

- Triggered by `⌘K` / `Ctrl+K` globally (registered in `module.config.ts`
  `shellSurfaces.commandPaletteScopes`).
- Renders a `<CommandDialog>` with debounced input → `useDirectoriesSearch`.
- Results grouped by cluster: Prescribers / Pharmacies / Drugs / Codes /
  Pricing / Exclusions. Max 3 visible per group before "See all N in
  [dataset]" link.
- Keyboard-navigable; click or Enter navigates to the detail page.
- B9-blocked results render with a "B9 pending" pill — still navigable (mock
  detail page shown).

### 6.3 Per-dataset surfaces (`src/surfaces/`)

Each surface cluster wraps and extends the existing portal pages in
`portal/operator/app/directories/`. The existing pages call backends directly
via `apiGet`; SP-2 migrates those calls through the SP-0 contract-layer BFF
pattern.

**`surfaces/prescribers/`**
- `PrescribersListPage` — wraps existing `portal/operator/app/directories/prescribers/page.tsx`; migrates direct `apiGet` call to contract-layer hook.
- `PrescriberDetailPage` — wraps existing `[npi]/page.tsx`; adds `ProvenanceBadge`, `FreshnessChip`, cross-links to CMS opt-out + SAM exclusion status.
- `PrescriberMonitoringPanel` — read-only view of `GET /api/v1/prescribers/monitoring/alerts` (alert acknowledgment deferred to future Directory Management SP per §3).

**`surfaces/pharmacies/`**
- `PharmaciesListPage` — wraps existing `portal/operator/app/directories/pharmacies/page.tsx`; migrates direct call to contract layer.
- `PharmacyDetailPage` — wraps `[npi]/page.tsx`; adds `ProvenanceBadge`, `FreshnessChip`, cross-links to prescriber relationships via `GET /api/v1/prescribers/relationships/{npi}/pharmacies`.

**`surfaces/drugs/`**
- `DrugsListPage` — wraps existing `portal/operator/app/directories/drugs/page.tsx`; migrates direct call.
- `DrugDetailPage` — wraps `[ndc]/page.tsx`; adds `ProvenanceBadge`, `FreshnessChip`, tabbed sub-sections: Pricing (CMS-ASP, CMS-NADAC, BPG), REMS, Shortages, Interactions (B9-mocked), Formulary (B9-mocked).
- `B9PendingBanner` — reusable: "This data requires FDB B9 ingestion which is in progress on a parallel track. Showing mock data."

**`surfaces/codes/`**
- `HcpcsListPage` — HCPCS codes browser; search by code or description.
- `Icd10ListPage` — ICD-10-CM codes browser; search by code or description.
- Both: `FreshnessChip` showing last ingestion run date.

**`surfaces/pricing/`**
- `CmsAspPage` — CMS ASP pricing browser; filterable by NDC + effective date.
- `CmsNadacPage` — NADAC pricing browser.
- `BpgPage` — BPG PatientLens pricing reference (external API — read-only display, no ingestion trigger for BPG as it is a live API not a batch source).

**`surfaces/exclusions/`**
- `ExclusionsPage` — unified exclusions browser: tabs for CMS Opt-Out / OFAC SDN / SAM Exclusions / Medicaid BINs. Search by name, NPI, entity ID.
- Cross-link: if a prescriber NPI appears in CMS opt-out or SAM exclusions, the prescriber detail page shows an `ExclusionAlertBadge` linking to the exclusions record.

### 6.4 Ingestion console (`src/ingestion/`)

- `IngestionConsolePage` — table of all registered sources (from
  `GET /ingest/schedules`) with last-run status, last-run time, record
  counts, error count, next scheduled run time.
- `RunHistoryDrawer` — drawer showing run history for a single source:
  `records_inserted`, `records_updated`, `records_errored`, wall time,
  status (`completed` / `completed_core` / `failed` / `skipped_unchanged`).
- `TriggerRefreshButton` — calls `POST /ingest/{source}/trigger` (via BFF);
  shows in-progress spinner; polls `GET /ingest/runs/{run_id}` every 5s
  until `status !== 'running'`; on completion shows record-count delta.
- `RunProgressBar` — live progress visualization while a run is in flight:
  `records_processed` / `records_in_source` (if known) from polling.

### 6.5 Data-quality dashboard (`src/quality/`)

The sidebar spine per D4.

- `QualityDashboardPanel` — sidebar component showing one row per dataset:
  `FreshnessChip` (last loaded date, color-coded: green <7d, yellow 7–14d,
  red >14d), record count from last run, error-count badge (non-zero =
  orange alert).
- `FreshnessChip` — reusable chip: `"NPPES — 2026-05-10 (6 days ago)"`.
- `IngestionAlertList` — list of actionable alerts: runs with
  `records_errored > 0` or `status = 'failed'` in the last 7 days. Each
  alert has "View details" → RunHistoryDrawer and "Re-trigger" → trigger
  flow.
- `DismissAlertAction` — marks an alert as acknowledged in BFF state (no
  backend persistence needed in SP-2; dismissed state is session-local or
  Redis-keyed per tenant+source).

### 6.6 Audit log viewer (`src/audit/`)

- `AuditLogPage` — read-only view of ingestion-related audit events from the
  core-platform audit log. Columns: timestamp, source, action (run started /
  completed / failed / manually triggered), actor (system or user sub), run_id.
- Filtered to `action` values in: `ingestion_run_started`,
  `ingestion_run_completed`, `ingestion_run_failed`,
  `ingestion_run_triggered_manually`.
- Cross-links to `RunHistoryDrawer` via `run_id`.

### 6.7 BFF (`src/bff/`)

Module-owned Next.js route handlers. Mounted by the shell into `app/api/directories/`.

| Route | Method | Description |
|---|---|---|
| `/api/directories/search` | GET | Fan-out search: calls all backend search endpoints in parallel, merges, ranks. |
| `/api/directories/quality` | GET | Freshness summary: reads `GET /api/v1/data-ingestion/status` (all-sources status) + each module's `/stats` endpoint; returns merged quality summary. See §9.6 for cross-tenant handling of stats endpoints. |
| `/api/directories/audit` | GET | Ingestion audit events: reads core-platform audit log filtered to ingestion actions. |
| `/api/directories/ingest/{source}/trigger` | POST | Proxy to shared ingestion `POST /api/v1/data-ingestion/{source}/trigger` (`routes.py:127`); authenticates at BFF — the backend router has no auth dependency (`routes.py` has no `Depends(get_current_user)`); BFF is the auth boundary. Logs actor from JWT `sub`. |
| `/api/directories/ingest/runs/{run_id}` | GET | Proxy to `GET /api/v1/data-ingestion/runs/{run_id}` (`routes.py:333`); used for polling run completion. |
| `/api/directories/ingest/{source}/history` | GET | Proxy to `GET /api/v1/data-ingestion/{source}/history` (`routes.py:295`); used by RunHistoryDrawer. |

All BFF route handlers:
- Extract and validate JWT via `packages/auth` (rejects 401 if missing/invalid).
- No role check (D7).
- Include `correlation_id` in all downstream calls and log it at every layer.
- Return SP-0 error envelope `{error:{code, message, field?, correlation_id}}` on failure.

### 6.8 `module.config.ts`

```ts
export default {
  id: 'directories',
  routes: [
    '/directories',
    '/directories/prescribers',
    '/directories/prescribers/[npi]',
    '/directories/pharmacies',
    '/directories/pharmacies/[npi]',
    '/directories/drugs',
    '/directories/drugs/[ndc]',
    '/directories/codes/hcpcs',
    '/directories/codes/icd10',
    '/directories/pricing',
    '/directories/exclusions',
    '/directories/ingestion',
    '/directories/audit',
  ],
  navEntry: {
    label: 'Directories',
    icon: 'Database',
    order: 3,
    children: [/* Prescribers, Pharmacies, Drugs, Codes, Pricing, Exclusions, Ingestion, Audit */],
  },
  shellSurfaces: {
    commandPaletteScopes: ['directories'],
    cacheTagPrefixes: ['directories'],
    routePrefixes: ['/directories'],
    cacheKeyNamespaces: ['dir'],
    redisKeyPrefixes: ['dir:'],
  },
  requires: {
    backends: ['prescriber-directory', 'pharmacy-directory', 'drug-database', 'core-platform'],
    sharedServices: ['redis', 'postgres'],
    schemas: ['prescriber_dir', 'pharmacy_dir', 'drug_db', 'shared', 'audit'],
    env: ['PRESCRIBER_DIRECTORY_URL', 'PHARMACY_DIRECTORY_URL', 'DRUG_DATABASE_URL', 'CORE_PLATFORM_URL'],
    health: ['prescriber-directory', 'pharmacy-directory', 'drug-database'],
    seedData: ['directories/fixtures'],
    queues: [],
    jobs: [],
    buckets: [],
    integrations: ['shared-ingestion-api'],
    secrets: [],
  },
  surfaceKinds: ['server', 'client'],
} satisfies ModuleConfig;
```

---

## 7. Data flow

### 7.1 Canonical search query path (Cmd+K)

```
1. User presses ⌘K → CommandPalette opens
2. User types "lipitor" (drug name) or "1234567890" (NPI) or "J0135" (HCPCS)
3. Debounce 80ms → useDirectoriesSearch fires
4. GET /api/directories/search?q=lipitor&datasets=all&limit=20
5. BFF authenticates JWT (packages/auth) → no role check
6. BFF checks cache (Next cache / Redis, TTL 30s, key: dir:search:{hash(q)})
7. Cache miss → FederatedSearchClient fans out (parallel, 300ms budget):
     prescriberClient.search({q:'lipitor', limit:5})    → GET /api/v1/prescribers/search?name=lipitor (0 results — name doesn't match)
     pharmacyClient.search({q:'lipitor', limit:5})      → GET /api/v1/pharmacies/search?q=lipitor (0 results)
     drugClient.search({q:'lipitor', limit:5})           → GET /api/v1/drugs/search?q=lipitor (hits: atorvastatin/Lipitor NDCs)
     codesClient.search({q:'lipitor', limit:5})          → BFF-internal codes search (0 results)
     pricingClient.search({q:'lipitor', limit:3})        → BFF-internal pricing search (0 results)
     exclusionsClient.search({q:'lipitor', limit:3})     → BFF-internal exclusions search (0 results)
8. Merge: 5 drug results
9. Rank: display-name prefix match "Atorvastatin (Lipitor)" scores highest
10. Return []DatasetRecord (zod-validated)
11. BFF writes to cache (tag: dir:search)
12. TanStack Query caches client-side → CommandPalette renders grouped results
13. User clicks a drug result → navigate to /directories/drugs/00071-0155-23
```

**ID shortcut path (NPI entered):**
```
Step 2: User types "1234567890" (10 digits)
Step 3: BFF detects NPI_PATTERN → routes to GET /api/v1/prescribers/lookup/1234567890 (fast PK lookup)
Step 5: Returns single DatasetRecord immediately; no fan-out needed
```

### 7.2 Ingestion trigger path

```
1. Operator clicks "Re-trigger" on a data-quality alert for source 'nppes'
2. POST /api/directories/ingest/nppes/trigger (BFF route)
3. BFF validates JWT via packages/auth → extracts {sub, tid} → logs actor (auth boundary; backend has none)
4. BFF calls shared ingestion API: POST /api/v1/data-ingestion/nppes/trigger (body: {run_type:'full', triggered_by: sub})
5. Shared ingestion API checks for in-flight run (routes.py:158) → 409 if already running
6. On success: shared ingestion API creates IngestionRun row (status='running'), returns {run_id}
7. BFF returns {run_id, status:'running'} to client
8. Client begins polling: GET /api/directories/ingest/runs/{run_id} every 5s
   → BFF proxies to GET /api/v1/data-ingestion/runs/{run_id} (routes.py:333)
   → returns RunDetail {status, records_processed, records_in_source, records_inserted, records_errored, error_samples}
9. RunProgressBar updates live
10. When status = 'completed': show record-count delta (records_inserted + records_updated)
    When status = 'failed': show error toast with error_message + correlation_id
11. QualityDashboardPanel revalidates: TanStack Query invalidates tag 'dir:quality'
```

### 7.3 Freshness refresh path

```
1. On QualityDashboardPanel mount (or focus): GET /api/directories/quality
2. BFF fans out:
   - GET /api/v1/data-ingestion/status (routes.py:260 — returns list[SourceStatus] with last_run per source; one call for all sources, no per-source looping needed)
   - GET /api/v1/prescribers/stats (router.py:381)
   - GET /api/v1/pharmacies/stats?x-tenant-id={tid} (router.py:440 — MANDATORY x-tenant-id query param; BFF extracts tid from JWT and passes it; tenant-scoped fields stripped from quality output; see §9.6)
   - GET /api/v1/drugs/refresh/status (router.py:345)
3. BFF merges into []DatasetQuality {source, last_run_at, last_run_status, records_in_db, records_errored}
4. BFF caches result (TTL 60s, tag: dir:quality)
5. QualityDashboardPanel renders FreshnessChips + IngestionAlertList
6. On manual trigger completion (§7.2 step 11): invalidate dir:quality tag → QualityDashboardPanel refetches
```

---

## 8. Error handling

Inherits SP-0 §8 error envelope (`{error:{code, message, field?, correlation_id}}`).
SP-2-specific rules:

| Failure mode | Behavior |
|---|---|
| **Search timeout (300ms budget exceeded)** | BFF returns partial results with `{isPartial: true, timedOutDatasets: ['exclusions']}`. CommandPalette shows "Some datasets unavailable — results may be incomplete." No full spinner. |
| **Single dataset backend unavailable during fan-out** | That dataset's results are omitted; `timedOutDatasets` lists it. Other datasets' results still render. SP-0 §8.3 `stale-ok`: serve cached results for the unavailable dataset if within TTL. |
| **Ingestion trigger 409 (already in flight)** | Toast: "A refresh is already running for [source]. View its progress." Link to RunProgressBar for the in-flight run_id. |
| **Ingestion trigger 404 (unknown source)** | Toast with `correlation_id`. Operator cannot trigger a source that has no schedule. |
| **Ingestion run fails (`status = 'failed'`)** | `IngestionAlertList` shows the alert with `error_message` + "Re-trigger" CTA. Audit log records the failure. |
| **Backend down (quality dashboard)** | SP-0 §8.3 `stale-ok`: serve last cached quality summary with "Data quality dashboard may be outdated (last updated N minutes ago)" banner. |
| **Backend down (browse/search — read path)** | SP-0 §8.3 `stale-ok`: cached data + soft "data may be outdated" banner. Reference data is staleness-tolerant. |
| **B9-blocked surface** | Always shows mock data + `B9PendingBanner`. Never an error state — the banner IS the expected state until B9 lands. |
| **Auth failure** | 401 → SP-0 redirect to login (per SP-0 §8.2). |
| **Internal / unexpected** | Module error boundary panel; `correlation_id` surfaced to user; full context logged server-side. Rest of portal stays alive. |
| **Correlation ID** | Every BFF route mints or forwards `correlation_id`; included in all downstream calls, structured logs, and error toasts. |

**PHI posture:** Reference data (NPPES, NCPDP, FDA, CMS, OFAC, SAM) is
public data. Individual prescriber names, addresses, and NPIs from NPPES are
**not PHI** — they are public provider directory data. Member/patient data
is not surfaced anywhere in SP-2. No PHI controls (`PHIMixin`,
`EncryptedString`, PHI access audit, `Cache-Control: no-store`, masking) are
required for reference data records.

Exception: if a future surface in this module ever displays a member's PHI
(e.g., from a Medicaid eligibility lookup), that surface MUST add PHIMixin,
EncryptedString columns, PHI read audit entries, `Cache-Control: no-store`,
and PHI masking per `.claude/rules/phi-compliance.md`. No such surface is in
SP-2 scope, but this rule is stated explicitly to prevent accidental
violation during plan-writing.

---

## 9. Testing

Per SP-0 §9 + project Auto-Gate + `.claude/rules/testing.md`.

### 9.1 Test layers

| Layer | What | Where | When |
|---|---|---|---|
| **Unit (frontend)** | rankResults(), FederatedSearchClient fan-out/merge logic, FreshnessChip color thresholds, B9PendingBanner rendering, CommandPalette keyboard navigation, ID-pattern detection (NPI/NDC/HCPCS/ICD-10) | `packages/modules/directories/tests/unit/` | Every PR (fast) |
| **Unit (frontend — contract schemas)** | zod schemas for SearchResultRecord, DatasetQuality, RunProgressPayload | Co-located with schemas | Every PR (fast) |
| **Integration (BFF ↔ backends)** | Each BFF route via docker-compose backends; fan-out merging with one backend down (partial result); ingestion trigger happy-path + 409 + 404; quality dashboard freshness aggregation; auth rejection (no JWT → 401) | `packages/modules/directories/tests/integration/` | Every PR (medium) |
| **E2E (the round trip per D5)** | Playwright: ⌘K → type query → result appears → click → detail page → ProvenanceBadge shows run date → QualityDashboard shows freshness → trigger refresh → RunProgressBar runs → completes with delta → alert dismissed | `portal/operator/tests/e2e/directories/` | PR + pre-merge (slowest) |

### 9.2 Coverage gates

Per `.claude/rules/testing.md` (corrected from SP-1 plans which erroneously
used 95%):
- 100% on security paths (auth validation in BFF route handlers, JWT
  extraction, 401 guard).
- 100% on any financial logic — SP-2 has none (pricing data is displayed,
  never calculated here). If a pricing calculation is added, 100% applies.
- 100% on PHI paths — SP-2 has none (public reference data). If PHI is
  introduced, 100% applies immediately.
- **99% branch coverage** on all other active SP-2 code (search federation,
  ranking, ingestion console, quality dashboard, all BFF routes, all
  components).
- Excluded from coverage: B9-mocked stub implementations (clearly marked;
  covered by a smoke test that asserts the mock returns the expected shape
  and the B9PendingBanner renders).

### 9.3 Synthetic fixtures (`fixtures/directories/`)

~10 records per dataset, all non-PHI (public reference data):

| File | Contents |
|---|---|
| `prescribers.json` | 10 NPPES-shaped prescribers (Luhn-valid invented NPIs per Luhn check prefix 80840, per `.claude/rules/security.md`) |
| `pharmacies.json` | 10 NCPDP-shaped pharmacies (invented NABP numbers) |
| `drugs-fda-ndc.json` | 10 FDA NDC drug records (real public NDCs from the FDA NDC database — public data, non-PHI) |
| `drugs-fdb-mock.json` | 10 FDB-shaped mock drug records (B9 pending; clearly labelled `_mock: true`) |
| `codes-hcpcs.json` | 10 HCPCS codes (real public codes from the CMS data) |
| `codes-icd10.json` | 10 ICD-10-CM codes (real public codes) |
| `pricing-cms-asp.json` | 5 CMS-ASP pricing records |
| `pricing-cms-nadac.json` | 5 CMS-NADAC pricing records |
| `exclusions-ofac.json` | 5 OFAC SDN records (real public data from `data/reference/ofac-sdn/sdn.csv`) |
| `exclusions-sam.json` | 5 SAM exclusion records (real public data from `data/reference/sam_exclusions/`) |
| `ingestion-runs.json` | 3 ingestion run records: one completed, one failed (records_errored=3), one running |
| `ingestion-schedules.json` | Schedules for sources with confirmed loader source_name keys (see §5.2 source key table); 15 confirmed loaders in `shared/data_ingestion/sources/` |

### 9.4 Search relevance regression tests

A set of fixed query → expected-top-result assertions that run in CI to
prevent ranking regressions:

| Query | Expected top result | Dataset |
|---|---|---|
| `"8084012345"` (Luhn-valid NPI) | Prescriber with that NPI | nppes |
| `"00071-0155"` (NDC prefix) | Drug matching that NDC | fda-ndc |
| `"J0135"` | HCPCS code J0135 (Adalimumab injection) | hcpcs |
| `"Z87.891"` | ICD-10 code Z87.891 (Personal history of nicotine dependence) | icd10-cm |
| `"excluded corp"` | SAM exclusion matching that entity name | sam_exclusions |

These tests use fixture data and the `rankResults()` pure function — no
backend required.

### 9.5 Ingestion idempotency tests

- Trigger ingestion for a source → assert `IngestionRun` row created (status=running).
- Trigger same source again while first is running → assert 409 returned.
- Mock run completion → assert quality dashboard reflects new record count.
- Trigger with unknown source → assert 404 returned.

### 9.6 Cross-tenant isolation

Reference data (`nppes`, `fda-ndc`, etc.) is **not tenant-scoped** — it is
shared read-only data. Ingestion runs in `shared.ingestion_runs` use the
shared schema, not per-tenant. No cross-tenant test is required for the
reference data browse surfaces themselves.

**Exception 1 — pharmacy stats endpoint.** `GET /api/v1/pharmacies/stats`
(pharmacy-directory `router.py:440`) signature: `tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")]` — this is a **mandatory** query parameter, not optional. The BFF MUST:
- Extract `tid` from the JWT via `packages/auth` and pass it as `?x-tenant-id={tid}` on every call to this endpoint. Without it the backend will return 422 (missing required field).
- Strip or clearly label tenant-scoped aggregate fields (`total_networks`, `pending_credentialing`) in the quality dashboard — these reflect tenant state, not global reference data freshness.
- Have a per-endpoint cross-tenant isolation test: call with `tid_A` JWT, call with `tid_B` JWT, assert that global reference-data fields (pharmacy record counts from public sources) are identical and that tenant-scoped fields reflect each tenant's own data only.

**Exception 2 — drug overrides surface (NOT in SP-2 scope).** If a future
surface displays tenant-specific overrides (e.g., `GET /api/v1/drugs/overrides`),
that surface MUST have a per-endpoint cross-tenant isolation test per
`.claude/rules/tenant-isolation.md`. This is excluded from SP-2 per §3.

The BFF `/api/directories/search` route extracts `tid` from the JWT (for
structured logging correlation) but does NOT use `tid` to filter reference
data queries — correct behavior for shared reference data. An integration
test asserts that requests with `tid_A` and `tid_B` return identical results
for the same search query (no tenant leakage in either direction).

### 9.7 Performance posture

Per SP-0 D2:
- Cmd+K typeahead: <100ms perceived; BFF fan-out budget 300ms.
- Per-dataset list pages: <150ms transition (TanStack Table + Virtual on
  paginated results; no 9.5M-row full-table renders — always search-first).
- Ingestion console: <150ms initial load (run history is paginated).
- Freshness dashboard: 60s cached; refetched on-focus.

---

## 10. Open questions / plan-time decisions

Intentionally deferred to plan-writing. Plan-writer must resolve:

1. **Search index vs BFF fan-out.** BFF fan-out is correct for SP-2 launch.
   If end-to-end search latency (backend response times + fan-out overhead)
   cannot hit 300ms budget in practice, plan-writer should evaluate a
   lightweight search index (e.g., a materialized view in Postgres using
   `tsvector` / `pg_trgm`) as an alternative to a separate search service.
   Flag the decision at plan time with measured latency data.

2. **Plan phasing sequence.** Approach A (D6) locks search-spine first. Plan
   1 = federated search infra + Cmd+K + BFF fan-out route + quality dashboard
   skeleton. Subsequent plans wire per-dataset surfaces into the search spine
   one cluster at a time. Exact per-plan boundaries are for the plan-writer.

3. **Ingestion API host.** The shared ingestion API (`shared/data_ingestion/api/routes.py`)
   must be mounted on a running FastAPI app for the BFF to call. Which
   module hosts it, and on which port, is not confirmed in this spec. Plan-
   writer must verify (via `grep -rn "ingestion" modules/*/src/main.py`)
   which module mounts the ingestion router, or scaffold the mount if missing.

4. **`portal/operator/app/directories/` migration strategy.** The existing
   four directory pages (`prescribers/`, `pharmacies/`, `drugs/`, `members/`)
   call backends directly via `apiGet`. SP-2 migrates these to the contract-
   layer BFF pattern. Plan-writer decides: (a) migrate in-place and adopt
   into the module package, or (b) create new pages in the module package and
   deprecate the old paths.
   Note: `members/` is a member-management surface (members, enrollment,
   eligibility) — it is NOT reference data and should NOT be included in the
   SP-2 directories module. Plan-writer must explicitly exclude it and flag
   it as a future member-management UI vertical.

5. **Quality alert persistence.** In SP-2, dismissed alerts are session-local
   or Redis-keyed per `{tid}:{source}`. If persistent alert state (survives
   session, visible to all operators in the same tenant) is needed, a thin
   backend resource is required. Plan-writer decides.

6. **BPG ingestion trigger.** BPG (`data/reference/bpg/`) is a live external
   API (`patientlens-api`), not a batch-loaded file. There is no ingestion
   schedule for it in `shared.ingestion_runs`. The ingestion console should
   show BPG as "Live API — no ingestion schedule" rather than a freshness
   chip. Plan-writer confirms this behavior.

7. **`relay-health/` vs `RelayHealth/` directory.** Both exist in
   `data/reference/`. Plan-writer determines which is canonical and whether
   the loader reads both or only one.

8. **`medicaid/` BIN coverage maps.** `data/reference/medicaid/` contains
   regional CSVs (`midwest.csv`, `northeast.csv`, etc.) and a
   `coverage_report.md`. The exclusions surface groups this under "Medicaid
   BINs" but the data may be coverage maps, not exclusions. Plan-writer
   clarifies the correct browse surface and label before building.

---

## 11. Cross-references

**Founding specs (binding):**
- SP-0 spec: `docs/superpowers/specs/2026-05-14-sp0-integration-foundation-design.md`
- SP-0 auth contract (SD-1): `docs/superpowers/specs/2026-05-15-sp0-decision-spike-auth-interface.md`
- SP-0 composition (SD-4): `docs/superpowers/specs/2026-05-15-sp0-decision-spike-composition.md`
- SP-1 spec (format template): `docs/superpowers/specs/2026-05-16-sp1-paysync-operator-portal-design.md`
- SP-1 codex NO-GO (failure modes to avoid): `docs/superpowers/codex-sp1-review-r1.md`

**Project rules (binding):**
- `CLAUDE.md` — principles, module table, environment architecture, auto-gate
- `.claude/rules/architecture.md` — module structure, shared code, LESSON-006
- `.claude/rules/code-standards.md` — naming, LESSON-005 logging keys
- `.claude/rules/error-handling.md` — error envelope, HTTP status codes
- `.claude/rules/event-bus.md` — EventEnvelope requirements (no new events in SP-2; if added, EventEnvelope + ordering_key + idempotency_key + schema_version required)
- `.claude/rules/phi-compliance.md` — PHI encryption (not triggered in SP-2; rules stated for guard)
- `.claude/rules/security.md` — auth, input validation, secrets
- `.claude/rules/tenant-isolation.md` — cross-tenant tests (not triggered for shared reference data; rules stated for guard)
- `.claude/rules/testing.md` — 100%/99% coverage gates, SQLAlchemy fixture pattern

**Existing code SP-2 wraps or calls:**
- `portal/operator/app/directories/prescribers/page.tsx` — existing prescribers list page
- `portal/operator/app/directories/pharmacies/page.tsx` — existing pharmacies list page
- `portal/operator/app/directories/drugs/page.tsx` — existing drugs list page
- `modules/prescriber-directory/src/api/router.py` — prescriber backend routes
- `modules/pharmacy-directory/src/api/router.py` — pharmacy backend routes
- `modules/drug-database/src/api/router.py` — drug backend routes
- `shared/data_ingestion/api/routes.py` — ingestion trigger + run status API
- `shared/data_ingestion/sources/` — 15 confirmed batch loaders (verified `_SOURCE_NAME` keys: `nppes`, `ncpdp`, `fda_ndc`, `fda_orange_book`, `fda_purple_book`, `fda_drug_shortages`, `fda_rems`, `hcpcs`, `icd10_cm`, `cms_asp`, `cms_nadac`, `cms_opt_out`, `ofac_sdn`, `sam_exclusions`, `state_medicaid_bins`); 3 additional `data/reference/` dirs (`relay-health/`, `fdb/`, `bpg/`) have no confirmed `_SOURCE_NAME`
- `shared/data_ingestion/models.py` — `IngestionRun` + `IngestionSchedule` ORM models
- `data/reference/` — reference data directory verified by `ls data/reference/`

**Parallel track:**
- B9 wave: FDB Tier B–D ingestion (`modules/drug-database/scripts/gen_fdb_tier_b_scaffolding.py`). SP-2 does not wait for B9; mock FDB surfaces until B9 lands.

**Decomposition context:**
- Sub-project of: Operator Portal & Platform Frontend milestone (decomposed 2026-05-14)
- SP-0 (spine), SP-1 (PaySync), **SP-2 (Directories)** ← this spec, SP-3 (Billing/Analytics), SP-4 (ReclaimRx), SP-5 (Claims/Adjudication), SP-6 (No-code program designer), SP-7 (Medical EDI)

---

## 12. Next steps

1. **Codex spec review** (automated by dispatching agent per process).
2. If GO or GO-WITH-CHANGES: address findings, then invoke `writing-plans`
   to produce SP-2 implementation plans.
3. Plans must: verify ingestion API mount host (§10.3), confirm `members/`
   exclusion from scope (§10.4), resolve `relay-health/` canonical source
   (§10.7), clarify `medicaid/` surface label (§10.8), and not repeat the
   SP-1 NO-GO failure modes (invented paths, wrong ORM names, 95% coverage
   gate, missing EventEnvelope, missing cross-tenant tests).

---

*End of spec.*
