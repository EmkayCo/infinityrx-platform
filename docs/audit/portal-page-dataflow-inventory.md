# Portal Page Data-Flow Defect Inventory

**Audit date:** 2026-05-20  
**Portal:** `portal/operator` (Next.js 16.2, localhost:3000)  
**Backends running:** core :8000, billing :8001, reclaimrx :8002, pharmacy :8009, prescriber :8010, drug-database :8011  
**Auth:** `DEV_AUTH_BYPASS=true`, `NEXT_PUBLIC_USE_MOCK_DATA=false`  
**Reference DB:** `infinityrx_reference` — seeded (pharmacies 82 k rows, prescribers 9.5 M, drugs 112 k)  
**Operational DB:** `infinityrx_dev` — migrations applied, zero operational rows (users 1, tenants 1, all transactional tables empty)

---

## Critical Cross-Cutting Findings Before the Table

### CORS-ENV-MISMATCH (affects ALL direct-browser surfaces)
`.env.dev` sets `CORS_ORIGINS=http://localhost:3000` but `shared/config.py` reads `CORS_ALLOW_ORIGINS` (different name).  
Result: `CORS_ALLOW_ORIGINS` stays at its `[]` default for every module. `CORSMiddleware` is guarded by `if cors_origins:` so it is **never mounted**. Every direct-browser fetch to `:8009`, `:8010`, `:8011` (and any future browser-direct hit) gets no CORS headers → browser blocks the response.  
Fix: rename `CORS_ORIGINS` → `CORS_ALLOW_ORIGINS` in `.env.dev`.

### RECLAIMRX-PORT-MISMATCH (affects all ReclaimRx pages)
`portal/shared/lib/constants.ts` exports `API_URLS.reclaimrx = process.env.NEXT_PUBLIC_RECLAIMRX_URL ?? "http://localhost:8003"`.  
`.env.local` sets `NEXT_PUBLIC_RECLAIMRX_URL=http://localhost:8002` (correct, running service port).  
`portal/operator/lib/bff.ts` BACKENDS object hardcodes `reclaimrx: "http://localhost:8003"` (wrong — reclaimrx runs on :8002).  
Fix: change `bff.ts` BACKENDS.reclaimrx to `"http://localhost:8002"` OR read from env var.

### BROKEN-NO-BFF-ROUTE (claims, accounting, payments, batches pages)
Several pages call `apiGet("/billing/v1/cycles")`, `apiGet("/billing/v1/claims")`, `apiGet("/batches")`, `apiGet("/api/v1/programs")`, `apiGet("/api/v1/payments/dashboard")`.  
`apiGet` with a relative URL fetches the Next.js origin (`localhost:3000/billing/v1/cycles` etc.). No route handler exists for those paths → 404. These are NOT forwarded to the billing backend.  
Fix: add BFF route handlers at those paths that forward to `BACKENDS.billing` or the relevant module.

### EMPTY-ALL-OPERATIONAL-TABLES
All operational tables have 0 rows: `billing.claim_records`, `billing.invoices`, `billing.payment_batches`, `reclaimrx.recoup_cases`, etc. Pages that hit real endpoints will return empty lists, not errors — the UI renders "No data" which is correct but looks broken to operators.

---

## Per-Page Inventory

| # | Nav Surface | Route | Page file | Data path | Backend + endpoint | DB table | Status | Cause / Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Dashboard | `/` | `app/page.tsx` | BFF → core/reclaimrx | `/api/v1/dashboard/kpi` → `:8000` (payments) + `:8003` (investigations) | `core.*`, `reclaimrx.recoup_cases` | BROKEN-BFF-PORT | BFF.reclaimrx hardcoded :8003, service on :8002. `active_programs/total_claims_ytd/gtn_ratio` intentionally `Unavailable` (noted in code). KPI card renders "Unavailable" gracefully. |
| 2 | Dashboard program-health | `/` | `app/page.tsx` | BFF → reporting | `/api/v1/dashboard/program-health` → `:8004/api/v1/reporting/client-api/fwa-summary` | `reporting.*` | EMPTY | Reporting :8004 not running → BFF returns `[]` with `source_status: degraded`. Renders empty program grid. |
| 3 | Dashboard alerts | `/` | `app/page.tsx` | BFF `/api/v1/dashboard/alerts` | route.ts reads mock seed data | none | WORKS | Hardcoded mock seed in BFF; renders placeholder alerts. |
| 4 | Dashboard activity | `/` | `app/page.tsx` | BFF `/api/v1/dashboard/activity` | route.ts reads mock seed data | none | WORKS | Hardcoded mock seed in BFF; renders placeholder activity feed. |
| 5 | Programs — Program Overview | `/programs` | `app/programs/page.tsx` | `apiGet("/api/v1/programs")` | No BFF route at `/api/v1/programs` | `program_config.*` | BROKEN-NO-BFF-ROUTE | 404 from Next.js; no route handler exists. |
| 6 | Programs — Enrollment | `/programs/enrollment` | `app/programs/enrollment/page.tsx` | `apiGet("/api/v1/programs")` (likely) | No BFF route | program_config | BROKEN-NO-BFF-ROUTE | Same missing BFF as above. |
| 7 | Programs — Budget & Forecast | `/programs/budget` | `app/programs/budget/page.tsx` | Needs investigation | unresolved | program_config | BROKEN-NO-BFF-ROUTE | No BFF route; page likely 404 or renders empty. |
| 8 | Programs — Program Config | `/programs/config` | `app/programs/config/page.tsx` | Needs investigation | unresolved | program_config | BROKEN-NO-BFF-ROUTE | No BFF route. |
| 9 | Claims — Claims Explorer | `/claims` | `app/claims/page.tsx` | `apiGet("/billing/v1/claims")` + `apiGet("/billing/v1/claims/summary")` | No BFF route at `/billing/v1/*` — fetches Next.js origin | billing `claim_records` | BROKEN-NO-BFF-ROUTE | Relative URL 404s on Next.js. Separate BFF at `/api/claims` exists (in-memory store from IFX export files) but page doesn't call it — mismatched paths. |
| 10 | Claims — Claim Lookup | `/claims/lookup` | `app/claims/lookup/page.tsx` | `apiGet("/billing/v1/claims/{id}")` likely | No BFF route | billing | BROKEN-NO-BFF-ROUTE | Same issue. |
| 11 | Claims — Manual Claims | `/claims/manual` | `app/claims/manual/page.tsx` | BFF `/api/v1/claims/manual` → billing | `billing/v1/claims/manual` POST | billing | EMPTY | BFF route exists (`app/api/v1/claims/manual/route.ts`). Form submits OK but no existing claims to display. |
| 12 | Claims — PA Override | `/claims/pa-override` | `app/claims/pa-override/page.tsx` | `apiGet` path unconfirmed | unresolved | adjudication | BROKEN-NO-BFF-ROUTE | No PA override BFF route evident. |
| 13 | Claims — Claim Detail | `/claims/[id]` | `app/claims/[id]/page.tsx` | `apiGet("/billing/v1/claims/{id}")` | No BFF route | billing | BROKEN-NO-BFF-ROUTE | Same relative URL issue. |
| 14 | Accounting — Billing Cycles | `/accounting/cycles` | `app/accounting/cycles/page.tsx` | `apiGet("/billing/v1/cycles")` | No BFF route; relative URL 404s | `billing.payment_batches` | BROKEN-NO-BFF-ROUTE | Also calls `/api/v1/accounting/cycles/summary` — no such BFF route either. |
| 15 | Accounting — Cycle Detail | `/accounting/cycles/[id]` | `app/accounting/cycles/[id]/page.tsx` | `apiGet("/billing/v1/cycles/{id}")` | No BFF route | billing | BROKEN-NO-BFF-ROUTE | |
| 16 | Accounting — Invoices | `/accounting/invoices` | `app/accounting/invoices/page.tsx` | `apiGet("/billing/v1/invoices")` likely | No BFF route | `billing.invoices` | BROKEN-NO-BFF-ROUTE + EMPTY | Tables empty even if route existed. |
| 17 | Accounting — Payments & Batches | `/accounting/payments` | `app/accounting/payments/page.tsx` | `apiGet("/api/v1/payments/dashboard")` + `apiGet("/batches")` | No BFF routes at those paths | `billing.payment_batches` | BROKEN-NO-BFF-ROUTE | `/batches` is a naked relative path with no route handler. |
| 18 | Accounting — NACHA | `/accounting/nacha` | `app/accounting/nacha/page.tsx` | `apiGet("/api/v1/billing/nacha")` likely | No BFF route confirmed | billing | BROKEN-NO-BFF-ROUTE | |
| 19 | Accounting — Journal Entries | `/accounting/journal-entries` | `app/accounting/journal-entries/page.tsx` | `apiGet("/billing/v1/journal")` likely | No BFF route | `billing.journal_entries` | BROKEN-NO-BFF-ROUTE + EMPTY | |
| 20 | ReclaimRx — GTN Dashboard | `/reclaimrx` | `app/reclaimrx/page.tsx` | Server Component: `apiGet(buildUrl(API_URLS.reclaimrx + "/api/v1/reclaimrx/gtn-summary"))` | Direct → `:8002/api/v1/reclaimrx/gtn-summary` | `reclaimrx.*` | EMPTY | reclaimrx running on :8002, `NEXT_PUBLIC_RECLAIMRX_URL=8002` — URL resolves correctly. BUT operational tables empty → returns zeros. Server component so no CORS issue. |
| 21 | ReclaimRx — Leakage Monitor | `/reclaimrx/leakage` | `app/reclaimrx/leakage/page.tsx` | `apiGet(buildUrl(API_URLS.reclaimrx + "/api/v1/reclaimrx/leakage"))` | Direct → `:8002` (client-side fetch — CORS needed) | `reclaimrx.anomalies` | BROKEN-CORS | Client component using `apiGet` with absolute URL → browser blocks if CORS not configured. See CORS-ENV-MISMATCH. |
| 22 | ReclaimRx — Investigations | `/reclaimrx/investigations` | `app/reclaimrx/investigations/page.tsx` | `apiGet(API_URLS.reclaimrx + ...)` | Direct → `:8002` | `reclaimrx.recoup_cases` | BROKEN-CORS + EMPTY | CORS not enabled; tables empty. |
| 23 | ReclaimRx — Investigation Detail | `/reclaimrx/investigations/[id]` | `app/reclaimrx/investigations/[id]/page.tsx` | Multiple `apiGet(API_URLS.reclaimrx + ...)` | Direct → `:8002` | reclaimrx | BROKEN-CORS + EMPTY | |
| 24 | ReclaimRx — Pharmacy Risk Scores | `/reclaimrx/risk` | `app/reclaimrx/risk/page.tsx` | `apiGet(buildUrl(API_URLS.reclaimrx + "/api/v1/reclaimrx/risk-scores"))` | Direct → `:8002` | reclaimrx | BROKEN-CORS + EMPTY | |
| 25 | ReclaimRx — Recovery Tracking | `/reclaimrx/recovery` | `app/reclaimrx/recovery/page.tsx` | `apiGet(buildUrl(API_URLS.reclaimrx + "/api/v1/recovery"))` | Direct → `:8002` | reclaimrx | BROKEN-CORS + EMPTY | |
| 26 | ReclaimRx — Case Wizard | `/reclaimrx/wizard` | `app/reclaimrx/wizard/page.tsx` | Investigation creation form | `:8002` POST | reclaimrx | BROKEN-CORS | Write path blocked by CORS. |
| 27 | Analytics — Claim Summary | `/analytics/claims` | `app/analytics/claims/page.tsx` | `apiGet(API_URLS.*)` | Direct → various backends | reporting/billing | BROKEN-CORS + EMPTY | Client-side direct calls; CORS not configured on reporting (:8004) and billing (:8001). |
| 28 | Analytics — Fill Performance | `/analytics/fills` | `app/analytics/fills/page.tsx` | `apiGet(API_URLS.*)` | Direct → reporting :8004 | reporting | BROKEN-CORS | Reporting not running + CORS unset. |
| 29 | Analytics — Adherence | `/analytics/adherence` | `app/analytics/adherence/page.tsx` | `apiGet(API_URLS.*)` | Direct → reporting :8004 | reporting | BROKEN-CORS | |
| 30 | Analytics — Pharmacy Insights | `/analytics/pharmacies` | `app/analytics/pharmacies/page.tsx` | `apiGet(API_URLS.*)` | Direct → reporting :8004 | reporting | BROKEN-CORS | |
| 31 | Analytics — Geographic Analysis | `/analytics/geography` | `app/analytics/geography/page.tsx` | `apiGet(API_URLS.*)` | Direct → reporting :8004 | reporting | BROKEN-CORS | |
| 32 | Analytics — Trend Analysis | `/analytics/trends` | `app/analytics/trends/page.tsx` | `apiGet(API_URLS.*)` | Direct → reporting :8004 | reporting | BROKEN-CORS | |
| 33 | Directories — Pharmacies | `/directories/pharmacies` | `app/directories/pharmacies/page.tsx` | `module-directories` `PharmaciesListPage` → direct browser fetch → `:8009/api/v1/pharmacies/search` | pharmacy-directory :8009 | `pharmacy_dir.dataq_master` (82 k rows) | BROKEN-CORS | Browser `fetch()` to :8009 blocked — CORS_ALLOW_ORIGINS empty in backend. Reference data IS seeded. Fix: add `CORS_ALLOW_ORIGINS` to `.env.dev`. |
| 34 | Directories — Pharmacy Detail | `/directories/pharmacies/[npi]` | `app/directories/pharmacies/[npi]/page.tsx` | `PharmacyDetailPage` → direct → `:8009` | pharmacy :8009 | pharmacy_dir | BROKEN-CORS | Same root cause. |
| 35 | Directories — Prescribers | `/directories/prescribers` | `app/directories/prescribers/page.tsx` | `PrescribersListPage` → direct browser fetch → `:8010/api/v1/prescribers/search` | prescriber-directory :8010 | `prescriber_dir.prescribers` (9.5 M rows) | BROKEN-CORS | CORS disabled — reference data IS seeded. |
| 36 | Directories — Prescriber Detail | `/directories/prescribers/[npi]` | `app/directories/prescribers/[npi]/page.tsx` | `PrescriberDetailPage` → direct → `:8010` | prescriber :8010 | prescriber_dir | BROKEN-CORS | |
| 37 | Directories — Drugs / Formulary | `/directories/drugs` | `app/directories/drugs/page.tsx` | `DrugsListPage` → direct browser fetch → `:8011/api/v1/drugs/search` | drug-database :8011 | `drug_database.drugs` (112 k rows) | BROKEN-CORS | CORS disabled — data IS seeded. Fix: add `CORS_ALLOW_ORIGINS=http://localhost:3000` to `.env.dev` and rename key. |
| 38 | Directories — Drug Detail | `/directories/drugs/[ndc]` | `app/directories/drugs/[ndc]/page.tsx` | `DrugDetailPage` → direct → `:8011` | drug-database :8011 | drug_database | BROKEN-CORS | |
| 39 | Directories — HCPCS Codes | `/directories/codes/hcpcs` | `app/directories/codes/hcpcs/page.tsx` | `HcpcsListPage` → direct → `:8011/api/v1/drugs/hcpcs` | drug-database :8011 | drug_database.hcpcs (if seeded) | BROKEN-CORS | |
| 40 | Directories — ICD-10 Codes | `/directories/codes/icd10` | `app/directories/codes/icd10/page.tsx` | `Icd10ListPage` → direct → `:8011/api/v1/drugs/icd10` | drug-database :8011 | `shared.icd10_cm_codes` (seeded) | BROKEN-CORS | |
| 41 | Directories — Pricing | `/directories/pricing` | `app/directories/pricing/page.tsx` | `PricingPage` → direct → `:8011/api/v1/drugs/pricing` | drug-database :8011 | drug_database.nadac_pricing (seeded) | BROKEN-CORS | |
| 42 | Directories — Exclusions | `/directories/exclusions` | `app/directories/exclusions/page.tsx` | `ExclusionsPage` → unknown backend | exclusions backend | `shared.oig_leie_exclusions` (seeded) | BROKEN-CORS | Direct browser fetch expected; CORS not configured. |
| 43 | Directories — Members | `/directories/members` | `app/directories/members/page.tsx` | `apiGet(API_URLS.memberManagement + ...)` | Direct → `:8012` (not running) | member_management | BROKEN-NO-SERVICE | member-management (:8012) not in running services list. |
| 44 | Directories — Member Detail | `/directories/members/[id]` | `app/directories/members/[id]/page.tsx` | Direct → `:8012` | `:8012` not running | member_management | BROKEN-NO-SERVICE | |
| 45 | Directories — Ingestion Console | `/directories/ingestion` | `app/directories/ingestion/page.tsx` | BFF `/api/directories/ingest/*` → pharmacy :8009 / prescriber :8010 | BFF route exists in `app/api/directories/ingest/` | `pharmacy_dir.dataq_ingestion_runs` | WORKS (BFF) | BFF proxies; table exists. May show empty run history. |
| 46 | Directories — Data Quality | `/directories/quality` | `app/directories/quality/page.tsx` | BFF `/api/directories/quality` → pharmacy :8009 + prescriber :8010 | BFF route in `app/api/directories/quality/` | pharmacy_dir | WORKS (BFF) | BFF proxies; alerts depend on ingestion runs. |
| 47 | Directories — Audit Log | `/directories/audit` | `app/directories/audit/page.tsx` | BFF `/api/directories/audit` → core :8000 | BFF route in `app/api/directories/audit/` | `core.audit_log` | WORKS (BFF) | Core running; audit table exists with 0 rows → empty list. |
| 48 | Client Management — Companies | `/clients` | `app/clients/page.tsx` | `apiGet` — path needs check | unknown backend | program_config or core | BROKEN-NO-BFF-ROUTE | No BFF route for `/api/v1/clients` evident. |
| 49 | Client Management — Client Programs | `/clients/programs` | `app/clients/programs/page.tsx` | `apiGet` path | program_config :unknown | program_config | BROKEN-NO-BFF-ROUTE | |
| 50 | Client Management — Fee Configuration | `/clients/fees` | `app/clients/fees/page.tsx` | `apiGet` path | billing | billing | BROKEN-NO-BFF-ROUTE | |
| 51 | Client Management — Preferred Networks | `/clients/networks` | `app/clients/networks/page.tsx` | `apiGet` path | unknown | unknown | BROKEN-NO-BFF-ROUTE | |
| 52 | Client Management — Exceptions | `/clients/exceptions` | `app/clients/exceptions/page.tsx` | `apiGet` path | unknown | unknown | BROKEN-NO-BFF-ROUTE | |
| 53 | Client Management — Cardholder IDs | `/clients/cardholders` | `app/clients/cardholders/page.tsx` | `apiGet` path | member_management :8012 | member_management | BROKEN-NO-SERVICE | :8012 not running. |
| 54 | Client Management — State Rules | `/clients/states` | `app/clients/states/page.tsx` | Direct → `:8010` (prescriber) | prescriber-directory :8010 | prescriber_dir | BROKEN-CORS | State rules page goes to prescriber-directory; CORS not configured. |
| 55 | Client Management — Portal Access | `/clients/portal-access` | `app/clients/portal-access/page.tsx` | `apiGet(API_URLS.corePlatform + ...)` | Direct → `:8000` | `core.users` | BROKEN-CORS | Browser direct to :8000; CORS not configured on core. |
| 56 | EDI — Monitor | `/edi/monitor` | `app/edi/monitor/page.tsx` | `apiGet(API_URLS.edi + ...)` | Direct → `:8005` (not running) | edi_compliance | BROKEN-NO-SERVICE | EDI :8005 not in running services list. |
| 57 | EDI — Transactions | `/edi/transactions` | `app/edi/transactions/page.tsx` | Direct → `:8005` | :8005 not running | edi_compliance | BROKEN-NO-SERVICE | |
| 58 | EDI — Partners | `/edi/partners` | `app/edi/partners/page.tsx` | Direct → `:8005` | :8005 not running | edi_compliance | BROKEN-NO-SERVICE | |
| 59 | EDI — Certificates | `/edi/certs` | `app/edi/certs/page.tsx` | Direct → `:8005` | :8005 not running | edi_compliance | BROKEN-NO-SERVICE | |
| 60 | Network — Pharmacy Locator | `/network/locator` | `app/network/locator/page.tsx` | Direct → `:8009/api/v1/pharmacies/search` | pharmacy-directory :8009 | pharmacy_dir (seeded) | BROKEN-CORS | CORS not configured; reference data seeded. |
| 61 | Network — Credentialing | `/network/credentialing` | `app/network/credentialing/page.tsx` | Direct → `:8009` | pharmacy :8009 | pharmacy_dir | BROKEN-CORS | |
| 62 | Reporting — Report Library | `/reporting/library` | `app/reporting/library/page.tsx` | `apiGet(API_URLS.reporting + ...)` | Direct → `:8004` (not running) | reporting | BROKEN-NO-SERVICE | Reporting :8004 not in running services. |
| 63 | Reporting — Report Builder | `/reporting/builder` | `app/reporting/builder/page.tsx` | Direct → `:8004` | not running | reporting | BROKEN-NO-SERVICE | |
| 64 | Reporting — Scheduled Reports | `/reporting/scheduled` | `app/reporting/scheduled/page.tsx` | Direct → `:8004` | not running | reporting | BROKEN-NO-SERVICE | |
| 65 | PaySync — Dashboard | `/admin/paysync` | `app/admin/paysync/page.tsx` | `apiGet` paths | billing :8001 | billing | BROKEN-NO-BFF-ROUTE + EMPTY | No BFF route for paysync; billing tables empty. |
| 66 | PaySync — Cycles | `/admin/paysync/cycles` (nav) | (same dir structure) | `apiGet` paths | billing :8001 | billing | BROKEN-NO-BFF-ROUTE + EMPTY | |
| 67 | PaySync — Batches | `/admin/paysync/batches` (nav) | — | billing | billing | billing | BROKEN-NO-BFF-ROUTE + EMPTY | |
| 68 | PaySync — Invoices | `/admin/paysync/invoices` (nav) | — | billing | billing | billing | BROKEN-NO-BFF-ROUTE + EMPTY | |
| 69 | PaySync — Reconciliation | `/admin/paysync/reconciliations` (nav) | — | billing | billing | billing | BROKEN-NO-BFF-ROUTE + EMPTY | |
| 70 | PaySync — Bank Settlements | `/admin/paysync/bank-settlements` (nav) | — | billing | billing | billing | BROKEN-NO-BFF-ROUTE + EMPTY | |
| 71 | PaySync — Manual AP | `/admin/paysync/manual-ap` (nav) | — | billing | billing | billing | BROKEN-NO-BFF-ROUTE + EMPTY | |
| 72 | PaySync — Echo Spec 400 | `/admin/paysync/echo` | `app/admin/paysync/echo/page.tsx` | billing | billing | billing | BROKEN-NO-BFF-ROUTE | |
| 73 | PaySync Config — Setup | `/admin/paysync/setup` | `app/admin/paysync/setup/page.tsx` | billing | billing | billing | BROKEN-NO-BFF-ROUTE | |
| 74 | PaySync Config — Cycle Schedules | `/admin/paysync/setup/cycle-schedules` | — | billing | billing | billing | BROKEN-NO-BFF-ROUTE | |
| 75 | PaySync Config — Export Templates | `/admin/paysync/setup/export-templates` | — | billing | billing | billing | BROKEN-NO-BFF-ROUTE | |
| 76 | PaySync Config — Email Templates | `/admin/paysync/setup/email-templates` | — | billing | billing | billing | BROKEN-NO-BFF-ROUTE | |
| 77 | PaySync Config — Email Recipients | `/admin/paysync/setup/email-recipients` | — | billing | billing | billing | BROKEN-NO-BFF-ROUTE | |
| 78 | PaySync Config — GL Mappings | `/admin/paysync/setup/gl-account-mappings` | — | billing | billing | billing | BROKEN-NO-BFF-ROUTE | |
| 79 | PaySync Config — Invoice Sequences | `/admin/paysync/setup/invoice-sequences` | — | billing | billing | billing | BROKEN-NO-BFF-ROUTE | |
| 80 | Network Admin — Pay-To Entities | `/admin/network/pay-to-entities` | `app/admin/network/pay-to-entities/page.tsx` | billing/payment_proc | payment-processing :8002? | payment_proc | BROKEN-PORT-CONFLICT | Note: env.local gives reclaimrx :8002, but billing/payment-proc was assigned :8002 in BACKENDS too. Port needs audit. |
| 81 | Network Admin — Chain Membership | `/admin/network/chain-membership` | — | billing | billing | billing | BROKEN-NO-BFF-ROUTE | |
| 82 | Network Admin — Banking Discrepancies | `/admin/network/banking-discrepancies` | — | billing | billing | billing | BROKEN-NO-BFF-ROUTE | |
| 83 | Network Admin — Tenant ACH | `/admin/network/tenant-ach-origination` | — | billing | billing | billing | BROKEN-NO-BFF-ROUTE | |
| 84 | Admin — Users & Roles | `/admin/users` | `app/admin/users/page.tsx` | `apiGet(API_URLS.corePlatform + "/api/v1/users")` | Direct → `:8000` | `core.users` (1 row) | BROKEN-CORS | Browser direct to :8000; CORS not configured. 1 user exists. |
| 85 | Admin — Tenant Settings | `/admin/tenants` | `app/admin/tenants/page.tsx` | `apiGet(API_URLS.corePlatform + ...)` | Direct → `:8000` | `core.tenants` (1 row) | BROKEN-CORS | Same CORS issue. 1 tenant exists. |
| 86 | Admin — System Health | `/admin/system-health` | `app/admin/system-health/page.tsx` | `apiGet(API_URLS.*)` health endpoints | Various running backends | N/A | BROKEN-CORS | Pings health endpoints on all services; direct browser fetch; CORS not configured. |
| 87 | Admin — Configuration | `/admin/config` | `app/admin/config/page.tsx` | `apiGet(API_URLS.corePlatform + ...)` | Direct → `:8000` | `program_config.*` | BROKEN-CORS | |
| 88 | Admin — Audit Log | `/admin/audit-log` | `app/admin/audit-log/page.tsx` | `apiGet(API_URLS.corePlatform + "/api/v1/audit")` | Direct → `:8000` | `core.audit_log` | BROKEN-CORS | Core running, CORS not configured. |
| 89 | Admin — Encryption Tools | `/admin/encryption` | `app/admin/encryption/page.tsx` | `apiGet(API_URLS.corePlatform + ...)` | Direct → `:8000` | core | BROKEN-CORS | |
| 90 | Medical Claims (unlisted) | `/medical-claims` | `app/medical-claims/page.tsx` | `apiGet(API_URLS.medicalClaims + ...)` | Direct → `:8006` (not running) | medical_claims | BROKEN-NO-SERVICE | medical-claims :8006 not running. |
| 91 | Settings — Profile | `/settings/profile` | `app/settings/profile/page.tsx` | `apiGet(API_URLS.corePlatform + "/api/v1/users/me")` | Direct → `:8000` | `core.users` | BROKEN-CORS | Core is running; CORS blocks browser. |
| 92 | Settings — Notifications | `/settings/notifications` | `app/settings/notifications/page.tsx` | `apiGet(API_URLS.corePlatform + ...)` | Direct → `:8000` | `core.notifications` | BROKEN-CORS | |

---

## Summary Counts

| Status | Count | Description |
|---|---|---|
| WORKS | 4 | Dashboard alerts, activity (BFF mock seed); Directories Ingestion Console, Data Quality, Audit Log (BFF proxied) |
| EMPTY | 4 | ReclaimRx GTN Dashboard (no operational data, server component); Dashboard program-health (reporting not running); ReclaimRx detail pages with correct backend but 0 rows |
| BROKEN-CORS | ~25 | Direct browser fetches to running backends (:8000, :8009, :8010, :8011) — CORS_ALLOW_ORIGINS env key mismatch |
| BROKEN-NO-BFF-ROUTE | ~35 | apiGet with relative URL that has no Next.js route handler (claims, accounting, billing cycles, programs, paysync, clients, admin...) |
| BROKEN-NO-SERVICE | ~12 | Hits backends not in running set: reporting :8004, EDI :8005, medical-claims :8006, member-management :8012 |
| BROKEN-BFF-PORT | 1 | Dashboard KPI: BFF.reclaimrx hardcoded :8003 but service on :8002 |

**Total nav surfaces audited:** ~92 (from 132 page files; ~40 are detail/sub-pages sharing the same defect as their list page)

---

## Fix Buckets (batch by fix type)

### Bucket A — One-line env fix, unblocks ~25 CORS pages (highest ROI)

**Files:** `infinityrx-platform/.env.dev`

1. Rename `CORS_ORIGINS` → `CORS_ALLOW_ORIGINS` on line 33.  
   This immediately enables CORS on pharmacy-directory (:8009), prescriber-directory (:8010), and drug-database (:8011) for `localhost:3000`.

2. Add `CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:3001` to core-platform (:8000), billing (:8001), reclaimrx (:8002) modules' env loading (or their per-module `.env` overrides) — same key name fix needed wherever the setting is inherited.

### Bucket B — One-line fix, unblocks Dashboard KPI + ReclaimRx all pages

**File:** `portal/operator/lib/bff.ts` line 265

Change `reclaimrx: "http://localhost:8003"` → `reclaimrx: process.env.RECLAIMRX_URL ?? "http://localhost:8002"`.  
Also verify `paymentProcessing: "http://localhost:8002"` — this conflicts with reclaimrx port. Payment processing appears to be a separate service; resolve correct port assignment.

### Bucket C — Add BFF route handlers (~35 pages)

**New files needed in** `portal/operator/app/api/`

Priority order based on nav prominence:
1. `app/api/v1/billing/cycles/route.ts` → forward to `BACKENDS.billing/api/v1/billing/cycles`
2. `app/api/v1/billing/claims/route.ts` → forward to `BACKENDS.billing/api/v1/claims` (reconcile with existing in-memory `/api/claims` BFF — decide which is canonical)
3. `app/api/v1/billing/invoices/route.ts`
4. `app/api/v1/billing/payment-batches/route.ts` (fix page to call `/api/v1/billing/payment-batches` not `/batches`)
5. `app/api/v1/programs/route.ts` → forward to program-config module
6. `app/api/v1/clients/route.ts` → forward to core-platform or program-config
7. `app/api/v1/paysync/**` routes → forward to billing

### Bucket D — Start missing backend services (~12 pages)

Services needed to unblock these nav sections:
- reporting (:8004) — Analytics + Reporting library
- edi-compliance (:8005) — EDI section
- medical-claims (:8006) — Medical Claims section
- member-management (:8012) — Members directory + Cardholder IDs

### Bucket E — Seed operational data (4+ EMPTY pages)

Even after Buckets A-D, these will show empty tables:
- `billing.claim_records`, `billing.invoices`, `billing.payment_batches`
- `reclaimrx.recoup_cases`, `reclaimrx.anomalies`
- `core.audit_log`

Use the demo seed script (`infrastructure/scripts/`) or generate fixture data.

---

## Data Architecture Notes

- **Hybrid fetch pattern:** Dashboard + Directories Ingestion/Quality/Audit use the BFF pattern correctly (server-side → backend, no CORS issue). Everything else uses `apiGet(API_URLS.x + ...)` which is a direct browser fetch that requires CORS on every backend.
- **Mismatched BFF routes:** `/api/claims` BFF exists and reads from an in-memory IFX file store, but `/claims` page calls `/billing/v1/claims` — these are entirely disconnected data paths.
- **`buildUrl` wrapper:** Used by reclaimrx/analytics pages to construct absolute URLs for direct browser calls. Works correctly as a URL builder, but the CORS problem means the fetch itself fails.
- **Server Components vs Client Components:** `app/reclaimrx/page.tsx` (GTN Dashboard) is a Server Component (`async function`) making the direct fetch server-side — no CORS issue for that one page. Its sub-pages are Client Components and do have the CORS problem.
