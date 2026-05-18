# SP-2 Plan C — Ingestion Console, Ingestion Router Mount, Scheduled-Job UI

**Status:** DRAFT  
**Date:** 2026-05-17  
**Vertical:** SP-2 Directories Portal / Reference Data Control Plane  
**Spec ref:** `docs/superpowers/specs/2026-05-16-sp2-directories-portal-design.md` §6.4, §5.4, §5.5  
**Depends on:** Plan A (BFF search route, auth pattern), Plan B (FreshnessChip, ProvenanceBadge)  

---

## Purpose

Plan C delivers two things:

1. **Backend:** Mount the shared ingestion router
   (`shared/data_ingestion/api/routes.py`) in `prescriber-directory`'s
   `create_app()` — the confirmed host module (port 8010). Without this,
   BFF calls to `POST /api/v1/data-ingestion/{source}/trigger` return
   connection-refused.

2. **Frontend:** The ingestion console UI — `IngestionConsolePage`,
   `RunHistoryDrawer`, `TriggerRefreshButton`, `RunProgressBar` — wired
   through BFF proxy routes to the now-mounted shared ingestion API.

---

## Verified facts (pre-write grep confirmed)

| Fact | Verification |
|---|---|
| `shared/data_ingestion/api/routes.py` router variable | `router = APIRouter(tags=["data-ingestion"])` (line 42) |
| Router DB dependency | `_get_db(request: Request)` (line 50) — reads `request.state.db`; raises HTTP 500 if None |
| Router correlation_id dependency | `_correlation_id(request: Request)` (line 58) — reads `request.state.correlation_id` |
| Test pattern for mount | `shared/data_ingestion/tests/test_api_routes.py:28-44` — `_make_app` uses `app.dependency_overrides[_get_db]` to inject session |
| Mount docstring | `routes.py:5-6` — `app.include_router(ingestion_router, prefix="/api/v1/data-ingestion")` |
| No current mount | `grep -rn "ingestion_router\|from shared.data_ingestion.api" modules` → zero results |
| prescriber-directory `create_app()` | `modules/prescriber-directory/src/main.py:67` |
| prescriber-directory session factory | `modules/prescriber-directory/src/db/session.py:58` — `get_db_session()` returns `Iterator[Session]` |
| 409 check line | `shared/data_ingestion/api/routes.py:158-169` — in-flight run guard |
| `POST trigger` function | `routes.py:127-197` — `@router.post(...)` → `async def trigger_run(...)` at line 132 |
| `GET status` (all sources) | `routes.py:260-293` → `async def get_all_status()` |
| `GET history` | `routes.py:295-332` → `async def get_source_history()` |
| `GET runs/{run_id}` | `routes.py:333-357` → `async def get_run_detail()` |
| `POST cancel` | `routes.py:355-400` → `async def cancel_run()` |

---

## Part 1 — Backend: Mount shared ingestion router in prescriber-directory

### Why prescriber-directory

The shared ingestion router manages reference-data loads across all directory
modules (prescribers, pharmacies, drugs, codes, pricing, exclusions). It has
no module-specific dependencies — it reads `IngestionRun` and
`IngestionSchedule` from the shared schema, which `prescriber-directory`
already has access to (it uses the shared DB session factory with
`install_tenant_loader`). prescriber-directory runs on port 8010
(confirmed from `portal/shared/lib/constants.ts:19-20`), is already listed
in the operator portal as a backend dependency, and is the natural "directories
coordinator" module. No new module is needed.

Alternative rejected: creating a standalone ingestion-api microservice is
over-engineering for SP-2 (YAGNI per CLAUDE.md principle 6).

### DB session bridging

The ingestion router's `_get_db` reads `request.state.db`. The prescriber-
directory's own routes use a Depends-injection pattern (`get_db_session()`),
not middleware that sets `request.state.db`. The mount requires a one-time
`dependency_overrides` registration in `create_app()`:

```python
# In modules/prescriber-directory/src/main.py — within create_app()
from shared.data_ingestion.api.routes import router as ingestion_router, _get_db
from shared.data_ingestion.api.routes import _correlation_id as _ingestion_correlation_id
from src.db.session import get_db_session
import uuid

def _ingestion_db_override(request: Request) -> Session:
    """Bridge prescriber-directory's session factory to ingestion router's request.state.db."""
    with get_db_session() as session:
        request.state.db = session
        request.state.correlation_id = getattr(
            request.state, "correlation_id", str(uuid.uuid4())
        )
        return session

app.include_router(ingestion_router, prefix="/api/v1/data-ingestion")
app.dependency_overrides[_get_db] = _ingestion_db_override
```

**Surgical scope:** Only the two lines `include_router` + `dependency_overrides`
and the helper function `_ingestion_db_override` are added to `create_app()`.
No other changes to `prescriber-directory/src/main.py`.

### Integration test (LESSON-006 compliance)

LESSON-006: every router/middleware primitive MUST have an integration test
through `create_app()`. This test goes in the prescriber-directory test suite.

**File:** `modules/prescriber-directory/tests/test_ingestion_mount.py`

```python
"""Integration test: shared ingestion router mounted on prescriber-directory's create_app().

Verifies LESSON-006: the router is reachable through the app factory, not just
in isolation. Tests the full HTTP path from TestClient → create_app() →
ingestion router → DB session.
"""
import pytest
from fastapi.testclient import TestClient
from src.main import create_app

@pytest.fixture()
def client(db):
    """TestClient wired to create_app() with shared test DB session."""
    app = create_app()
    # Redirect ingestion router's _get_db to the test session (same pattern as
    # shared/data_ingestion/tests/test_api_routes.py:43)
    from shared.data_ingestion.api.routes import _get_db
    from fastapi import Request

    def _override(request: Request):
        request.state.db = db
        return db

    app.dependency_overrides[_get_db] = _override
    return TestClient(app)

def test_ingestion_status_reachable(client):
    """GET /api/v1/data-ingestion/status returns 200 through prescriber-directory app."""
    resp = client.get("/api/v1/data-ingestion/status")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_ingestion_trigger_unknown_source_404(client):
    """POST /api/v1/data-ingestion/unknown_source/trigger returns 404."""
    resp = client.post("/api/v1/data-ingestion/unknown_source/trigger", json={"run_type": "full"})
    assert resp.status_code == 404

def test_ingestion_trigger_duplicate_409(client, db):
    """POST trigger while run is already running → 409."""
    from shared.data_ingestion.models import IngestionRun, IngestionSchedule
    from datetime import UTC, datetime
    import uuid
    # Seed a running run for fda_ndc
    sched = IngestionSchedule(source="fda_ndc", cron_expression="0 2 * * *", enabled=True)
    db.add(sched)
    run = IngestionRun(
        id=uuid.uuid4(), source="fda_ndc", status="running",
        started_at=datetime.now(UTC),
    )
    db.add(run)
    db.commit()
    resp = client.post("/api/v1/data-ingestion/fda_ndc/trigger", json={"run_type": "full"})
    assert resp.status_code == 409

def test_ingestion_no_auth_still_works(client):
    """Ingestion router has no auth dependency (backend is unauthed; BFF is the auth gate).
    Verify a call without Authorization header still reaches the router (returns non-401).
    """
    resp = client.get("/api/v1/data-ingestion/status")
    assert resp.status_code != 401  # 200 or empty list, never 401
```

**Coverage gate:** 100% on the `_ingestion_db_override` helper (auth-adjacent
bridging code). 99% overall on this test file.

---

## Part 2 — Frontend: Ingestion console UI

### D-C1 — BFF proxy routes (`src/bff/ingest.ts`)

These proxy the shared ingestion API. All authenticate JWT via `verifyAccessToken`
from `@infinityrx/auth` (same pattern as Plan A `bff/search.ts`). No role check (D7).

```typescript
// src/bff/ingest.ts
// BFF routes for the ingestion console.
// POST /api/directories/ingest/[source]/trigger  → proxies to shared ingestion API
// GET  /api/directories/ingest/[source]/history  → proxies history endpoint
// GET  /api/directories/ingest/runs/[run_id]     → proxies run detail (polling)
// POST /api/directories/ingest/[source]/cancel   → proxies cancel

const INGESTION_BASE =
  process.env.PRESCRIBER_DIRECTORY_URL ?? "http://prescriber-directory:8010";
```

**BFF route handlers:**

| BFF route | Backend call | Spec ref |
|---|---|---|
| `POST /api/directories/ingest/{source}/trigger` | `POST http://prescriber-directory:8010/api/v1/data-ingestion/{source}/trigger` (routes.py:127) | spec §7.2 step 4 |
| `GET /api/directories/ingest/{source}/history` | `GET .../api/v1/data-ingestion/{source}/history` (routes.py:295) | spec §6.4 |
| `GET /api/directories/ingest/runs/{run_id}` | `GET .../api/v1/data-ingestion/runs/{run_id}` (routes.py:333) | spec §7.2 step 8 |
| `POST /api/directories/ingest/{source}/cancel` | `POST .../api/v1/data-ingestion/{source}/cancel` (routes.py:355) | spec §6.4 |

**Source validation in BFF:** Before proxying, validate `source` against the
known source keys from Plan A's `DatasetKeySchema`. If source is not in the
allowed set, return 404 to prevent SSRF (structural injection via `source`
path parameter).

```typescript
// Allowed source keys — only these can be triggered via BFF
const TRIGGERABLE_SOURCES = new Set([
  "nppes", "nppes_monthly", "nppes_deactivation",
  "ncpdp", "fda_ndc", "fda_orange_book", "fda_purple_book",
  "fda_drug_shortages", "fda_rems", "rxnorm",
  "hcpcs", "icd10_cm",
  "cms_asp", "cms_nadac", "state_medicaid_bins",
  "cms_opt_out", "ofac_sdn", "sam_exclusions",
  "oig_leie", "dea_registrations",
] as const);
// Note: "bpg", "fdb", "relay-health" are intentionally excluded.
// bpg = live external API, no trigger. fdb = B9-blocked. relay-health = not a loader.
```

### D-C2 — `IngestionConsolePage` (`src/ingestion/IngestionConsolePage.tsx`)

Table of all registered sources. Data source: BFF `GET /api/directories/quality`
(Plan D, but Plan C stubs it with a local fetch to
`GET /api/v1/data-ingestion/status` proxied through a minimal quality BFF stub).

| Column | Source |
|---|---|
| Source | Source key string |
| Cluster | Mapped from source key (Prescribers / Pharmacies / Drugs / Codes / Pricing / Exclusions) |
| Last Run | `last_run.started_at` from `SourceStatus` |
| Status | `last_run.status` (completed / failed / running / skipped_unchanged) |
| Records | `last_run.records_inserted + records_updated` |
| Errors | `last_run.records_errored` (orange badge when > 0) |
| Next Scheduled | From `IngestionSchedule.cron_expression` (human-readable, e.g., "Daily 2 AM") |
| Actions | `TriggerRefreshButton` + "View history" → `RunHistoryDrawer` |

**Rows for no-loader sources:**
- `bpg`: "Live API — no schedule" in Status column; no trigger button; no history link
- `fdb`: "Pending B9" in Status; no trigger; no history
- relay-health: NOT shown (not a loader, not in scope)

### D-C3 — `TriggerRefreshButton` (`src/ingestion/TriggerRefreshButton.tsx`)

```typescript
interface TriggerRefreshButtonProps {
  source: string;          // must be in TRIGGERABLE_SOURCES
  onRunStarted: (runId: string) => void;
  disabled?: boolean;      // set true during in-flight run
}
```

Behavior:
1. `POST /api/directories/ingest/{source}/trigger` (body: `{run_type:"full"}`)
2. On 200: extract `run_id`; call `onRunStarted(run_id)`; show spinner
3. On 409: show toast "A refresh is already running for {source}. View its progress."
4. On 404: show toast with correlation_id "Source not found. Check ingestion console."
5. On error: show error toast with correlation_id

```typescript
// Toast uses portal's existing toast mechanism (check portal/operator for toast library)
// Execution-time verification: grep -rn "toast\|useToast\|Toaster" portal/operator/app
// before implementing to find the correct import path.
```

### D-C4 — `RunProgressBar` (`src/ingestion/RunProgressBar.tsx`)

Live progress bar for an in-flight run. Polls BFF every 5 seconds until
`status !== 'running'`.

```typescript
interface RunProgressBarProps {
  runId: string;
  source: string;
  onComplete: (result: RunDetail) => void;
}
// Polls GET /api/directories/ingest/runs/{runId} every 5s
// Renders: records_processed / records_in_source (if known) progress bar
// On complete: calls onComplete(result) — parent updates QualityDashboard tag
// On failed: shows error toast with error_message + correlation_id
```

### D-C5 — `RunHistoryDrawer` (`src/ingestion/RunHistoryDrawer.tsx`)

Slide-in drawer showing run history for a single source.

```typescript
interface RunHistoryDrawerProps {
  source: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}
// Fetches GET /api/directories/ingest/{source}/history
// Columns: Run ID (short), Status, Started, Duration, Records Inserted,
//          Records Updated, Records Errored, Trigger (system/manual)
// Error rows are highlighted red
// Each row: "View run" link opens minimal run detail panel
```

### D-C6 — Scheduled-job UI additions to `IngestionConsolePage`

Per spec §6.4: the ingestion console shows `next_scheduled_run_time` from
`IngestionSchedule.cron_expression`. Human-readable cron descriptions:

```typescript
// Cron to human-readable description — pure function, unit-tested
// Uses known DEFAULT_SCHEDULES patterns (no arbitrary cron parsing needed)
const SCHEDULE_LABELS: Record<string, string> = {
  "0 2 * * *": "Daily 2:00 AM",
  "0 3 * * 1": "Weekly Mon 3:00 AM",
  "0 4 1 * *": "Monthly 1st 4:00 AM",
  "0 3 * * 2": "Weekly Tue 3:00 AM",
  "0 4 15 * *": "Monthly 15th 4:00 AM",
  "0 5 15 * *": "Monthly 15th 5:00 AM",
  "0 4 1 1,4,7,10 *": "Quarterly 1st 4:00 AM",
  "0 1 1-7 * 1": "First Mon of month 1:00 AM",
  "0 5 * * 3": "Weekly Wed 5:00 AM",
  "0 6 * * *": "Daily 6:00 AM",
  "0 2 20 * *": "Monthly 20th 2:00 AM",
  "0 6 1 * *": "Monthly 1st 6:00 AM",
  "0 3 20 * *": "Monthly 20th 3:00 AM",
  "0 2 15 4,10 *": "Apr/Oct 15th 2:00 AM",
  "0 3 15 1,4,7,10 *": "Quarterly 15th 3:00 AM",
};
// null cron = "Manual only"
```

Cron labels verified against `shared/data_ingestion/scheduler.py:27-52`
(DEFAULT_SCHEDULES dict, confirmed at HEAD).

---

## Tasks

### Task C-1: Mount ingestion router in prescriber-directory

**File to modify:** `modules/prescriber-directory/src/main.py`

Surgical changes only:
1. Add import: `from shared.data_ingestion.api.routes import router as ingestion_router, _get_db as _ingestion_get_db`
2. Add import: `from fastapi import Request` (if not already imported; check HEAD)
3. Add `_ingestion_db_override` helper function (per Part 1 above)
4. Inside `create_app()`, after `app.include_router(router)` (line 97), add:
   ```python
   app.include_router(ingestion_router, prefix="/api/v1/data-ingestion")
   app.dependency_overrides[_ingestion_get_db] = _ingestion_db_override
   ```

**Execution-time verification before writing:**
- `grep -n "^from fastapi\|^import fastapi\|^from fastapi import" modules/prescriber-directory/src/main.py`
  to check if `Request` is already imported.

**File to create:** `modules/prescriber-directory/tests/test_ingestion_mount.py` (per Part 1).

**Coverage gate:** 100% on `_ingestion_db_override` (the bridge between
prescriber-directory's session factory and the ingestion router's `request.state.db`).
This is security-adjacent code (it gates DB access for the ingestion API).

### Task C-2: BFF ingest proxy routes

**File:** `packages/modules/directories/src/bff/ingest.ts` — implement all 4 BFF
proxy routes with `TRIGGERABLE_SOURCES` allowlist and JWT auth.

**Tests:** `packages/modules/directories/tests/unit/bff-ingest.test.ts`:
- `POST .../trigger` with source not in `TRIGGERABLE_SOURCES` → 404 (SSRF guard)
- `POST .../trigger` without JWT → 401
- `POST .../trigger` with valid JWT + valid source → proxies to backend (mocked fetch)
- `POST .../trigger` with backend returning 409 → passes 409 through
- `GET .../history` without JWT → 401
- `GET .../runs/{run_id}` without JWT → 401
- `POST .../cancel` for non-triggerable source → 404

**Coverage gate:** 100% on auth validation + SSRF guard (source allowlist check).
99% overall.

### Task C-3: Ingestion console components

**Files to create:**
- `packages/modules/directories/src/ingestion/IngestionConsolePage.tsx`
- `packages/modules/directories/src/ingestion/TriggerRefreshButton.tsx`
- `packages/modules/directories/src/ingestion/RunProgressBar.tsx`
- `packages/modules/directories/src/ingestion/RunHistoryDrawer.tsx`
- `packages/modules/directories/src/ingestion/scheduleLabels.ts`
- `packages/modules/directories/src/ingestion/index.ts`

**Tests:**
- `tests/unit/ingestion/IngestionConsolePage.test.tsx`:
  - Table renders one row per source key (18 rows — 15 loaders + rxnorm + oig_leie + dea_registrations)
  - BPG row shows "Live API — no schedule"; no trigger button present in that row
  - FDB row shows "Pending B9"; no trigger button
  - relay-health does NOT appear in the table
  - Source with `records_errored > 0` shows orange badge
- `tests/unit/ingestion/TriggerRefreshButton.test.tsx`:
  - Click → POST fires; spinner appears
  - 409 response → correct toast message
  - 404 response → toast with correlation_id
  - Button is disabled when `disabled=true`
- `tests/unit/ingestion/RunProgressBar.test.tsx`:
  - Polls every 5s (mock timers)
  - Shows `records_processed / records_in_source`
  - `status = 'completed'` → calls `onComplete`
  - `status = 'failed'` → error toast
- `tests/unit/ingestion/scheduleLabels.test.ts`:
  - All 15 DEFAULT_SCHEDULE cron expressions map to non-empty human-readable strings
  - `null` cron → "Manual only"

### Task C-4: Source barrel update

**File:** `packages/modules/directories/src/ingestion/index.ts` — exports all ingestion components.

**File:** `packages/modules/directories/src/index.ts` — add ingestion exports.

---

## Testing requirements (Plan C total)

| Test file | What | Coverage target |
|---|---|---|
| `modules/prescriber-directory/tests/test_ingestion_mount.py` | mount + 409 + 404 + no-auth passthrough | 100% on bridge function; 99% overall |
| `tests/unit/bff-ingest.test.ts` | auth guard + SSRF allowlist + proxy | 100% auth + SSRF; 99% overall |
| `tests/unit/ingestion/IngestionConsolePage.test.tsx` | table rows, BPG/FDB treatment | 99% |
| `tests/unit/ingestion/TriggerRefreshButton.test.tsx` | click flow, 409, 404 | 99% |
| `tests/unit/ingestion/RunProgressBar.test.tsx` | poll + complete + fail | 99% |
| `tests/unit/ingestion/scheduleLabels.test.ts` | all 15 cron → label; null → manual | 100% (pure function, trivially achievable) |

---

## Ingestion console data model (from spec §6.4)

BFF `GET /api/directories/quality` (Plan D) will be the primary data source.
In Plan C, `IngestionConsolePage` uses a stub `GET /api/directories/ingest/status`
that proxies directly to `GET /api/v1/data-ingestion/status` (routes.py:260).

The `SourceStatus` schema from `shared/data_ingestion/api/schemas.py`:

```typescript
// Mirrored from shared/data_ingestion/api/schemas.py (verified against HEAD)
// RunSummary fields confirmed at schemas.py:47-62; SourceStatus at schemas.py:81-89.
interface SourceStatus {
  source: string;
  cron_expression: string | null;  // top-level on SourceStatus, NOT nested in schedule
  enabled: boolean;
  last_success_at: string | null;
  next_run_at: string | null;
  last_run: {
    id: string;
    source: string;
    run_type: string;
    status: "running" | "completed" | "completed_core" | "failed" | "skipped_unchanged";
    records_processed: number;
    records_inserted: number;
    records_updated: number;
    records_skipped: number;
    records_errored: number;
    started_at: string;
    completed_at: string | null;   // NOT "finished_at" — verified: schemas.py:60
    duration_seconds: number | null;
    error_message: string | null;
  } | null;
}
```

**CORRECTION (codex r1 BLOCK):** The original interface had `finished_at` — this field does NOT
exist. The actual field is `completed_at` (confirmed at `shared/data_ingestion/api/schemas.py:60`).
The SourceStatus structure was also corrected: `cron_expression`, `enabled`, `last_success_at`,
and `next_run_at` are top-level fields on SourceStatus, not nested in a `schedule` sub-object.
Implementing agents MUST use `completed_at`.

---

## PHI and security posture

- Ingestion data (run records, schedules, error messages) is non-PHI: it is
  operational metadata about reference data loads.
- No `PHIMixin`, `EncryptedString`, or `Cache-Control: no-store` needed.
- The `_ingestion_db_override` bridge does NOT apply `install_tenant_loader` —
  the shared schema is not tenant-scoped. This is correct behavior (verified:
  `IngestionRun` and `IngestionSchedule` use the `shared` schema, not a
  tenant-scoped schema).
- BFF `TRIGGERABLE_SOURCES` allowlist prevents SSRF via path injection into
  the `{source}` parameter. This is a security control and requires 100% test coverage.

---

## Verified citations (pre-write grep results)

| Symbol / Path | Verification |
|---|---|
| `shared/data_ingestion/api/routes.py:42` | `router = APIRouter(tags=["data-ingestion"])` |
| `shared/data_ingestion/api/routes.py:50-55` | `_get_db` reads `request.state.db`, raises HTTP 500 if None |
| `shared/data_ingestion/api/routes.py:127` | `@router.post(...)` for trigger |
| `shared/data_ingestion/api/routes.py:132` | `async def trigger_run(...)` |
| `shared/data_ingestion/api/routes.py:158-169` | 409 in-flight guard |
| `shared/data_ingestion/api/routes.py:260` | `@router.get(...)` for all-status |
| `shared/data_ingestion/api/routes.py:265` | `async def get_all_status()` |
| `shared/data_ingestion/api/routes.py:295` | `@router.get(...)` for history |
| `shared/data_ingestion/api/routes.py:300` | `async def get_source_history()` |
| `shared/data_ingestion/api/routes.py:333` | `@router.get(...)` for run detail |
| `shared/data_ingestion/api/routes.py:338` | `async def get_run_detail()` |
| `shared/data_ingestion/api/routes.py:355` | `@router.post(...)` for cancel |
| `shared/data_ingestion/api/routes.py:360` | `async def cancel_run()` |
| `shared/data_ingestion/tests/test_api_routes.py:28-44` | `_make_app` — dependency_overrides pattern confirmed |
| `modules/prescriber-directory/src/main.py:67` | `def create_app()` |
| `modules/prescriber-directory/src/main.py:97` | `app.include_router(router)` |
| `modules/prescriber-directory/src/db/session.py:58` | `def get_db_session() -> Iterator[Session]` |
| `shared/data_ingestion/scheduler.py:27-52` | `DEFAULT_SCHEDULES` — all cron expressions verified |
| `portal/shared/lib/constants.ts:17-22` | `prescriberDirectory: :8010` (ingestion host port) |

---

## Out of scope for Plan C

- Data-quality dashboard (Plan D) — `GET /api/directories/quality` aggregation
- Audit log viewer (Plan D)
- E2E fixtures and round-trip tests (Plan E)
- Alert dismissal Redis key writes (Plan D owns `DismissAlertAction`)
