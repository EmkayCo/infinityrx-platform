# P0a Exclusion Screening — Discovery Report

**Date**: 2026-05-15
**Branch**: wave/B10-w5-p0a-exclusion-screening
**Items**: MISSING-LOADER-10 (aggregator), LOADER-BUG-07a (SAM URL)

---

## 1. Table Locations

| Table | File | Schema | Notes |
|---|---|---|---|
| `core.exclusion_list` | `shared/db/models/core.py` (`ExclusionList`) | `core` | Global reference data — no `TenantScopedMixin`. Source CHECK constraint: `IN ('OIG', 'SAM')` |
| `core.exclusion_matches` | `shared/db/models/core.py` (`ExclusionMatch`) | `core` | Tenant-scoped match results |
| `core_exclusion_list` | `modules/core-platform/src/models.py` (`ExclusionListEntry`) | SQLite-shim (local) | Used by core-platform service layer and tests. Same columns, no schema prefix (SQLite) |
| `shared.oig_leie_exclusions` | `shared/db/models/oig_leie_exclusions.py` (`OigLeieExclusion`) | `shared` | 82,896 rows loaded by `scripts/load_oig_leie.py` |
| `shared.sam_exclusions` | `shared/db/models/sam_exclusions.py` (`SamExclusion`) | `shared` | 0 rows — blocked by LOADER-BUG-07a |

**Discovery note**: Two ORM representations exist for `exclusion_list`:
- `shared/db/models/core.py::ExclusionList` — production Postgres model with explicit `core` schema
- `modules/core-platform/src/models.py::ExclusionListEntry` — SQLite-shim model for core-platform service layer (`core_exclusion_list` table, no schema)

The aggregator (`aggregate_exclusion_list.py`) writes via the **shim model path** so it is testable and so the existing `ingestion.py`, `matching.py`, and `screening_service.py` services can consume from it without change.

---

## 2. OIG Loader

| Item | Value |
|---|---|
| Script | `scripts/load_oig_leie.py` |
| Ingester | `shared/data_ingestion/sources/oig_leie.py` (`OigLeieIngester`) |
| Target table | `shared.oig_leie_exclusions` |
| Row count (surveyor) | **82,896** rows (monthly LEIE update) |
| Status | Working. Runs via CLI: `python scripts/load_oig_leie.py` |

The OIG pipeline downloads the monthly CSV from `oig.hhs.gov`, upserts into `shared.oig_leie_exclusions`, and cross-references `prescriber_dir.prescribers` + `pharmacy_dir.pharmacies` by NPI. It does **not** write to `core.exclusion_list` — that is the missing aggregation step.

---

## 3. SAM.gov Loader — URL Analysis (LOADER-BUG-07a)

### Current URLs by file

| File | URL / Constant |
|---|---|
| `shared/data_ingestion/sources/sam_exclusions.py` | `_SAM_API_BASE_URL = "https://api.sam.gov/entity-information/v4/exclusions"` (paginated JSON) |
| `scripts/load_sam.py` | `BASE_URL = "https://api.sam.gov/entity-information/v4"` → `EXTRACT_URL = .../exclusions`, `DOWNLOAD_URL = .../download-exclusions` (async extract) |
| `modules/core-platform/src/exclusions/ingestion.py` | `SAMIngestionClient.DEFAULT_URL = "https://api.sam.gov/entity-information/v3/exclusions"` **(STALE — v3)** |
| `modules/core-platform/tests/exclusions/test_ingestion.py` | Mock target: `"https://api.sam.gov/entity-information/v3/exclusions"` **(matches stale URL)** |

### Root cause
`modules/core-platform/src/exclusions/ingestion.py::SAMIngestionClient` was never updated from v3 to v4. The `load_sam.py` script uses the correct v4 async-extract endpoint, but the `SAMIngestionClient` used by the core-platform service layer still has `DEFAULT_URL` pointing at `/entity-information/v3/exclusions` (which returns 404 per the LOADER-BUG-07a symptom log from `tasks/loader-bugs.md`).

### Correct endpoint (v4)
The current SAM.gov API (verified in `scripts/load_sam.py` comments, dated 2026-04-16) is:
- **Paginated JSON**: `https://api.sam.gov/entity-information/v4/exclusions`
- **Async bulk extract**: `https://api.sam.gov/entity-information/v4/exclusions` (submit) + `/entity-information/v4/download-exclusions` (poll/download)

The `SAMIngestionClient` in `ingestion.py` uses the paginated JSON path. The fix is to update `DEFAULT_URL` from `v3` to `v4` and update the test mock URL to match.

---

## 4. Consumer — Adjudication

`modules/adjudication-engine/` is Phase 4, not started (README placeholder only). The current consumer of `core.exclusion_list` / `core_exclusion_list` is within `core-platform` itself:

- `modules/core-platform/src/exclusions/screening_service.py` — `ExclusionScreeningService.screen_entity()` queries `ExclusionListEntry` (the local shim model for `core_exclusion_list`).
- `modules/core-platform/src/exclusions/matching.py` — `ExclusionMatcher` runs exact NPI + fuzzy name matches against `ExclusionListEntry`.

When adjudication-engine is built it will call `ExclusionScreeningService` via API. The aggregator populating `core_exclusion_list` / `core.exclusion_list` is the load-bearing prerequisite.

---

## 5. Summary of Gaps Closed by This Wave

| Gap | File Fixed | Status |
|---|---|---|
| LOADER-BUG-07a — SAM v3→v4 URL | `modules/core-platform/src/exclusions/ingestion.py` | Fix 1 (small) |
| MISSING-LOADER-10 — aggregator | `modules/core-platform/scripts/aggregate_exclusion_list.py` (new) | Fix 2 (bigger) |
| Test mock URL alignment | `modules/core-platform/tests/exclusions/test_ingestion.py` | Part of Fix 1 |

---

## 6. Data Flow After Both Fixes

```
scripts/load_oig_leie.py
  → shared.oig_leie_exclusions (82,896 rows)
                                              \
                                               → [aggregate_exclusion_list.py DAILY]
                                              /      → core.exclusion_list (unified)
scripts/load_sam.py (v4 endpoint)                         → ExclusionScreeningService
  → shared.sam_exclusions (~167k rows)                         → core.exclusion_matches
```

---

## 7. v2 Changes — Codex Gate-Close Findings (P0a v2, 2026-05-15)

Codex pass-1 on v1 identified 3 BLOCKs and 3 CONCERNs after the initial
wave commit. All 6 were addressed in P0a v2.

| Finding | Status | Commit |
|---|---|---|
| BLOCK 1: aggregator wrote to SQLite shim (`core_exclusion_list`) not production `core.exclusion_list`; Date columns used DateTime | CLOSED | `10338d7` |
| BLOCK 2: SAM parser read v3 flat key `exclusionDetails` after URL upgraded to v4; v4 returns nested `excludedEntity` — zero rows ingested | CLOSED | `c928652` |
| BLOCK 3: ExactMatcher + FuzzyMatcher did not filter `reinstate_date IS NULL`; reinstated entities matched and produced false positives | CLOSED | `7c42644` |
| CONCERN 1: delisting guard — `_mark_delisted()` now gates per-source on configurable row-count threshold (`oig_min_rows` / `sam_min_rows`); defaults env-driven (`EXCL_OIG_MIN_ROWS=60000`, `EXCL_SAM_MIN_ROWS=100000`); tests bypass with 0 | CLOSED | `10338d7` |
| CONCERN 2: NULL-NPI name-key rows were duplicated when source later added an NPI; secondary name-key lookup now upgrades existing row | CLOSED | `10338d7` |
| CONCERN 3: `exclusion_refresh` handler existed but was never seeded into `core_jobs` and never imported on startup; `src/jobs/seed.py` + lifespan wiring added | CLOSED | `e4b7b7e` |

**Pre-existing fix also landed**: `test_main_auth_wired.py` patches exited
their `with` block before `TestClient` ran the lifespan; extended to
`ExitStack` pattern so patches persist through the full lifespan. (`7858ac3`)

**Final test count**: 452 passed, 0 failed (full core-platform suite).
**New tests added**: 11 (4 BLOCK-3 matcher, 3 CONCERN-1 guard, 1 CONCERN-2
NPI upgrade, 3 CONCERN-3 seed).
**Branch**: `wave/B10-w5-p0a-exclusion-screening`
