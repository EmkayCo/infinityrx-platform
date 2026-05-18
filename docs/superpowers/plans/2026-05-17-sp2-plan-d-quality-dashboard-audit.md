# SP-2 Plan D — Data-Quality Dashboard, Audit Log Viewer, Alert Dismissal

**Status:** DRAFT  
**Date:** 2026-05-17  
**Vertical:** SP-2 Directories Portal / Reference Data Control Plane  
**Spec ref:** `docs/superpowers/specs/2026-05-16-sp2-directories-portal-design.md` §6.5, §6.6, §6.7  
**Depends on:** Plan A (BFF auth pattern, search schemas), Plan C (ingestion router mounted, SourceStatus schema)  

---

## Purpose

Plan D delivers the secondary spine of SP-2:

1. **`GET /api/directories/quality` BFF aggregator** — merges `SourceStatus` from all
   sources with per-module stats; returns the `DatasetQuality[]` payload the sidebar uses.
2. **`QualityDashboardPanel`** — sidebar component with `FreshnessChip` per dataset,
   record counts, and `IngestionAlertList` for runs with errors or failures.
3. **`DismissAlertAction`** — marks an alert dismissed in Redis
   (`dir:alert_dismissed:{tid}:{source}`, TTL 24h). No new backend resource needed.
4. **`AuditLogPage`** — read-only viewer of ingestion-related audit events from
   `core-platform` audit log. Filtered to ingestion-action values via
   `GET /api/v1/audit?action=ingestion_run_*&module=shared_ingestion`.
5. **`GET /api/directories/audit` BFF route** — proxies to core-platform's
   `GET /api/v1/audit` with ingestion-action filter pre-applied.

---

## Verified facts (pre-write grep confirmed)

| Fact | Verification |
|---|---|
| `shared/data_ingestion/api/schemas.py:81-89` | `SourceStatus` fields: `source`, `cron_expression`, `enabled`, `last_run: RunSummary | None`, `last_success_at`, `next_run_at` |
| `shared/data_ingestion/api/schemas.py:47-62` | `RunSummary` fields: `id`, `source`, `run_type`, `status`, `records_processed`, `records_inserted`, `records_updated`, `records_skipped`, `records_errored`, `started_at`, `completed_at`, `duration_seconds`, `error_message` |
| `shared/data_ingestion/api/schemas.py:65-78` | `RunDetail` (extends RunSummary): adds `records_in_source`, `error_samples`, `triggered_by`, `created_at`, `source_url`, download/parse/load seconds |
| `shared/data_ingestion/api/routes.py:260` | `GET /api/v1/data-ingestion/status` → `get_all_status()` (no path param, returns all sources) |
| `modules/prescriber-directory/src/api/router.py:381` | `GET /api/v1/prescribers/stats` — no `x-tenant-id` alias (uses `TenantId` dependency) |
| `modules/pharmacy-directory/src/api/router.py:440-442` | `GET /api/v1/pharmacies/stats` — MANDATORY `x-tenant-id: Annotated[uuid.UUID, Query(alias="x-tenant-id")]` |
| `modules/drug-database/src/api/router.py:345` | `GET /api/v1/drugs/refresh/status` → `refresh_status()` |
| `modules/core-platform/src/audit/api.py:4-6` | Audit API: `GET /api/v1/audit` (list), `GET /api/v1/audit/export`, `GET /api/v1/audit/{id}` |
| `modules/core-platform/src/audit/api.py:39-66` | `list_audit` accepts `action`, `module`, `entity_type`, `date_from`, `date_to`, `limit`, `offset` |
| `modules/core-platform/src/api/__init__.py:16,77` | `build_audit_router` is called and mounted as part of `api_router` |
| `packages/auth/src/claims.ts:6-7` | JWT: `sub: z.string().uuid()`, `tid: z.string().uuid()` |
| `portal/shared/lib/constants.ts:6-7` | `corePlatform: process.env.NEXT_PUBLIC_CORE_PLATFORM_URL ?? "http://localhost:8000"` |
| `portal/operator/tests/e2e/sp1-paysync-round-trip.spec.ts:1-30` | E2E pattern: `E2E_STACK_READY` gate, `CORE_BASE_URL` env, Playwright |
| `portal/operator/tests/e2e/directories/directories-detail.spec.ts` | Existing directories E2E file (Plan E extends this) |

---

## Key architectural decision: ingestion audit actions

The shared ingestion router (`shared/data_ingestion/api/routes.py`) does NOT
write to the core-platform audit log — confirmed: zero `AuditMiddleware`,
`AuditService`, or `write_audit` calls in `routes.py`. The core-platform
`AuditMiddleware` runs at the HTTP boundary and captures request actions
generically (not with ingestion-specific action names like
`ingestion_run_started`).

**Plan D decision:** The `AuditLogPage` queries `GET /api/v1/audit` filtered to
`module=shared_ingestion` (the module identifier the audit middleware assigns
when the request passes through prescriber-directory after Plan C mounts the
ingestion router). If no `module=shared_ingestion` entries exist yet (because
the middleware wasn't wiring ingestion calls before Plan C), the audit viewer
shows an empty state with "No ingestion audit events yet — trigger an ingestion
run to see events appear here." This is correct behavior, not an error.

As Plan C's ingestion mount goes live and operators trigger runs, the
AuditMiddleware in prescriber-directory will capture those requests and write
audit entries with `module=prescriber_directory`, `action=POST /api/v1/data-ingestion/{source}/trigger`.
The BFF audit query filters by this path pattern.

**Execution-time refinement:** Before implementing the BFF audit query, run:
`grep -n "module\|action\|entity_type" modules/core-platform/src/audit/middleware.py`
to confirm exactly what `module` and `action` values the AuditMiddleware writes
for ingestion requests. Adjust the BFF filter accordingly.

---

## Part 1 — `GET /api/directories/quality` BFF aggregator

### D-D1 — `DatasetQuality` TypeScript type (add to `src/search/schemas.ts`)

```typescript
// Add to src/search/schemas.ts
export const DatasetQualitySchema = z.object({
  source: DatasetKeySchema,
  last_run_at: z.string().nullable(),           // ISO datetime (RunSummary.started_at)
  last_success_at: z.string().nullable(),        // SourceStatus.last_success_at
  last_run_status: z.enum([
    "completed", "completed_core", "failed", "skipped_unchanged", "running"
  ]).nullable(),
  records_inserted: z.number().nullable(),
  records_errored: z.number().int().nullable(),
  cron_expression: z.string().nullable(),        // null = manual-only
  next_run_at: z.string().nullable(),
  cluster: z.enum(["prescribers","pharmacies","drugs","codes","pricing","exclusions"]),
  is_dismissed: z.boolean().default(false),      // from Redis alert-dismiss key
  no_loader: z.boolean().default(false),         // bpg, fdb — no ingestion trigger
  b9_blocked: z.boolean().default(false),        // fdb only
});
export type DatasetQuality = z.infer<typeof DatasetQualitySchema>;

export const QualityResponseSchema = z.object({
  datasets: z.array(DatasetQualitySchema),
  as_of: z.string(),                             // ISO datetime of the aggregation
});
export type QualityResponse = z.infer<typeof QualityResponseSchema>;
```

### D-D2 — `GET /api/directories/quality` BFF route (`src/bff/quality.ts`)

```typescript
// src/bff/quality.ts
// GET /api/directories/quality
// Aggregates SourceStatus from shared ingestion API + per-module stats.
// Auth: JWT required. No role check (D7).
// Cache: 60s (tag: dir:quality). Invalidated by TanStack Query on ingestion complete.
```

**Aggregation logic:**

```
1. JWT auth via verifyAccessToken (packages/auth) → extract { sub, tid }
2. Parallel fan-out (200ms budget):
   a. GET http://prescriber-directory:8010/api/v1/data-ingestion/status
      → list[SourceStatus] (all sources from shared.ingestion_runs)
   b. GET http://prescriber-directory:8010/api/v1/prescribers/stats
      → { total_prescribers, ... }
   c. GET http://pharmacy-directory:8009/api/v1/pharmacies/stats?x-tenant-id={tid}
      → { total_pharmacies, total_active, total_networks [tenant], pending_credentialing [tenant] }
   d. GET http://drug-database:8011/api/v1/drugs/refresh/status
      → list[RefreshStatusResponse] (per-source refresh state)

3. Merge: For each source key in the authoritative list (18 primary + 3 extra sources,
   minus relay-health which is excluded):
   - Find matching SourceStatus from (a); if absent → no_loader=true
   - Apply cluster mapping (from Plan A's CLUSTER_LABELS equivalent)
   - Apply is_dismissed: check Redis key dir:alert_dismissed:{tid}:{source}
   - Apply b9_blocked for fdb
   - Apply no_loader for bpg, fdb

4. Return QualityResponse:
   { datasets: DatasetQuality[], as_of: <ISO datetime> }

5. Cache at Next.js layer: s-maxage=60, tag: dir:quality
```

**Redis alert-dismiss key read:**
```typescript
// Read Redis key to check if this alert has been dismissed
// Redis is available server-side via process.env.REDIS_URL
// Use ioredis (check portal/operator/package.json for redis client)
// Execution-time: grep -n "redis\|ioredis\|Redis" portal/operator/package.json
// If no Redis client in portal, use a fetch to a thin core-platform proxy.
// Decision: if Redis is not directly available in Next.js BFF, dismiss state
// is stored as a BFF-local Map keyed by {tid}:{source} with TTL managed by
// expiry timestamp comparison. This avoids a Redis dependency in the BFF.
```

**Execution-time verification:** `grep -rn "ioredis\|\"redis\"" portal/operator/package.json`
to confirm whether Redis client is available before implementing dismiss state.

### D-D3 — Alert cluster mapping

```typescript
// Source → cluster mapping (verified against plan decisions in Plan A)
const SOURCE_CLUSTER: Record<string, DatasetQuality["cluster"]> = {
  nppes: "prescribers",
  cms_opt_out: "exclusions",  // CMS opt-out is an exclusion, cross-linked from prescribers
  ncpdp: "pharmacies",
  fda_ndc: "drugs", fda_orange_book: "drugs", fda_purple_book: "drugs",
  fda_drug_shortages: "drugs", fda_rems: "drugs", rxnorm: "drugs",
  hcpcs: "codes", icd10_cm: "codes",
  cms_asp: "pricing", cms_nadac: "pricing", state_medicaid_bins: "pricing",
  ofac_sdn: "exclusions", sam_exclusions: "exclusions",
  oig_leie: "exclusions", dea_registrations: "exclusions",
  // nppes sub-modes:
  nppes_monthly: "prescribers", nppes_deactivation: "prescribers",
  // No-loader sources (still shown in dashboard):
  fdb: "drugs",    // b9_blocked
  // bpg: excluded from quality dashboard (no IngestionSchedule row)
  // relay-health: excluded entirely
};
```

---

## Part 2 — Quality dashboard sidebar components

### D-D4 — `QualityDashboardPanel` (`src/quality/QualityDashboardPanel.tsx`)

Sidebar spine per spec D4. Fetches `GET /api/directories/quality` via
`useQuery` with `staleTime: 60_000` (matches BFF cache TTL).

```typescript
interface QualityDashboardPanelProps {
  onAlertDismiss?: (source: string) => void;
}
// Renders:
// - One FreshnessChip row per cluster, sorted by staleness (oldest first)
// - IngestionAlertList (errors or failures in last 7 days)
// - Refetch triggered by TanStack Query invalidation of tag 'dir:quality'
//   (fired from RunProgressBar.onComplete in Plan C)
```

**Freshness color thresholds** (verified: spec §6.5):
- Green: `last_run_at` within 7 days
- Yellow: 7–14 days ago
- Red: > 14 days or `last_run_at = null`

### D-D5 — `IngestionAlertList` (`src/quality/IngestionAlertList.tsx`)

List of actionable alerts. An alert is triggered when:
- `last_run_status = 'failed'` in the last 7 days, OR
- `records_errored > 0` in the last run

```typescript
interface IngestionAlert {
  source: string;
  cluster: DatasetQuality["cluster"];
  alertType: "failed" | "errors";
  records_errored: number;
  last_run_at: string;
  is_dismissed: boolean;
}
// Each alert row:
// - Source name + cluster badge
// - "View details" → RunHistoryDrawer (from Plan C)
// - "Re-trigger" → TriggerRefreshButton (from Plan C)
// - "Dismiss" → DismissAlertAction
```

### D-D6 — `DismissAlertAction` (`src/quality/DismissAlertAction.tsx`)

Marks alert dismissed. Calls BFF `POST /api/directories/quality/dismiss/{source}`.
BFF writes `dir:alert_dismissed:{tid}:{source}` to Redis (TTL 86400s = 24h).
Next quality dashboard refetch reads the key and sets `is_dismissed: true`.

```typescript
interface DismissAlertActionProps {
  source: string;
  onDismissed: () => void;  // invalidates dir:quality TanStack tag
}
```

**BFF route:** `POST /api/directories/quality/dismiss/{source}`

```typescript
// src/bff/quality.ts (additional export)
// POST /api/directories/quality/dismiss/{source}
// Sets Redis key: dir:alert_dismissed:{tid}:{source} = "1" (TTL 24h)
// Auth: JWT required. Returns 204 on success.
// No-loader sources cannot be dismissed (404 if source not in TRIGGERABLE_SOURCES).
```

---

## Part 3 — Audit log viewer

### D-D7 — `AuditLogPage` (`src/audit/AuditLogPage.tsx`)

Read-only, paginated view of ingestion-related audit events from the core-platform
audit log. Columns: Timestamp, Source (from `entity_id`), Action, Actor
(`triggered_by` from RunDetail), Run ID (link to `RunHistoryDrawer`), Status.

```typescript
// Fetches via BFF: GET /api/directories/audit?limit=50&offset=0
// Supports pagination via offset param
// Each row: cross-link run_id → RunHistoryDrawer (Plan C)
```

### D-D8 — `GET /api/directories/audit` BFF route

```typescript
// src/bff/audit.ts
// GET /api/directories/audit?limit=50&offset=0
// Proxies to: GET http://core-platform:8000/api/v1/audit
//   with pre-applied filter: module=prescriber_directory (ingestion host post-Plan-C)
//   and date_from = now - 90d (90-day window for audit viewer)
// Returns AuditPage from core-platform's audit API.
// Auth: JWT required. JWT forwarded to core-platform (core-platform's audit API
//   requires audit:read permission via require_permission("audit:read")).
//
// IMPORTANT: The BFF forwards the original JWT to core-platform — it does NOT
// re-sign or create a new token. This means the authenticated user must have
// audit:read permission in core-platform. Per D7 (no RBAC in SP-2), all
// authenticated users are granted audit:read for ingestion-related events.
// Execution-time: verify core-platform's permission model allows this — if
// audit:read requires a specific role, either (a) add it to the default user
// permissions in core-platform, or (b) use the BFF as a service-account
// caller with a service JWT for audit reads only.
```

---

## Tasks

### Task D-1: Quality schemas extension

**File:** `packages/modules/directories/src/search/schemas.ts` — add `DatasetQualitySchema`,
`QualityResponseSchema` per D-D1.

**Tests:** `packages/modules/directories/tests/unit/schemas.test.ts` — add:
- `DatasetQualitySchema` parses valid payload
- `DatasetQualitySchema` rejects unknown `cluster` value
- `DatasetQualitySchema.is_dismissed` defaults to `false`
- `QualityResponseSchema` parses array of datasets with `as_of` string

### Task D-2: Quality BFF aggregator

**File:** `packages/modules/directories/src/bff/quality.ts` — implement `GET /api/directories/quality`
and `POST /api/directories/quality/dismiss/{source}` per D-D2 and D-D6.

**Tests:** `packages/modules/directories/tests/unit/bff-quality.test.ts`:
- No JWT → 401
- Fan-out: all backends respond → 200 with full dataset list
- Pharmacy stats called with `?x-tenant-id={tid}` (mandatory per router.py:442); assert URL contains it
- Fan-out: ingestion status backend down → partial results with `is_partial: true`
- FDB entry: `b9_blocked: true`, `no_loader: true`
- BPG entry: absent from quality response (no IngestionSchedule)
- relay-health: absent from quality response
- Dismissed source: `is_dismissed: true` in response
- `POST /dismiss/{source}` with unknown source → 404
- `POST /dismiss/{source}` with valid source → 204; subsequent GET shows `is_dismissed: true`

**Coverage gate:** 100% on auth validation + source allowlist check (security controls).
100% on x-tenant-id pass-through logic (tenant-isolation test). 99% overall.

### Task D-3: Quality dashboard components

**Files to create:**
- `packages/modules/directories/src/quality/QualityDashboardPanel.tsx`
- `packages/modules/directories/src/quality/IngestionAlertList.tsx`
- `packages/modules/directories/src/quality/DismissAlertAction.tsx`
- `packages/modules/directories/src/quality/index.ts`

**Tests:** `packages/modules/directories/tests/unit/quality/QualityDashboardPanel.test.tsx`:
- Renders one chip per source (18 total minus bpg, relay-health = N rows)
- Source with `last_run_at` today → green chip
- Source with `last_run_at` 10 days ago → yellow chip
- Source with `last_run_at` null → red chip, "Never loaded"
- `records_errored > 0` → orange error badge
- `last_run_status = 'failed'` → alert in `IngestionAlertList`

`packages/modules/directories/tests/unit/quality/IngestionAlertList.test.tsx`:
- No alerts → empty state "No data quality issues detected"
- Alert with `failed` status → shows "Re-trigger" + "View details" + "Dismiss"
- Alert with `records_errored > 0` → shows error count badge
- Dismissed alert → "Dismiss" button absent (or greyed)

`packages/modules/directories/tests/unit/quality/DismissAlertAction.test.tsx`:
- Click dismiss → POST fires → `onDismissed` called
- POST 404 (unknown source) → error toast

### Task D-4: Audit log viewer

**Files to create:**
- `packages/modules/directories/src/bff/audit.ts`
- `packages/modules/directories/src/audit/AuditLogPage.tsx`
- `packages/modules/directories/src/audit/index.ts`

**Tests:** `packages/modules/directories/tests/unit/bff-audit.test.ts`:
- No JWT → 401
- Valid JWT → proxies to core-platform with pre-applied filter
- JWT forwarded to core-platform (Authorization header preserved)

`packages/modules/directories/tests/unit/audit/AuditLogPage.test.tsx`:
- Renders table with timestamp, action, actor columns
- Empty state when no events: "No ingestion audit events yet"
- Run ID link navigates to RunHistoryDrawer

**Coverage gate:** 100% on auth validation in `bff/audit.ts`. 99% overall.

### Task D-5: Cross-tenant isolation test for quality BFF

Per spec §9.6: pharmacy stats is tenant-scoped; quality dashboard must strip
tenant-scoped fields.

**Test:** `packages/modules/directories/tests/integration/quality-cross-tenant.test.ts`
(integration, requires docker-compose backends or mock servers):
- Call `GET /api/directories/quality` with `tid_A` JWT
- Call `GET /api/directories/quality` with `tid_B` JWT
- Assert: global reference fields (`records_inserted`, `records_errored`, `last_run_at`)
  are identical for non-tenant-scoped sources
- Assert: `total_networks` and `pending_credentialing` from pharmacy stats are
  tenant-specific (these are NOT surfaced in the quality response — they are stripped
  in the BFF merge step; test verifies they do NOT appear in the quality response body)

**Coverage gate:** 100% on the x-tenant-id extraction + pharmacy stats call path
(tenant isolation test requirement per `.claude/rules/tenant-isolation.md`).

### Task D-6: Module barrel update

**File:** `packages/modules/directories/src/quality/index.ts` — barrel exports.
**File:** `packages/modules/directories/src/audit/index.ts` — barrel exports.
**File:** `packages/modules/directories/src/index.ts` — add quality and audit exports.

---

## Testing requirements (Plan D total)

| Test file | What | Coverage target |
|---|---|---|
| `tests/unit/schemas.test.ts` (extended) | DatasetQuality + QualityResponse zod schemas | 100% |
| `tests/unit/bff-quality.test.ts` | auth + fan-out + x-tenant-id + dismiss + BPG/FDB/relay-health exclusion | 100% auth + tenant; 99% overall |
| `tests/unit/quality/QualityDashboardPanel.test.tsx` | freshness colors, error badges, alert list | 99% |
| `tests/unit/quality/IngestionAlertList.test.tsx` | alert detection, empty state, dismiss | 99% |
| `tests/unit/quality/DismissAlertAction.test.tsx` | dismiss POST, error toast | 99% |
| `tests/unit/bff-audit.test.ts` | auth + proxy + JWT forwarding | 100% auth; 99% overall |
| `tests/unit/audit/AuditLogPage.test.tsx` | table columns, empty state, run link | 99% |
| `tests/integration/quality-cross-tenant.test.ts` | tenant-scoped fields stripped; global fields identical | 100% on x-tenant-id path |

---

## `SourceStatus` field name reference (confirmed from HEAD)

These are the EXACT field names from `shared/data_ingestion/api/schemas.py:47-89`.
Any plan or code that references these must use these exact names:

```typescript
// SourceStatus fields:
// source: str
// cron_expression: str | null
// enabled: bool
// last_run: RunSummary | null
// last_success_at: datetime | null
// next_run_at: datetime | null

// RunSummary fields (nested in last_run):
// id: UUID
// source: str
// run_type: str
// status: "running" | "completed" | "completed_core" | "failed" | "skipped_unchanged"
// records_processed: int
// records_inserted: int
// records_updated: int
// records_skipped: int
// records_errored: int
// started_at: datetime
// completed_at: datetime | null     ← NOT "finished_at" (that field does NOT exist)
// duration_seconds: int | null
// error_message: str | null
```

Note: The spec §7.2 references `run.status` and `records_errored` — these are
confirmed correct. The spec's reference to `finished_at` is incorrect — the
actual field is `completed_at`. All Plan D code uses `completed_at`.

---

## Verified citations (pre-write grep results)

| Symbol / Path | Verification |
|---|---|
| `shared/data_ingestion/api/schemas.py:81-89` | `SourceStatus` — `source`, `cron_expression`, `enabled`, `last_run`, `last_success_at`, `next_run_at` |
| `shared/data_ingestion/api/schemas.py:47-62` | `RunSummary` — all fields listed above; `completed_at` NOT `finished_at` |
| `shared/data_ingestion/api/schemas.py:92-96` | `TriggerResponse` — `run_id: UUID`, `source: str` |
| `shared/data_ingestion/api/routes.py:260` | `@router.get(...)` for all-status |
| `shared/data_ingestion/api/routes.py:265` | `async def get_all_status()` |
| `modules/core-platform/src/audit/api.py:34` | `router = APIRouter(prefix="/api/v1/audit", ...)` |
| `modules/core-platform/src/audit/api.py:39-66` | `list_audit` — `action`, `module`, `entity_type`, `date_from`, `date_to`, `limit`, `offset` params |
| `modules/core-platform/src/api/__init__.py:16` | `from ..audit.api import build_audit_router` |
| `modules/core-platform/src/api/__init__.py:77` | `build_audit_router(...)` called |
| `modules/pharmacy-directory/src/api/router.py:440-442` | `GET /stats` MANDATORY `x-tenant-id` |
| `modules/prescriber-directory/src/api/router.py:381-382` | `GET /stats` no `x-tenant-id` alias |
| `modules/drug-database/src/api/router.py:345-346` | `GET /refresh/status` |
| `portal/shared/lib/constants.ts:6-7` | `corePlatform: http://localhost:8000` |
| `portal/shared/lib/constants.ts:17-22` | portal/shared API URLs confirmed |
| `shared/data_ingestion/api/routes.py` (full file) | Zero audit writes — confirmed not writing to core-platform audit log |
| `packages/auth/src/claims.ts:6-7` | JWT `sub` + `tid` field names |

---

## Out of scope for Plan D

- E2E round-trip test (Plan E)
- Synthetic fixture seeding (Plan E)
- Playwright spec for quality dashboard (Plan E)
- Backend ingestion audit event writing (would require modifying
  `shared/data_ingestion/api/routes.py` to add audit calls — out of SP-2 scope;
  the AuditLogPage gracefully handles empty state)
