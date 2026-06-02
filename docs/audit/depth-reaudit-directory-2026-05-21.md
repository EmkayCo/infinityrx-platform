# Depth Re-Audit: Directory/Member/FWA/Rebate Cluster
**Date:** 2026-05-21  
**Scope:** directories (drug-database, pharmacy-directory, prescriber-directory), member-management, reclaimrx, rebate-management  
**Sources checked:** PRDs, portal/operator/app/**, packages/modules/{directories,reclaimrx}/src/**, manifest.json

---

## Classification Key

| State | Meaning |
|---|---|
| NOT_BUILT | No component exists anywhere |
| SCAFFOLD | Route exists; ComingSoonPage or empty stub only |
| BUILT_UNWIRED | Full component built, not reachable (not in manifest / module index empty / no route) |
| BUILT_WIRED | Route exists, component substantive, manifest includes it |

Effort: **S** = <1 pd, **M** = 1–3 pd, **L** = 4–8 pd, **XL** = 8+ pd

---

## DIRECTORIES CLUSTER (`@infinityrx/module-directories`)

**Module status:** In manifest (`modules: ["directories"]`). Barrel exports Plans A–D. All portal pages are thin wrappers importing from the package. Known issue: PharmacyDetailPage/PharmaciesListPage use `useQuery` directly inside the package with their own react-query instance — QueryClient crash vector documented (obs 2366, 2527).

| Surface | Designed? | Build State | Effort to Complete | Note |
|---|---|---|---|---|
| Drug search list (`/directories/drugs`) | Yes (PRD §drug-db) | BUILT_WIRED | S | Delegates to `DrugsListPage` from module-directories; BFF search route present |
| Drug detail page (`/directories/drugs/[ndc]`) | Yes | BUILT_WIRED | S | Delegates to `DrugDetailPage`; NDC param passed correctly |
| Drug pricing page (`/directories/pricing`) | Yes | BUILT_WIRED | S | Delegates to `PricingPage` from module-directories |
| Drug exclusions page (`/directories/exclusions`) | Yes | BUILT_WIRED | S | Delegates to `ExclusionsPage` from module-directories |
| HCPCS codes list (`/directories/codes/hcpcs`) | Yes | BUILT_WIRED | S | Delegates to `HcpcsListPage` |
| ICD-10 codes list (`/directories/codes/icd10`) | Yes | BUILT_WIRED | S | Delegates to `Icd10ListPage` |
| Pharmacy search list (`/directories/pharmacies`) | Yes (PRD §3) | BUILT_WIRED | M | `PharmaciesListPage` built with search+FreshnessChip; QueryClient crash risk on dual react-query instance |
| Pharmacy detail page (`/directories/pharmacies/[npi]`) | Yes | BUILT_WIRED | M | `PharmacyDetailPage` built with ProvenanceBadge, FreshnessChip, prescriber relationships cross-link; QueryClient crash risk; no credentialing tab |
| Prescriber search list (`/directories/prescribers`) | Yes (PRD §4) | BUILT_WIRED | S | `PrescribersListPage` from module-directories |
| Prescriber detail page (`/directories/prescribers/[npi]`) | Yes | BUILT_WIRED | S | `PrescriberDetailPage` with ExclusionAlertBadge, MonitoringPanel, FreshnessChip |
| Prescriber credential monitoring panel | Yes (PRD §4 DEA/license expiry) | BUILT_WIRED | S | `PrescriberMonitoringPanel` exists in module-directories src |
| Directories federated search / command palette | Yes (PRD §11) | BUILT_WIRED | S | `DirectoriesCommandPalette` + `FederatedSearchClient` in module-directories |
| Data ingestion console (`/directories/ingestion`) | Yes (PRD ops) | BUILT_WIRED | S | `IngestionConsolePage` with RunHistoryDrawer, RunProgressBar, TriggerRefreshButton; BFF ingest API routes present |
| Quality dashboard (`/directories/quality`) | Yes | BUILT_WIRED | S | `QualityDashboardPanel` + `IngestionAlertList` + `DismissAlertAction` |
| Audit log viewer (`/directories/audit`) | Yes | BUILT_WIRED | S | `AuditLogPage` in module-directories |
| Pharmacy network adequacy / map locator (`/network/locator`) | Yes (PRD §3 geographic access) | SCAFFOLD | L | `ComingSoonPage` only — no map component |
| Pharmacy credentialing queue + doc upload (`/network/credentialing`) | Yes (PRD §3 credentialing workflow: application→review→approval→monitoring) | SCAFFOLD | XL | `ComingSoonPage` only — designed 5-stage workflow completely absent |
| Pharmacy contract rate history | Yes (PRD §3 contract terms per pharmacy/network) | NOT_BUILT | L | No portal surface at any route |
| PSAO / LDD classification display | Yes (PRD §3 accreditation) | NOT_BUILT | M | No portal surface |

---

## MEMBER MANAGEMENT CLUSTER

**Module status:** Not a separate npm package — pages are self-contained in `portal/operator/app/directories/members/`. API calls go directly to `API_URLS.memberManagement`.

| Surface | Designed? | Build State | Effort to Complete | Note |
|---|---|---|---|---|
| Member list / search (`/directories/members`) | Yes (PRD §5) | BUILT_WIRED | S | Full DataTable with PHI masking, permission-gated name search, export, navigation to enroll/eligibility |
| Member detail page (`/directories/members/[id]`) | Yes | BUILT_WIRED | S | Identity, coverage, accumulators (deductible/OOP bars, benefit phase, TrOOP), copay enrollment cards, claims/prescriptions/adherence/eligibility-history tabs, PHI audit beacon |
| Enrollment file upload wizard (`/directories/members/enroll`) | Yes (PRD §5 834/CSV ingestion) | BUILT_WIRED | M | 4-step wizard (upload→validate→preview→confirm) using shared `Wizard` component; dropzone accepts .csv/.edi/.x12; validate/preview/apply API calls wired; missing: field mapping step (PRD step 2), CSV error download |
| Eligibility real-time check (`/directories/members/eligibility`) | Yes (PRD §5 270/271) | BUILT_WIRED | S | Single-form page: member_id + DOB → POST eligibility; renders coverage status, plan, group, dates |
| Accumulator display (deductible/OOP/TrOOP/benefit phase) | Yes (PRD §5) | BUILT_WIRED | S | AccumulatorBars component fully built with progress bars and benefit phase badge |
| Copay program enrollment display | Yes (PRD §5) | BUILT_WIRED | S | CopayEnrollmentCard with benefit remaining progress bar, card status badge |
| Member claims history tab | Yes | BUILT_WIRED | S | DataTable wired to `/api/v1/members/{id}/claims` |
| Adherence tab (PDC scores) | Yes (PRD §5) | SCAFFOLD | M | Static hardcoded KPIs ("87%", "79%") — no live data fetch |
| Member group management | Yes (PRD §5 group/employer) | NOT_BUILT | M | No group CRUD surface in portal |
| COB management UI | Yes (PRD §5 COB primary/secondary/tertiary) | NOT_BUILT | M | No portal surface for COB editing |
| COBRA tracking | Yes (PRD §5 note in CLAUDE.md) | NOT_BUILT | M | No portal surface |

---

## RECLAIMRX CLUSTER

**Critical architecture finding:** `packages/modules/reclaimrx/src/index.ts` exports ONLY `config` — all sub-indexes (`investigations/index.ts`, `graph/index.ts`, `holds/index.ts`, `recovery/index.ts`, `rules/index.ts`, `ml/index.ts`) are empty stubs (`export {}`). Reclaimrx is NOT in `manifest.json` modules list (only `prescriber-directory`, `directories`, `paysync` are listed). However, the portal pages are self-contained (do not import from the reclaimrx package) and all portal routes exist. Classification is BUILT_WIRED for self-contained pages that are routable, SCAFFOLD for ComingSoonPage stubs.

| Surface | Designed? | Build State | Effort to Complete | Note |
|---|---|---|---|---|
| GTN Protection Dashboard (`/reclaimrx`) | Yes (PRD §arch + portal §7.5) | BUILT_WIRED | S | Server component; fetches gtn-summary + gtn-trend; KpiCardRow (6 cards); GTNDashboardCharts client boundary; links to wizard and leakage |
| Investigation queue — kanban+table (`/reclaimrx/investigations`) | Yes (PRD §inv workflow) | BUILT_WIRED | M | Toggle kanban/table view; kanban via dynamic import `InvestigationsKanban`; table via `InvestigationsTable` |
| Investigation detail (`/reclaimrx/investigations/[id]`) | Yes | BUILT_WIRED | M | Recovery amounts (est/demanded/collected); flag evidence narrative; evidence checklist with toggle mutation; related claims DataTable; document upload dropzone (UI only, no POST); action timeline via ActivityFeed; "Continue Investigation" links to `/wizard` sub-route (route does not exist — dead link) |
| New case wizard — 7 steps (`/reclaimrx/wizard`) | Yes (PRD §7.5: 5-step investigation wizard) | BUILT_WIRED | M | 7 steps: category→subject→claims→estimate→assign→notes→review; entity/claims lists are MOCK data (hardcoded); submit is `setTimeout` not real API POST; draft auto-save not implemented |
| Leakage monitor (`/reclaimrx/leakage`) | Yes (PRD leakage tracking) | BUILT_WIRED | M | Full ConfigurableDataTable with FilterPanel (category/type/status/program); client-side filtering; row click → investigation or wizard; category color-coded badges |
| Recovery tracking dashboard (`/reclaimrx/recovery`) | Yes (PRD §recovery) | BUILT_WIRED | M | Server component fetching `/api/v1/recovery`; delegates to `RecoveryInteractive` client leaf |
| Pharmacy risk scores (`/reclaimrx/risk`) | Yes (PRD §entity profiles) | BUILT_WIRED | M | ConfigurableDataTable with RiskScoreBadge (bar+tier); risk tier color key; row click → pharmacy detail |
| Payment holds (`/reclaimrx/holds`) | Yes (PRD hold/block action) | SCAFFOLD | L | ComingSoonPage — "Plan D" |
| Threshold configuration (`/reclaimrx/thresholds`) | Yes (PRD §rule parameters) | SCAFFOLD | M | ComingSoonPage — "Plan C" |
| Fraud ring visualization (`/reclaimrx/fraud-rings`) | Yes (PRD graph analysis) | SCAFFOLD | XL | ComingSoonPage — "Plan E"; `graph/index.ts` is empty stub |
| Graph analysis runs (`/reclaimrx/graph-runs`) | Yes (PRD batch graph job) | SCAFFOLD | L | ComingSoonPage — "Plan E" |
| Accumulator anomaly detection (`/reclaimrx/accumulator-anomalies`) | Yes (PRD §3.5 accumulator detection) | SCAFFOLD | L | ComingSoonPage — "Plan E" |
| Demand letter generation (AI-drafted) | Yes (PRD §7.5 step 4) | NOT_BUILT | L | No portal surface; investigation wizard skips this step entirely |
| Real-time detection during adjudication (UI) | Yes (PRD §arch real-time path) | NOT_BUILT | XL | No portal surface; backend event consumers exist but no operator visibility |
| Reclaimrx module package exports | N/A — infra | BUILT_UNWIRED | M | All src sub-indexes are empty stubs; `index.ts` exports only `config`; manifest excludes module |

---

## REBATE MANAGEMENT CLUSTER

**Module status:** PRD is Phase 5. No portal pages exist anywhere under any route. Backend `modules/rebate-management/src/` has API/models/services scaffolding per CLAUDE.md status table but zero frontend.

| Surface | Designed? | Build State | Effort to Complete | Note |
|---|---|---|---|---|
| Rebate contract list / lifecycle | Yes (PRD §3 draft→termination) | NOT_BUILT | XL | No portal surface |
| Rebate contract detail + amendment tracking | Yes (PRD §3) | NOT_BUILT | L | No portal surface |
| Rebate calculation engine dashboard | Yes (PRD §4) | NOT_BUILT | XL | No portal surface |
| CAA 2026 pass-through ledger | Yes (PRD §2) | NOT_BUILT | XL | No portal surface |
| BFSF documentation + attestation | Yes (PRD §2) | NOT_BUILT | L | No portal surface |
| Semiannual transparency report generator | Yes (PRD §2) | NOT_BUILT | L | No portal surface |
| GTN waterfall dashboard | Yes (PRD §7 GTN waterfall) | NOT_BUILT | L | No portal surface (distinct from reclaimrx GTN dashboard) |
| Guaranteed spend cap / performance guarantees | Yes (PRD §5) | NOT_BUILT | XL | No portal surface |

---

## SUMMARY COUNTS

| Cluster | NOT_BUILT | SCAFFOLD | BUILT_UNWIRED | BUILT_WIRED | Total |
|---|---|---|---|---|---|
| Directories | 3 | 2 | 0 | 14 | 19 |
| Member Management | 3 | 1 | 0 | 7 | 11 |
| ReclaimRx | 2 | 6 | 1 | 7 | 16 |
| Rebate Management | 8 | 0 | 0 | 0 | 8 |
| **TOTAL** | **16** | **9** | **1** | **28** | **54** |

---

## EFFORT TOTAL

Rough person-days to reach BUILT_WIRED for all surfaces:

| Cluster | Gap surfaces | Rough pd |
|---|---|---|
| Directories (credentialing queue, map locator, contract history, PSAO) | 4 gaps | ~15 pd |
| Member Management (adherence live data, group mgmt, COB, COBRA) | 4 gaps | ~8 pd |
| ReclaimRx (holds, thresholds, fraud-ring viz, graph runs, accumulator anomalies, demand letters, real-time UI, wizard mock→real, module exports+manifest) | 9 gaps | ~35 pd |
| Rebate Management (8 surfaces, zero baseline) | 8 gaps | ~45 pd |
| **TOTAL** | **25 gaps** | **~103 pd** |

---

## HIGH WATER MARK

The genuinely BUILT_WIRED surfaces that demonstrate what "done" looks like:

**Directories cluster (high-water mark for the entire platform):**
- Drug search/detail/pricing/exclusions/codes — thin wrappers over a fully built, dist-compiled npm package with BFF routes, federated search, provenance badges, freshness chips, and exclusion alerts
- Ingestion console — scheduled + on-demand trigger, run history, progress bar, cancel — complete operator workflow
- Quality dashboard — alert list with dismiss action wired to BFF

**Member management (strong second):**
- Member detail page — PHI masking, accumulator progress bars, copay enrollment cards, 4-tab layout, PHI audit beacon — matches design almost exactly
- Enrollment wizard — 4-step, file dropzone, validate/preview/confirm — missing only the field-mapping step

**ReclaimRx (partially wired, promising):**
- GTN dashboard + leakage monitor + risk scores — server-fetched, real API URLs, full ConfigurableDataTable with filter panel
- Investigation detail — evidence checklist with mutations, recovery amounts, activity timeline

**The critical gap:** `packages/modules/reclaimrx/src/index.ts` exports only `config`. All module sub-indexes are empty stubs. The portal pages work because they are self-contained (not importing from the package), but the module is not in the manifest and has no shared package surface — any portal that wants to embed reclaimrx components has zero exports to import.

---

## KEY BLOCKING ISSUES

1. **ReclaimRx module not in manifest** — `manifest.json` lists `["prescriber-directory", "directories", "paysync"]` only. Adding reclaimrx requires both manifest update and populating the empty module src exports.
2. **PharmacyDetailPage QueryClient crash vector** — dual react-query instance in `module-directories` package causes "No QueryClient set" crash (documented fix plan at `docs/audit/queryclient-turbopack-fix-plan.md`).
3. **Investigation wizard uses mock data** — `StepSubject` and `StepClaims` have hardcoded MOCK_ENTITIES/MOCK_CLAIMS arrays; submit is `setTimeout` not a real API call.
4. **`/reclaimrx/investigations/[id]/wizard` dead link** — investigation detail "Continue Investigation" button routes to this path but no route file exists.
5. **Pharmacy credentialing queue** — the highest-value designed workflow (application→review→approval→monitoring) is entirely absent. ComingSoonPage with no plan assigned.
6. **Rebate management** — zero frontend. PRD is complete; 8 surfaces, ~45 pd of work, entirely Phase 5 deferred.
