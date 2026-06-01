# ReclaimRx Detection Console — Foundation Slice (Design)

**Date:** 2026-06-01
**Author:** Mike K + Claude
**Parent plan:** `docs/superpowers/plans/2026-05-31-reclaimrx-detection-v2.md` (Phases 6 & 7 are the
designed-but-unbuilt source for this slice; this spec adopts and extends them).
**Branch target:** `feat/reclaimrx-csv-detection` → PR to `module/reclaimrx`.

## Problem

The reclaimrx detection-v2 **engine** (plan Phases 1–4) is built and committed, but there is
**no UI** to view or filter its output. The operator portal's GTN dashboard and Leakage Monitor
render blank because the reclaimrx **REST API does not exist yet** (every `/api/v1/reclaimrx/*`
read endpoint the portal calls returns 404). Operators need to view and filter detection findings,
the rule catalog, detection runs, and run-to-run differences.

## Scope decomposition (full console = 4 surfaces)

| # | Surface | Slice |
|---|---|---|
| 1 | **Anomalies / findings viewer** (filter by rule, severity, entity, $) | **Foundation (this spec)** |
| 2 | **Detection runs list** (status, counts, data_quality) | **Foundation (this spec)** |
| 3 | Rule catalog browser (46 rules, live/deferred, family, params) | Follow-on slice 2 |
| 4 | Compare runs (diff: rules fired ±, new/resolved) | Follow-on slice 3 |

**This spec covers the Foundation slice only** (surfaces 1 + 2 + their API + seeded data).
Surfaces 3 and 4 get their own spec→plan→build cycles after this lands. Build order is dependency
driven: the read API and a populated DB unblock everything else.

## Decisions (locked with user, 2026-06-01)

1. **Build foundation first** (Phase 6 API + Anomalies viewer + Runs list), then rule-catalog, then compare-runs.
2. **Data source = synthetic seed + real CLI.** Build a deterministic seed fixture (1 detection run +
   ~50 varied anomalies spanning multiple `finding_code`s/severities/entities) for dev/demo and the
   portal/API tests, AND run the real `python -m src.cli.detect` on the sample CSV once FDW reference
   is available. UI must be usable immediately from the seed; real engine output validates end-to-end.

## Architecture

Three layers, each reusing existing patterns. No new frameworks.

### Layer 1 — Backend read API (`modules/reclaimrx/src/api/router.py`)

Two endpoints, added to the existing `APIRouter` (prefix `/api/v1/reclaimrx`). Reuse the existing
dependencies already used by the FWA routes: `get_db`, `get_current_user`, `require_tenant_match`.
All queries tenant-scoped (`tenant_id == current tenant`). Responses carry `Cache-Control: no-store`
(PHI). Pydantic response models only.

**`GET /anomalies`** — paginated list of `anomalies` rows for the tenant.
- **Server-side filters** (all optional, AND-combined):
  `finding_code` (rule, repeatable), `severity`, `status`, `entity_type`
  (DERIVED: `pharmacy` if `pharmacy_npi IS NOT NULL`; `prescriber` if `prescriber_npi IS NOT NULL
  AND pharmacy_npi IS NULL`; else `unknown`), `pharmacy_npi`, `prescriber_npi`, `ndc`,
  `data_source_run_id`, `min_amount` (vs `amount_paid`), `date_from`/`date_to` (vs `date_of_service`).
- **Pagination:** `page` + `page_size` (default 50, max 200), returns `PaginatedResponse[AnomalyRead]`
  (reuse existing `PaginatedResponse`). Stable sort: `created_at DESC, id`.
- **Name enrichment (set-based, per page):** collect the page's distinct `pharmacy_npi` +
  `prescriber_npi`, run ONE batched query each to `reference.dataq_master` / `reference.prescribers`,
  map names back. Zero per-row queries. Postgres-only — guard like the engine (`_is_postgres`);
  on non-PG/no-FDW, names are null and the list still returns.
- **AnomalyRead fields:** id, finding_code, finding_summary, severity, confidence (str Decimal),
  status, entity_type, pharmacy_npi, pharmacy_name, prescriber_npi, prescriber_name, ndc,
  amount_paid (str), amount_billed (str), recovery_amount (str), date_of_service,
  data_source_run_id, created_at. **No raw PHI** beyond NPIs + names already exposed elsewhere.

**`GET /detection-runs`** — list of `detection_runs` for the tenant (most recent first):
- Fields: id, run_label, status, data_source, source_filename, record_count, anomaly_count,
  period_start/end, started_at, completed_at, failure_reason, `data_quality` (from
  `resolution_stats->'data_quality'`: no_fdb_wac, missing/invalid pharmacy/prescriber npi).
- **`GET /detection-runs/{id}`** — same + **per-rule breakdown**: `[{finding_code, severity, count}]`
  (one GROUP BY over anomalies for that run, tenant-scoped).

### Layer 2 — Portal (`portal/operator`)

- **Adapter (plan Task 7a):** `finding_code → LeakageCategory` mapping table (verbatim from parent
  plan §Phase 7a) + `AnomalyRead → LeakageFlag` adapter at the page boundary. **Do NOT mutate**
  `portal/shared/types/reclaimrx.ts` (World-B types) — add new types, adapt at the edge.
- **Leakage Monitor repoint (Task 7b):** `app/reclaimrx/leakage/page.tsx` `queryFn` → `/anomalies`.
  The page already has `ConfigurableDataTable` + `FilterPanel` + `StatusBadge` + client filtering;
  push filters to the backend query (category→finding_codes, severity, status, entity_type) and add
  a **rule (`finding_code`) filter** to `FILTER_FIELDS`.
- **Runs list page (new, Task 7c):** `app/reclaimrx/runs/page.tsx` → `/detection-runs`, table of runs
  with status, counts, data_quality chips; row → run detail (per-rule breakdown). Add nav entry.
- **Config fix:** correct the stale reclaimrx port in `portal/shared/lib/constants.ts:10`
  (`8003` → `8002`) and the `BACKENDS` map in `portal/operator/lib/bff.ts` (audit all entries vs
  `scripts/start-services/start-all-services.ps1`; reclaimrx is 8002). Latent footgun today.

### Layer 3 — Data seeding

- **Synthetic seed script:** new file `modules/reclaimrx/scripts/seed_detection_demo.py`
  (dedicated, not folded into `scripts/setup_demo.py`) — inserts 1 completed `detection_run` + ~50 `anomalies` across
  ≥6 finding_codes, 4 severities, pharmacy+prescriber entities, varied `amount_paid`, for the
  demo tenant `a0000000-0000-0000-0000-000000000001`. Decimal-only, idempotent.
- **Real CLI run:** document + run `python -m src.cli.detect --file tests/detection/fixtures/sample_claims.csv
  --tenant <demo>` after `infrastructure/scripts/setup_fdw.sh`. Validates the API against real output.

## Data flow

```
detection engine (CLI / consumers) ──► anomalies + detection_runs (infinityrx_dev, reclaimrx schema)
                                            │
            GET /anomalies?finding_code=…   │  (tenant-scoped, set-based name enrichment)
            GET /detection-runs             ▼
portal Leakage Monitor / Runs page ◄── AnomalyRead / DetectionRunRead (Pydantic, no-store)
        │  adapter: AnomalyRead → LeakageFlag (finding_code→category)
        ▼
   ConfigurableDataTable + FilterPanel (existing components)
```

## Testing (TDD, RED first)

- **Backend** `tests/detection/test_anomalies_api.py`, `test_detection_runs_api.py` — through the real
  FastAPI router with `dependency_overrides` (pattern from `tests/integration/test_api_endpoints.py`):
  filter correctness (each filter dimension), pagination bounds, entity_type derivation,
  **cross-tenant isolation on every endpoint** (2 tenants, query A, assert zero B rows),
  PHI `Cache-Control: no-store`, name-enrichment is set-based (query-count assertion), empty-DB returns `[]`.
- **Portal** — adapter unit test (finding_code→category, AnomalyRead→LeakageFlag), filter-pushdown test
  (filter values become query params), Runs page render with seeded data.
- **Coverage:** 100% on the new auth/tenant/PHI paths (auth-gate rule); 95%+ elsewhere.

## Dependencies / prerequisites

1. Phase 6 API must land before any portal page works (backend first).
2. A populated DB (seed script) before the UI shows anything.
3. FDW `reference.*` (setup_fdw.sh) for real-CLI name enrichment + ALL-002/003/FDB rules; the API
   degrades gracefully (null names) without it.
4. reclaimrx service on **8002** (port-map fix).

## Out of scope (this slice)

- Rule catalog browser (slice 2), compare-runs diff (slice 3).
- Anomaly write/triage actions (status changes, case linking) — read-only viewer first.
- GTN dashboard data (`/gtn-summary`, `/gtn-trend`) — separate from findings; not this slice.
- The MFR-003/HP-008 baseline gap (TODO-4c-001) — tracked separately.

## Open follow-ups (tracked, not blocking)

- TODO-4c-001 (MFR-003/HP-008 never fire) — anomalies of those codes will be absent until fixed.
- REJECT-75-70 wiring verification in `run_detection`.
