# SP-2 Plan E — E2E Round-Trip, Synthetic Fixtures, QA Harness

**Status:** DRAFT  
**Date:** 2026-05-17  
**Vertical:** SP-2 Directories Portal / Reference Data Control Plane  
**Spec ref:** `docs/superpowers/specs/2026-05-16-sp2-directories-portal-design.md` §9, D5  
**Depends on:** Plans A–D (all components and BFF routes exist)  

---

## Purpose

Plan E delivers the shippable bar (D5): a complete E2E round-trip exercising:

```
⌘K → search → result → drill to detail → ProvenanceBadge + FreshnessChip
→ QualityDashboard freshness → TriggerRefreshButton → RunProgressBar runs
→ completes with record-count delta → DismissAlertAction
```

Also delivers: synthetic fixtures, search relevance regression tests,
QA harness additions, and integration test wiring for cross-dataset round-trip.

---

## Verified facts (pre-write grep confirmed)

| Fact | Verification |
|---|---|
| `portal/operator/tests/e2e/sp1-paysync-round-trip.spec.ts` | E2E pattern: `E2E_STACK_READY` gate, `CORE_BASE_URL`, `fetchJwt()`, dev-bypass auth |
| `portal/operator/tests/fixtures/mock-session.ts:30` | `authenticateDevBypass(context, BASE)` — dev-bypass auth helper |
| `portal/operator/tests/fixtures/mock-session.ts` | `mockSession()` returns `tenant_id: "00000000-0000-0000-0000-000000000001"` |
| `portal/operator/tests/e2e/directories/directories-detail.spec.ts` | Existing directories E2E; `drillToFirstRow()` helper pattern |
| `packages/modules/paysync/fixtures/seeds/` | Fixture seed pattern for SP-1 (template) |
| `packages/modules/paysync/fixtures/uploads/` | Upload fixtures for SP-1 |
| `packages/qa-harness/src/seeds/` | QA harness seed hooks location |
| `packages/qa-harness/src/index.ts` | QA harness public surface |
| SP-1 E2E uses `E2E_STACK_READY` env gate — SP-2 E2E follows same pattern |
| `portal/operator/playwright.config.ts` | Playwright config location |
| `data/reference/ofac-sdn/` | Real public OFAC SDN reference data |
| `data/reference/sam_exclusions/` | Real public SAM exclusion data |

---

## Synthetic fixtures (`packages/modules/directories/fixtures/`)

All fixtures are non-PHI (public reference data). Each file contains ~10 records.

### Structure

```
packages/modules/directories/fixtures/
  prescribers.json         ← 10 NPPES-shaped prescribers (Luhn-valid NPIs)
  pharmacies.json          ← 10 NCPDP-shaped pharmacies (invented NABP)
  drugs-fda-ndc.json       ← 10 FDA NDC records (real public NDCs)
  drugs-fdb-mock.json      ← 10 FDB-shaped mock records (b9_blocked, _mock:true)
  codes-hcpcs.json         ← 10 real public HCPCS codes
  codes-icd10.json         ← 10 real public ICD-10-CM codes
  pricing-cms-asp.json     ← 5 CMS-ASP pricing records
  pricing-cms-nadac.json   ← 5 CMS-NADAC pricing records
  exclusions-ofac.json     ← 5 OFAC SDN records (from public sdn.csv)
  exclusions-sam.json      ← 5 SAM exclusion records (from public data)
  ingestion-runs.json      ← 3 IngestionRun records: completed, failed, running
  ingestion-schedules.json ← Schedules for all 18 sources + nppes sub-modes
```

### Prescriber NPI validity

Per `.claude/rules/security.md`: NPIs validated with Luhn check (prefix 80840).
All 10 fixture NPIs are Luhn-valid with prefix 80840 (invented — do not use real
provider NPIs). Example: NPI `8084012345` passes Luhn check.

**Fixture NPI set** (invented, Luhn-valid, prefix 80840):
These must be computed at execution time by the implementing agent using the Luhn
algorithm with prefix 80840. The plan-writer does not pre-compute them here to
avoid arithmetic errors in a document.

### Key fixture records for E2E round-trip

The E2E spec needs at least one fixture prescriber that also appears in a fixture
exclusion source (to test the `ExclusionAlertBadge` cross-link). The implementing
agent creates one prescriber NPI that is also present in `exclusions-ofac.json`
(as a sanctioned entity name) — or in `exclusions-sam.json` if that's simpler
to cross-link.

### `ingestion-runs.json` shape (matches `shared/data_ingestion/api/schemas.py`)

```json
[
  {
    "id": "aaaaaaaa-0001-0001-0001-000000000001",
    "source": "nppes",
    "run_type": "full",
    "status": "completed",
    "records_processed": 9494438,
    "records_inserted": 9494438,
    "records_updated": 0,
    "records_skipped": 0,
    "records_errored": 0,
    "started_at": "2026-05-10T03:00:00Z",
    "completed_at": "2026-05-10T04:22:11Z",
    "duration_seconds": 4931,
    "error_message": null
  },
  {
    "id": "aaaaaaaa-0002-0002-0002-000000000002",
    "source": "fda_ndc",
    "run_type": "full",
    "status": "failed",
    "records_processed": 142000,
    "records_inserted": 0,
    "records_updated": 0,
    "records_skipped": 0,
    "records_errored": 3,
    "started_at": "2026-05-16T02:01:00Z",
    "completed_at": "2026-05-16T02:03:44Z",
    "duration_seconds": 164,
    "error_message": "Connection reset by peer on download.fda.gov"
  },
  {
    "id": "aaaaaaaa-0003-0003-0003-000000000003",
    "source": "ncpdp",
    "run_type": "full",
    "status": "running",
    "records_processed": 5200,
    "records_inserted": 5200,
    "records_updated": 0,
    "records_skipped": 0,
    "records_errored": 0,
    "started_at": "2026-05-17T09:00:00Z",
    "completed_at": null,
    "duration_seconds": null,
    "error_message": null
  }
]
```

Note: `completed_at` not `finished_at` — verified from `schemas.py:60`.

---

## Search relevance regression tests (`tests/unit/search-relevance.test.ts`)

Per spec §9.4. Uses `rankResults()` (Plan A) and fixture data. No backend required.

```typescript
// packages/modules/directories/tests/unit/search-relevance.test.ts
import { rankResults } from "../../src/search/rankResults.js";
import type { SearchResultRecord } from "../../src/search/schemas.js";

const FIXTURE_PRESCRIBER: SearchResultRecord = {
  dataset: "nppes",
  id: "8084012345",  // Luhn-valid NPI from fixture (exact value set at execution time)
  display: "Dr. Jane Smith DO",
  secondary: "Internal Medicine",
  source_date: "2026-05-10",
  run_id: "aaaaaaaa-0001-0001-0001-000000000001",
};

const FIXTURE_DRUG: SearchResultRecord = {
  dataset: "fda_ndc",
  id: "00071015523",   // Real public NDC (atorvastatin 20mg — public data)
  display: "Atorvastatin Calcium (Lipitor)",
  secondary: "atorvastatin calcium",
  source_date: "2026-05-10",
  run_id: null,
};

const FIXTURE_HCPCS: SearchResultRecord = {
  dataset: "hcpcs",
  id: "J0135",
  display: "Adalimumab injection",
  secondary: "J0135",
  source_date: "2026-05-10",
  run_id: null,
};

const FIXTURE_ICD10: SearchResultRecord = {
  dataset: "icd10_cm",
  id: "Z87.891",
  display: "Personal history of nicotine dependence",
  secondary: "Z87.891",
  source_date: "2026-05-10",
  run_id: null,
};

const FIXTURE_SAM: SearchResultRecord = {
  dataset: "sam_exclusions",
  id: "SAM-GUID-00001",
  display: "Excluded Corp LLC",
  secondary: "EXCLUDED CORP",
  source_date: "2026-05-10",
  run_id: null,
};

const ALL_FIXTURES = [FIXTURE_PRESCRIBER, FIXTURE_DRUG, FIXTURE_HCPCS, FIXTURE_ICD10, FIXTURE_SAM];

describe("search relevance regression", () => {
  test("NPI exact match scores top", () => {
    const results = rankResults(ALL_FIXTURES, "8084012345");
    expect(results[0].dataset).toBe("nppes");
    expect(results[0].id).toBe("8084012345");
  });

  test("NDC prefix match scores top for drug query", () => {
    // Query: NDC prefix (first 7 digits)
    const results = rankResults([FIXTURE_DRUG, FIXTURE_PRESCRIBER], "00071015");
    expect(results[0].dataset).toBe("fda_ndc");
  });

  test("HCPCS exact code match", () => {
    const results = rankResults(ALL_FIXTURES, "J0135");
    expect(results[0].id).toBe("J0135");
  });

  test("ICD-10 code match", () => {
    const results = rankResults(ALL_FIXTURES, "Z87.891");
    expect(results[0].id).toBe("Z87.891");
  });

  test("SAM exclusion entity name match", () => {
    const results = rankResults(ALL_FIXTURES, "excluded corp");
    expect(results[0].dataset).toBe("sam_exclusions");
  });

  test("lipitor drug prefix match", () => {
    const results = rankResults([FIXTURE_DRUG, FIXTURE_PRESCRIBER, FIXTURE_SAM], "lipitor");
    expect(results[0].dataset).toBe("fda_ndc");
    expect(results[0].display).toContain("Lipitor");
  });
});
```

---

## Integration tests (`tests/integration/`)

### `tests/integration/bff-fan-out.test.ts`

Requires docker-compose backends (prescriber-directory, pharmacy-directory,
drug-database) or MSW mock servers.

```typescript
// Tests:
// 1. Fan-out with all 3 backends up → merged results ≤ 20 records
// 2. Fan-out with prescriber-directory down → nppes absent from results;
//    is_partial=true; timed_out_datasets includes "nppes"
// 3. Fan-out with all backends down → empty results, is_partial=true
// 4. NPI shortcut ("8084012345") → single result, no fan-out to pharmacy/drug
// 5. Auth rejection: no JWT → 401
// 6. Cross-tenant: search with tid_A and tid_B → identical reference results
//    (no tenant leakage — reference data is shared)
```

### `tests/integration/ingestion-trigger-idempotency.test.ts`

Per spec §9.5.

```typescript
// Tests (requires prescriber-directory with ingestion router mounted per Plan C):
// 1. POST /api/directories/ingest/fda_ndc/trigger → 200, {run_id, status:"running"}
// 2. POST same source while first running → 409 with message "already has a running job"
// 3. POST non-triggerable source (bpg) → 404
// 4. POST unknown source → 404
// 5. Mock run completion → GET /api/directories/quality returns updated record counts
```

---

## E2E round-trip spec (`portal/operator/tests/e2e/sp2-directories-round-trip.spec.ts`)

Per spec D5. Uses same pattern as `sp1-paysync-round-trip.spec.ts`:
- `E2E_STACK_READY` gate
- `authenticateDevBypass` from `tests/fixtures/mock-session.ts`
- Service base URLs from env with localhost defaults

```typescript
/**
 * SP-2 Directories E2E round-trip spec.
 *
 * Exercises the full operator journey per spec D5:
 *   ⌘K → search → result → detail (ProvenanceBadge + FreshnessChip)
 *   → QualityDashboard → TriggerRefreshButton → RunProgressBar
 *   → completes → record-count delta → DismissAlertAction
 *
 * PREREQUISITE: Full docker-compose stack must be running:
 *   docker-compose up -d postgres redis prescriber-directory pharmacy-directory
 *                       drug-database core-platform
 *
 * Skip when E2E_STACK_READY !== "true":
 *   E2E_STACK_READY=true npx playwright test sp2-directories-round-trip
 */

import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../fixtures/mock-session";

const E2E_READY = process.env["E2E_STACK_READY"] === "true";
const BASE = "http://localhost:3000";
const PRESCRIBER_BASE =
  process.env["PRESCRIBER_DIRECTORY_URL"] ?? "http://localhost:8010";

// ── Scenario ──────────────────────────────────────────────────────────────────

test.describe("SP-2 Directories round-trip", () => {
  test.skip(!E2E_READY, "E2E_STACK_READY not set — skipping full stack test");

  test.beforeEach(async ({ context }) => {
    await authenticateDevBypass(context, BASE);
  });

  test("Cmd+K → search → drill → provenance → ingestion trigger → delta → dismiss", async ({ page }) => {
    // Step 1: Open portal, press ⌘K
    await page.goto(`${BASE}/directories`, { waitUntil: "networkidle" });
    await page.keyboard.press("Meta+K");
    await expect(page.locator('[role="dialog"]')).toBeVisible();

    // Step 2: Type a drug query → results appear grouped
    await page.keyboard.type("lipitor");
    await expect(page.locator('[data-testid="search-result-group-drugs"]')).toBeVisible({ timeout: 5_000 });
    const topResult = page.locator('[data-testid="search-result-item"]').first();
    await expect(topResult).toContainText("Atorvastatin");

    // Step 3: Click result → navigate to drug detail
    await topResult.click();
    await page.waitForURL(/\/directories\/drugs\//, { timeout: 10_000 });

    // Step 4: ProvenanceBadge visible
    await expect(page.locator('[data-testid="provenance-badge"]')).toBeVisible();
    await expect(page.locator('[data-testid="provenance-badge"]')).toContainText("Source: fda_ndc");

    // Step 5: FreshnessChip visible
    await expect(page.locator('[data-testid="freshness-chip"]')).toBeVisible();

    // Step 6: B9PendingBanner visible on Interactions tab
    await page.locator('[role="tab"]', { hasText: "Interactions" }).click();
    await expect(page.locator('[data-testid="b9-pending-banner"]')).toBeVisible();
    await expect(page.locator('[data-testid="b9-pending-banner"]')).toContainText("FDB B9 ingestion");

    // Step 7: Navigate to Ingestion Console
    await page.goto(`${BASE}/directories/ingestion`, { waitUntil: "networkidle" });
    await expect(page.locator('h1, [data-testid="ingestion-console-title"]')).toContainText("Ingestion Console");

    // Step 8: Find nppes row — TriggerRefreshButton present
    const nppesRow = page.locator('[data-testid="ingestion-row-nppes"]');
    await expect(nppesRow).toBeVisible();
    const triggerBtn = nppesRow.locator('[data-testid="trigger-refresh-btn"]');
    await expect(triggerBtn).toBeVisible();

    // Step 9: Trigger refresh
    await triggerBtn.click();
    // RunProgressBar should appear
    await expect(page.locator('[data-testid="run-progress-bar"]')).toBeVisible({ timeout: 5_000 });

    // Step 10: Wait for completion (polling every 5s; mock run completes quickly)
    await expect(page.locator('[data-testid="run-complete-delta"]')).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="run-complete-delta"]')).toContainText("records");

    // Step 11: QualityDashboard refetches — freshness chip updated
    await page.goto(`${BASE}/directories`, { waitUntil: "networkidle" });
    const qualityPanel = page.locator('[data-testid="quality-dashboard-panel"]');
    await expect(qualityPanel).toBeVisible();

    // Step 12: Find failed alert (fda_ndc from fixture with records_errored=3)
    const fdaNdcAlert = page.locator('[data-testid="ingestion-alert-fda_ndc"]');
    // Dismiss it
    const dismissBtn = fdaNdcAlert.locator('[data-testid="dismiss-alert-btn"]');
    await expect(dismissBtn).toBeVisible();
    await dismissBtn.click();
    // Alert should be removed from the visible list (is_dismissed=true)
    await expect(fdaNdcAlert).not.toBeVisible({ timeout: 3_000 });

    // Step 13: Navigate to Audit Log
    await page.goto(`${BASE}/directories/audit`, { waitUntil: "networkidle" });
    await expect(page.locator('[data-testid="audit-log-table"]')).toBeVisible();
  });

  test("Prescriber search → exclusion cross-link", async ({ page }) => {
    await page.goto(`${BASE}/directories`, { waitUntil: "networkidle" });
    await page.keyboard.press("Meta+K");
    await page.keyboard.type("Dr. Jane");
    const result = page.locator('[data-testid="search-result-item"][data-dataset="nppes"]').first();
    await expect(result).toBeVisible({ timeout: 5_000 });
    await result.click();
    await page.waitForURL(/\/directories\/prescribers\//, { timeout: 10_000 });
    // ExclusionAlertBadge should appear (fixture prescriber is in exclusions)
    await expect(page.locator('[data-testid="exclusion-alert-badge"]')).toBeVisible();
  });

  test("BPG surface shows Live API label — no trigger button", async ({ page }) => {
    await page.goto(`${BASE}/directories/pricing`, { waitUntil: "networkidle" });
    await page.locator('[role="tab"]', { hasText: "BPG" }).click();
    await expect(page.locator('[data-testid="bpg-live-api-label"]')).toContainText("Live API — no ingestion schedule");
    await expect(page.locator('[data-testid="trigger-refresh-btn"][data-source="bpg"]')).not.toBeVisible();
  });

  test("Ingestion console: BPG row has no trigger, FDB row shows B9 pending", async ({ page }) => {
    await page.goto(`${BASE}/directories/ingestion`, { waitUntil: "networkidle" });
    // BPG: "Live API — no schedule" label, no trigger button
    await expect(page.locator('[data-testid="ingestion-row-bpg"]')).not.toBeVisible();
    // FDB: "Pending B9" status
    const fdbRow = page.locator('[data-testid="ingestion-row-fdb"]');
    await expect(fdbRow).toBeVisible();
    await expect(fdbRow).toContainText("Pending B9");
    await expect(fdbRow.locator('[data-testid="trigger-refresh-btn"]')).not.toBeVisible();
  });
});
```

---

## QA harness additions (`packages/qa-harness/`)

### D-E1 — Directories fixture seed hook

```typescript
// packages/qa-harness/src/seeds/directories-seed.ts
// Seed helper for the directories module QA harness.
// Calls the ingestion router's test-seed endpoint (if wired) or
// directly seeds via the prescriber-directory's /seed endpoint.
//
// Execution-time: verify whether prescriber-directory has a /seed endpoint.
// grep -n "seed\|fixture" modules/prescriber-directory/src/main.py
// If absent, seeding is done via direct DB insert in integration test fixtures
// (SQLAlchemy, following the SAVEPOINT pattern from LESSON-001).
export async function seedDirectoriesFixtures(baseUrl: string): Promise<void> {
  // Load prescribers.json, pharmacies.json, drugs-fda-ndc.json, ingestion-runs.json
  // POST each to the appropriate module's seed endpoint
}

export async function teardownDirectoriesFixtures(baseUrl: string): Promise<void> {
  // Cleanup seeded fixture data
}
```

### D-E2 — QA harness directories composition viewer

```typescript
// packages/qa-harness/src/composition-viewer.tsx — add directories module entry
// Shows the directories module state in the QA harness panel:
// - Number of loaded sources (from quality dashboard)
// - Number of active alerts
// - Last ingestion run timestamp per source
```

---

## Tasks

### Task E-1: Synthetic fixtures

**Files to create (all in `packages/modules/directories/fixtures/`):**
- `prescribers.json` — 10 NPPES-shaped records; Luhn-valid NPIs (prefix 80840);
  one NPI also present in `exclusions-sam.json` for cross-link test
- `pharmacies.json` — 10 NCPDP-shaped records (invented NABP, real-city addresses)
- `drugs-fda-ndc.json` — 10 records using real public NDCs (public data, non-PHI)
- `drugs-fdb-mock.json` — 10 records with `_mock: true`, `b9_blocked: true`
- `codes-hcpcs.json` — 10 real HCPCS codes (J0135, J3490, etc.)
- `codes-icd10.json` — 10 real ICD-10-CM codes (Z87.891, E11.9, etc.)
- `pricing-cms-asp.json` — 5 CMS-ASP pricing records
- `pricing-cms-nadac.json` — 5 NADAC pricing records
- `exclusions-ofac.json` — 5 OFAC SDN records (real names from public `data/reference/ofac-sdn/`)
- `exclusions-sam.json` — 5 SAM records; one entry name matches a fixture prescriber
- `ingestion-runs.json` — per schema above (completed nppes, failed fda_ndc, running ncpdp)
- `ingestion-schedules.json` — one ScheduleEntry per triggerable source key

**Verification:** Each fixture file must be valid JSON. Lint with `JSON.parse()` in test.

### Task E-2: Search relevance regression tests

**File:** `packages/modules/directories/tests/unit/search-relevance.test.ts` — per spec above.

**Coverage gate:** 100% on `rankResults.ts` (pure function; 100% is achievable and required
for this security-adjacent ranking function). The relevance tests cover all 4 ranking tiers.

### Task E-3: Integration tests

**Files to create:**
- `packages/modules/directories/tests/integration/bff-fan-out.test.ts`
- `packages/modules/directories/tests/integration/ingestion-trigger-idempotency.test.ts`

**Note on SQLite UUID compatibility (LESSON-007):** Integration tests that seed
`IngestionRun` rows with UUID columns use SQLite (via prescriber-directory test
conftest). Must apply `_UUIDString` TypeDecorator per `.claude/rules/testing.md`
LESSON-007 pattern to avoid `AttributeError: 'float' object has no attribute 'replace'`.

**Execution-time verification:** `grep -n "_UUIDString\|PG_UUID\|LESSON-007" modules/prescriber-directory/tests/conftest.py`
to check if the conftest already has the `_UUIDString` fix, since prescriber-directory
will now host the ingestion router. Apply if missing.

### Task E-4: E2E spec

**File:** `portal/operator/tests/e2e/sp2-directories-round-trip.spec.ts` — per spec above.

**`data-testid` attributes required (implementing agent wires these in Plans B/C/D):**
- `search-result-group-{cluster}` on CommandPalette group headers
- `search-result-item` on each result row; `data-dataset` attribute
- `provenance-badge` on ProvenanceBadge component
- `freshness-chip` on FreshnessChip component
- `b9-pending-banner` on B9PendingBanner component
- `ingestion-console-title` on IngestionConsolePage heading
- `ingestion-row-{source}` on each IngestionConsolePage row
- `trigger-refresh-btn` on TriggerRefreshButton; `data-source` attribute
- `run-progress-bar` on RunProgressBar
- `run-complete-delta` on completion delta display
- `quality-dashboard-panel` on QualityDashboardPanel
- `ingestion-alert-{source}` on IngestionAlertList row
- `dismiss-alert-btn` on DismissAlertAction button
- `audit-log-table` on AuditLogPage table
- `exclusion-alert-badge` on ExclusionAlertBadge
- `bpg-live-api-label` on BPG pricing label
- `run-history-drawer` on RunHistoryDrawer

**Failing fast:** If `E2E_STACK_READY` is not set, all tests in the spec are
skipped via `test.skip(!E2E_READY, ...)`. The spec must still be importable
without error in CI environments without the full stack.

### Task E-5: QA harness additions

**File:** `packages/qa-harness/src/seeds/directories-seed.ts` — seed helper per D-E1.

**Execution-time verification before writing:** `grep -n "seed\|fixture\|/seed" modules/prescriber-directory/src/main.py`
to determine if prescriber-directory has a seed endpoint. If not, implement seeding
via direct ORM inserts in the integration test conftest instead.

### Task E-6: `data-testid` audit pass (retrospective wiring)

After Plans B/C/D are implemented, do a targeted pass to ensure every component
referenced in the E2E spec has its `data-testid` attribute wired. This is a
SINGLE task, not per-component — it is done once after all components exist.

---

## Testing requirements (Plan E total)

| Test file | What | Coverage target |
|---|---|---|
| `tests/unit/search-relevance.test.ts` | All 4 ranking tiers, all spec §9.4 queries | 100% on `rankResults.ts` |
| `tests/unit/fixtures-valid.test.ts` | All 12 fixture JSON files parse without error | N/A (pure data validation) |
| `tests/integration/bff-fan-out.test.ts` | All 6 fan-out scenarios | 99% |
| `tests/integration/ingestion-trigger-idempotency.test.ts` | 5 idempotency scenarios | 99% |
| `portal/operator/tests/e2e/sp2-directories-round-trip.spec.ts` | 4 E2E scenarios (gated by `E2E_STACK_READY`) | N/A (E2E; coverage measured separately) |

---

## Coverage summary — all 5 plans

Consolidated gate that must pass before the coordinator merges SP-2:

| Path / module | Gate |
|---|---|
| `packages/modules/directories/src/search/rankResults.ts` | 100% |
| `packages/modules/directories/src/search/schemas.ts` | 100% |
| `packages/modules/directories/src/bff/search.ts` (auth lines) | 100% |
| `packages/modules/directories/src/bff/ingest.ts` (auth + SSRF guard) | 100% |
| `packages/modules/directories/src/bff/quality.ts` (auth + x-tenant-id) | 100% |
| `packages/modules/directories/src/bff/audit.ts` (auth lines) | 100% |
| `modules/prescriber-directory/src/main.py` (`_ingestion_db_override`) | 100% |
| All other active SP-2 code | 99% branch coverage |
| B9-mocked stubs | Smoke test only (excluded from branch coverage) |

---

## Verified citations (pre-write grep results)

| Symbol / Path | Verification |
|---|---|
| `portal/operator/tests/e2e/sp1-paysync-round-trip.spec.ts:27` | `E2E_STACK_READY` pattern |
| `portal/operator/tests/fixtures/mock-session.ts:30` | `authenticateDevBypass` signature |
| `portal/operator/tests/e2e/directories/directories-detail.spec.ts` | Existing directories E2E; `drillToFirstRow` helper |
| `packages/modules/paysync/fixtures/seeds/` | Fixture seed pattern (template) |
| `packages/qa-harness/src/seeds/` | QA harness seeds location |
| `packages/qa-harness/src/index.ts` | QA harness public surface |
| `shared/data_ingestion/api/schemas.py:60` | `completed_at` (NOT `finished_at`) in RunSummary |
| `.claude/rules/testing.md` (LESSON-007) | `_UUIDString` TypeDecorator for UUID columns in SQLite |
| `.claude/rules/security.md` | NPI Luhn check prefix 80840 |
| `data/reference/ofac-sdn/` | OFAC reference data dir (confirmed at HEAD) |
| `data/reference/sam_exclusions/` | SAM reference data dir (confirmed at HEAD) |

---

## Out of scope for Plan E

- Backend ingestion audit event writing (already noted in Plan D)
- Excel/PDF report rendering (deferred per CLAUDE.md module status table)
- Graph analysis batch job (deferred)
- 250K claim demo scaling (deferred — production hardening separate wave)
- Full async session migration (deferred — separate wave)
