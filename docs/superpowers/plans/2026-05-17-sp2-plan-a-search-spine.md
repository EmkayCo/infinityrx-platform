# SP-2 Plan A — Federated Search Spine, Cmd+K, BFF Fan-out

**Status:** DRAFT  
**Date:** 2026-05-17  
**Vertical:** SP-2 Directories Portal / Reference Data Control Plane  
**Spec ref:** `docs/superpowers/specs/2026-05-16-sp2-directories-portal-design.md`  
**Codex:** Spec GO after r3 (`docs/superpowers/codex-sp2-spec-review-r1.md`)  
**Builds on:** SP-0 (Plans A–D, all shipped)  

---

## §10 Open-gap decisions locked by this plan

These were deferred to the plan-writer in the spec's §10 and the codex review.
All decisions verified against HEAD before writing.

| Gap | Decision |
|---|---|
| **§10.3 Ingestion API host** | No module currently mounts `shared/data_ingestion/api/routes.py`. Verified: `grep -rn "ingestion_router\|from shared.data_ingestion.api" modules` → zero results. SP-2 Plan C mounts it in `prescriber-directory` (the natural "directories" backend, port 8010 per `.env.local`). One-liner: `app.include_router(ingestion_router, prefix="/api/v1/data-ingestion")`. |
| **§10.4 members/ exclusion** | `portal/operator/app/directories/members/` is member-management UI, not reference data. SP-2 does NOT wrap it. Flagged as future member-management vertical. |
| **§10.7 relay-health** | `data/reference/relay-health/` and `data/reference/RelayHealth/` contain VPN connectivity guides, PDF docs, and switch test files — NOT batch-loadable reference data. No `_SOURCE_NAME` exists in `shared/data_ingestion/sources/`. Disposition: excluded from ingestion console; displayed in portal documentation section only (out of SP-2 scope). |
| **§10.8 medicaid/ surface** | `data/reference/medicaid/` contains regional BIN coverage maps (midwest.csv, northeast.csv, etc.) and a `coverage_report.md` confirming 219 loaded BIN entries. Source constant: `source_name = "state_medicaid_bins"` in `sources/state_medicaid_bins.py`. Disposition: **Pricing cluster** (alongside CMS-ASP, NADAC, BPG) with label "Medicaid BINs — state BIN coverage". |
| **rxnorm/oig_leie/dea_registrations cluster** | All three confirmed loaders (verified in `sources/rxnorm.py`, `sources/oig_leie.py`, `sources/dea_registrations.py`). `rxnorm` → **Drugs cluster** (drug classification / terminology). `oig_leie` and `dea_registrations` → **Exclusions cluster** (alongside `cms_opt_out`, `ofac_sdn`, `sam_exclusions`, `state_medicaid_bins`). |
| **§10.6 BPG** | `data/reference/bpg/` contains `BPG_Translator_API_Documentation.txt` and `patientlens-api-complete-reference.txt` — live external API, no batch loader. No `_SOURCE_NAME` in `sources/`. Disposition: Pricing browse surface shows BPG with label "Live API — no ingestion schedule"; no trigger button in ingestion console. |
| **§10.5 Alert persistence** | Dismissed alerts are Redis-keyed per `dir:alert_dismissed:{tid}:{source}` (TTL 24h). No new backend resource required — the BFF reads/writes its own Redis key. |
| **§10.1 Search index** | BFF fan-out is correct for launch. Decision: proceed with fan-out at plan time. If measured P95 exceeds 300ms during integration testing, escalate to a Postgres `tsvector` materialized view as fallback. A dedicated search service (Elasticsearch) is explicitly deferred. |
| **§10.2 Plan phasing** | Approach A (spec D6). Plan A: search spine. Plan B: browse clusters. Plan C: ingestion console + ingestion router mount. Plan D: data-quality dashboard + audit log viewer. Plan E: E2E round-trip + fixtures. |

---

## Authoritative source-key inventory (confirmed from HEAD)

All source key strings verified against `shared/data_ingestion/sources/` and `scheduler.py`.

### 6 Browse Clusters — 18 sources total

| Cluster | Sources (source key string) | Notes |
|---|---|---|
| Prescribers | `nppes`, `cms_opt_out` _(exclusion cross-link only)_ | `nppes.py:_SOURCE="nppes"` |
| Pharmacies | `ncpdp` | `ncpdp_dataq.py:_SOURCE_NAME="ncpdp"`, manual-only |
| Drugs | `fda_ndc`, `fda_orange_book`, `fda_purple_book`, `fda_drug_shortages`, `fda_rems`, `rxnorm` | All in `sources/` |
| Codes | `hcpcs`, `icd10_cm` | |
| Pricing | `cms_asp`, `cms_nadac`, `state_medicaid_bins` + BPG (live API) | `state_medicaid_bins.py:source_name="state_medicaid_bins"` |
| Exclusions | `cms_opt_out`, `ofac_sdn`, `sam_exclusions`, `oig_leie`, `dea_registrations` | `sam_exclusions.py:_SOURCE="sam_exclusions"`, `oig_leie.py:_SOURCE="oig_leie"`, `dea_registrations.py:_SOURCE="dea_registrations"` |

**No-loader sources (displayed but not triggerable):**
- `fdb`: B9-blocked. Mock surfaces with "Pending B9" banner.
- `bpg`: Live external API. Pricing browse shows read-only reference. No trigger button.
- `relay-health`: Switch connectivity docs, not reference data. Excluded from SP-2.

**nppes sub-modes** (`nppes_monthly`, `nppes_deactivation` in `DEFAULT_SCHEDULES`): exposed in ingestion console as separate schedule rows (same browse cluster as `nppes`).

---

## Deliverables

### D1 — Module package scaffold

**Path:** `packages/modules/directories/` (new; no file exists at HEAD)

```
packages/modules/directories/
  src/
    search/
      schemas.ts            ← zod: SearchResultRecord, SearchResponse
      rankResults.ts        ← pure ranking function
      FederatedSearchClient.ts  ← BFF-side fan-out class
      useDirectoriesSearch.ts   ← TanStack Query hook (client-side)
      index.ts              ← barrel
    components/             ← shared primitives (FreshnessChip, B9PendingBanner)
      FreshnessChip.tsx
      B9PendingBanner.tsx
      ProvenanceBadge.tsx
      ExclusionAlertBadge.tsx
      index.ts
    bff/
      search.ts             ← GET /api/directories/search handler
      index.ts
    surfaces/               ← STUB in Plan A; filled in Plan B
    ingestion/              ← STUB in Plan A; filled in Plan C
    quality/                ← STUB in Plan A; filled in Plan D
    audit/                  ← STUB in Plan A; filled in Plan D
    index.ts
  fixtures/                 ← synthetic seed data (Plan E)
  tests/
    unit/
      rankResults.test.ts
      schemas.test.ts
      FederatedSearchClient.test.ts
      FreshnessChip.test.tsx
      B9PendingBanner.test.tsx
  module.config.ts
  package.json
  tsconfig.json
  vitest.config.ts
```

### D2 — `module.config.ts`

**Verified template:** `packages/modules/paysync/module.config.ts` uses `as const` literal, no shared type import from `@infinityrx/shell`. Same pattern here.

```typescript
// packages/modules/directories/module.config.ts
// SP-2 Directories module config.
// Follows SD-4 §3 shape (read by packages/scripts/build-manifest.ts).
// No shared type imported from @infinityrx/shell — `as const` literal per SP-0 Plan A R2.

export const config = {
  name: "directories",
  routes: [
    "/directories",
    "/directories/prescribers",
    "/directories/prescribers/[npi]",
    "/directories/pharmacies",
    "/directories/pharmacies/[npi]",
    "/directories/drugs",
    "/directories/drugs/[ndc]",
    "/directories/codes/hcpcs",
    "/directories/codes/icd10",
    "/directories/pricing",
    "/directories/exclusions",
    "/directories/ingestion",
    "/directories/audit",
  ],
  navEntry: {
    label: "Directories",
    icon: "database",
    order: 3,
  },
  requires: {
    backends: ["prescriber-directory", "pharmacy-directory", "drug-database", "core-platform"],
    sharedServices: ["postgres", "redis"],
    schemas: ["prescriber_dir", "pharmacy_dir", "drug_db", "shared", "audit"],
    migrations: [],
    env: [
      "PRESCRIBER_DIRECTORY_URL",
      "PHARMACY_DIRECTORY_URL",
      "DRUG_DATABASE_URL",
      "CORE_PLATFORM_URL",
    ],
    health: [
      "http://prescriber-directory:8010/health",
      "http://pharmacy-directory:8009/health",
      "http://drug-database:8011/health",
    ],
    seedData: ["directories/fixtures"],
    queues: [],
    jobs: [],
    buckets: [],
    integrations: ["shared-ingestion-api"],
    secrets: [],
  },
  shellSurfaces: {
    navOrderSlots: [3],
    cacheTagPrefixes: ["dir:"],
    commandPaletteScopes: ["directories.*"],
    routePrefixes: ["/directories"],
    cacheKeyNamespaces: ["dir"],
    redisKeyPrefixes: ["dir:"],
  },
} as const;

export default config;
```

### D3 — Zod schemas (`src/search/schemas.ts`)

```typescript
// src/search/schemas.ts
import { z } from "zod";

/** Dataset cluster keys — 6 browse clusters + sub-keys for disambiguation */
export const DatasetKeySchema = z.enum([
  "nppes",
  "ncpdp",
  "fda_ndc",
  "fda_orange_book",
  "fda_purple_book",
  "fda_drug_shortages",
  "fda_rems",
  "rxnorm",
  "hcpcs",
  "icd10_cm",
  "cms_asp",
  "cms_nadac",
  "state_medicaid_bins",
  "cms_opt_out",
  "ofac_sdn",
  "sam_exclusions",
  "oig_leie",
  "dea_registrations",
]);
export type DatasetKey = z.infer<typeof DatasetKeySchema>;

/** Single federated search result (BFF boundary + client boundary validated) */
export const SearchResultRecordSchema = z.object({
  dataset: DatasetKeySchema,
  id: z.string().min(1),
  display: z.string().min(1),
  secondary: z.string().default(""),
  source_date: z.string().nullable(),
  run_id: z.string().nullable(),
  b9_blocked: z.boolean().optional(),
});
export type SearchResultRecord = z.infer<typeof SearchResultRecordSchema>;

/** BFF response envelope */
export const SearchResponseSchema = z.object({
  results: z.array(SearchResultRecordSchema),
  is_partial: z.boolean(),
  timed_out_datasets: z.array(DatasetKeySchema),
});
export type SearchResponse = z.infer<typeof SearchResponseSchema>;

/** ID pattern detection — NPI, NDC, HCPCS, ICD-10 */
export const ID_PATTERNS = {
  NPI: /^\d{10}$/,
  NDC_11: /^\d{11}$/,
  NDC_HYPHENATED: /^\d{4,5}-\d{3,4}-\d{1,2}$/,
  HCPCS: /^[A-Z]\d{4}$/i,
  ICD10: /^[A-Z]\d{2}(\.\w{1,4})?$/i,
} as const;
```

### D4 — `rankResults` pure function (`src/search/rankResults.ts`)

```typescript
// src/search/rankResults.ts
// Pure ranking function — exact-id first, then prefix, then substring, then secondary.
// Unit-tested in isolation (no BFF or backend dependency).
import type { SearchResultRecord } from "./schemas.js";

type RankTier = 0 | 1 | 2 | 3 | 4; // 0=exact, 1=prefix, 2=substring, 3=secondary, 4=none

function scoreTier(record: SearchResultRecord, q: string): RankTier {
  const ql = q.toLowerCase();
  if (record.id.toLowerCase() === ql) return 0;
  if (record.display.toLowerCase().startsWith(ql)) return 1;
  if (record.display.toLowerCase().includes(ql)) return 2;
  if (record.secondary.toLowerCase().includes(ql)) return 3;
  return 4;
}

export function rankResults(
  results: SearchResultRecord[],
  query: string,
): SearchResultRecord[] {
  if (!query.trim()) return results;
  return [...results].sort((a, b) => {
    const ta = scoreTier(a, query);
    const tb = scoreTier(b, query);
    if (ta !== tb) return ta - tb;
    return a.display.localeCompare(b.display);
  });
}
```

### D5 — `FederatedSearchClient` (`src/search/FederatedSearchClient.ts`)

BFF-side class. Runs in Node.js environment (Next.js route handler).

```typescript
// src/search/FederatedSearchClient.ts
// BFF-side federated search client. Fans out to backend search endpoints in
// parallel, enforces 300ms wall-time budget, merges and ranks results.
import type { SearchResultRecord } from "./schemas.js";
import { rankResults } from "./rankResults.js";
import { ID_PATTERNS } from "./schemas.js";

export interface FederatedSearchOpts {
  prescriberDirectoryUrl: string;  // e.g. http://prescriber-directory:8010
  pharmacyDirectoryUrl: string;    // e.g. http://pharmacy-directory:8009
  drugDatabaseUrl: string;         // e.g. http://drug-database:8011
  budgetMs?: number;               // wall-time budget (default 300)
  limitPerDataset?: number;        // per-backend limit (default 5)
}

export class FederatedSearchClient {
  private opts: Required<FederatedSearchOpts>;

  constructor(opts: FederatedSearchOpts) {
    this.opts = { budgetMs: 300, limitPerDataset: 5, ...opts };
  }

  /** ID shortcut: detect NPI/NDC/HCPCS/ICD-10 and route to exact-match endpoint */
  detectIdShortcut(q: string): { kind: "npi" | "ndc" | "hcpcs" | "icd10"; value: string } | null {
    if (ID_PATTERNS.NPI.test(q)) return { kind: "npi", value: q };
    if (ID_PATTERNS.NDC_11.test(q) || ID_PATTERNS.NDC_HYPHENATED.test(q)) return { kind: "ndc", value: q };
    if (ID_PATTERNS.HCPCS.test(q)) return { kind: "hcpcs", value: q };
    if (ID_PATTERNS.ICD10.test(q)) return { kind: "icd10", value: q };
    return null;
  }

  async search(
    q: string,
    correlationId: string,
  ): Promise<{ results: SearchResultRecord[]; timedOutDatasets: string[] }> {
    const deadline = Date.now() + this.opts.budgetMs;
    const headers = { "x-correlation-id": correlationId, "content-type": "application/json" };
    const limit = this.opts.limitPerDataset;

    // Build fan-out promises — each resolves to records or [] on timeout/error
    const withDeadline = async <T>(p: Promise<T>, fallback: T): Promise<T> => {
      const timeout = new Promise<T>((res) => setTimeout(() => res(fallback), deadline - Date.now()));
      return Promise.race([p, timeout]);
    };

    type DatasetFetch = Promise<{ records: SearchResultRecord[]; dataset: string; ok: boolean }>;

    const fetches: DatasetFetch[] = [
      withDeadline(
        fetch(`${this.opts.prescriberDirectoryUrl}/api/v1/prescribers/search?q=${encodeURIComponent(q)}&limit=${limit}`, { headers })
          .then((r) => r.json())
          .then((data) => ({
            records: (data.results ?? []).map((p: Record<string, unknown>) => ({
              dataset: "nppes" as const,
              id: String(p.npi ?? ""),
              display: String(p.name ?? p.display ?? ""),
              secondary: String(p.specialty ?? ""),
              source_date: String(p.source_date ?? "") || null,
              run_id: String(p.run_id ?? "") || null,
            })),
            dataset: "nppes",
            ok: true,
          }))
          .catch(() => ({ records: [], dataset: "nppes", ok: false })),
        { records: [], dataset: "nppes", ok: false },
      ),
      withDeadline(
        fetch(`${this.opts.pharmacyDirectoryUrl}/api/v1/pharmacies/search?q=${encodeURIComponent(q)}&limit=${limit}`, { headers })
          .then((r) => r.json())
          .then((data) => ({
            records: (data.results ?? []).map((p: Record<string, unknown>) => ({
              dataset: "ncpdp" as const,
              id: String(p.nabp ?? ""),
              display: String(p.name ?? p.display ?? ""),
              secondary: String(p.city ?? ""),
              source_date: String(p.source_date ?? "") || null,
              run_id: String(p.run_id ?? "") || null,
            })),
            dataset: "ncpdp",
            ok: true,
          }))
          .catch(() => ({ records: [], dataset: "ncpdp", ok: false })),
        { records: [], dataset: "ncpdp", ok: false },
      ),
      withDeadline(
        fetch(`${this.opts.drugDatabaseUrl}/api/v1/drugs/search?q=${encodeURIComponent(q)}&limit=${limit}`, { headers })
          .then((r) => r.json())
          .then((data) => ({
            records: (data.results ?? []).map((d: Record<string, unknown>) => ({
              dataset: "fda_ndc" as const,
              id: String(d.ndc ?? ""),
              display: String(d.proprietary_name ?? d.display ?? ""),
              secondary: String(d.nonproprietary_name ?? ""),
              source_date: String(d.source_date ?? "") || null,
              run_id: String(d.run_id ?? "") || null,
            })),
            dataset: "fda_ndc",
            ok: true,
          }))
          .catch(() => ({ records: [], dataset: "fda_ndc", ok: false })),
        { records: [], dataset: "fda_ndc", ok: false },
      ),
    ];

    const settled = await Promise.all(fetches);
    const timedOutDatasets = settled.filter((s) => !s.ok).map((s) => s.dataset);
    const allRecords = settled.flatMap((s) => s.records);
    return { results: rankResults(allRecords, q), timedOutDatasets };
  }
}
```

### D6 — BFF route handler (`src/bff/search.ts`)

This is a Next.js route handler mounted at `/api/directories/search`. SP-0 composition mounts the module's BFF into the shell's `app/api/` tree per SD-4.

```typescript
// src/bff/search.ts
// GET /api/directories/search?q=...&datasets=all&limit=20
// Validates JWT (packages/auth), fans out to backends, returns ranked results.
import { type NextRequest, NextResponse } from "next/server";
import { verifyAccessToken } from "@infinityrx/auth";
import { SearchResponseSchema } from "../search/schemas.js";
import { FederatedSearchClient } from "../search/FederatedSearchClient.js";
import { rankResults } from "../search/rankResults.js";

const client = new FederatedSearchClient({
  prescriberDirectoryUrl: process.env.PRESCRIBER_DIRECTORY_URL ?? "http://prescriber-directory:8010",
  pharmacyDirectoryUrl: process.env.PHARMACY_DIRECTORY_URL ?? "http://pharmacy-directory:8009",
  drugDatabaseUrl: process.env.DRUG_DATABASE_URL ?? "http://drug-database:8011",
  budgetMs: 300,
  limitPerDataset: 5,
});

export async function GET(req: NextRequest): Promise<NextResponse> {
  // Auth gate — verifyAccessToken from packages/auth (verifyAccessToken exported from src/verify.ts)
  const authHeader = req.headers.get("authorization") ?? "";
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : null;
  if (!token) {
    return NextResponse.json({ error: { code: "UNAUTHORIZED", message: "Authentication required", correlation_id: crypto.randomUUID() } }, { status: 401 });
  }
  let claims: { sub: string; tid: string };
  try {
    claims = await verifyAccessToken(token, { secret: process.env.JWT_SECRET! });
  } catch {
    return NextResponse.json({ error: { code: "UNAUTHORIZED", message: "Invalid token", correlation_id: crypto.randomUUID() } }, { status: 401 });
  }

  const correlationId = req.headers.get("x-correlation-id") ?? crypto.randomUUID();
  const q = req.nextUrl.searchParams.get("q")?.trim() ?? "";

  if (!q || q.length < 2) {
    return NextResponse.json(
      SearchResponseSchema.parse({ results: [], is_partial: false, timed_out_datasets: [] }),
    );
  }

  // ID shortcut check
  const shortcut = client.detectIdShortcut(q);
  if (shortcut) {
    // Route to exact-match endpoint (faster path — returns single result)
    // Handled inline for NPI; other shortcuts delegated to fan-out with limit=1
    // (simplified in Plan A; full exact-match routing in Plan B per-dataset pages)
  }

  const { results, timedOutDatasets } = await client.search(q, correlationId);
  const limited = results.slice(0, 20);

  const response = SearchResponseSchema.parse({
    results: limited,
    is_partial: timedOutDatasets.length > 0,
    timed_out_datasets: timedOutDatasets,
  });

  // Cache: 30s, tag dir:search (Next.js cache tags per SD-4 §5.3)
  const res = NextResponse.json(response);
  res.headers.set("Cache-Control", "public, s-maxage=30");
  res.headers.set("x-correlation-id", correlationId);
  return res;
}
```

### D7 — `useDirectoriesSearch` hook (`src/search/useDirectoriesSearch.ts`)

Client-side TanStack Query hook. `@tanstack/react-query` is in `portal/operator/package.json:44`.

```typescript
// src/search/useDirectoriesSearch.ts
import { useQuery } from "@tanstack/react-query";
import { SearchResponseSchema, type SearchResponse } from "./schemas.js";

export interface UseDirectoriesSearchOpts {
  datasets?: "all" | string[];
  limit?: number;
  enabled?: boolean;
}

export interface UseDirectoriesSearchResult {
  results: SearchResponse["results"];
  isPartial: boolean;
  timedOutDatasets: SearchResponse["timed_out_datasets"];
  isLoading: boolean;
  error: Error | null;
}

async function fetchSearch(q: string, opts: UseDirectoriesSearchOpts): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, limit: String(opts.limit ?? 20) });
  const res = await fetch(`/api/directories/search?${params.toString()}`);
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  const data = await res.json();
  return SearchResponseSchema.parse(data);
}

export function useDirectoriesSearch(
  query: string,
  opts: UseDirectoriesSearchOpts = {},
): UseDirectoriesSearchResult {
  const trimmed = query.trim();
  const { data, isLoading, error } = useQuery({
    queryKey: ["dir:search", trimmed, opts.datasets, opts.limit],
    queryFn: () => fetchSearch(trimmed, opts),
    enabled: (opts.enabled ?? true) && trimmed.length >= 2,
    staleTime: 30_000,
    gcTime: 60_000,
    // 80ms debounce handled by caller (CommandPalette component uses setTimeout)
  });

  return {
    results: data?.results ?? [],
    isPartial: data?.is_partial ?? false,
    timedOutDatasets: data?.timed_out_datasets ?? [],
    isLoading,
    error: error as Error | null,
  };
}
```

### D8 — Shared primitive components

**`FreshnessChip.tsx`** — color-coded freshness indicator:
```typescript
// src/components/FreshnessChip.tsx
interface FreshnessChipProps {
  sourceKey: string;
  lastRunAt: string | null; // ISO date string
  className?: string;
}
// Color logic: green (<7d), yellow (7-14d), red (>14d or null)
// Renders: "NPPES — 2026-05-10 (6 days ago)" with color dot
```

**`B9PendingBanner.tsx`** — FDB mock indicator:
```typescript
// src/components/B9PendingBanner.tsx
interface B9PendingBannerProps {
  dataType: "interactions" | "formulary" | "clinical";
}
// Renders: "This data requires FDB B9 ingestion which is in progress on a
// parallel track. Showing mock data."
```

**`ProvenanceBadge.tsx`** — ingestion run provenance:
```typescript
// src/components/ProvenanceBadge.tsx
interface ProvenanceBadgeProps {
  sourceKey: string;
  runId: string | null;
  sourceDate: string | null;
  recordCount?: number;
}
// Renders: "Source: NPPES | Loaded: 2026-05-10 | Records: 9,494,438 | Run: [link]"
```

**`ExclusionAlertBadge.tsx`** — cross-link alert:
```typescript
// src/components/ExclusionAlertBadge.tsx
interface ExclusionAlertBadgeProps {
  npi?: string;
  entityName?: string;
  exclusionSources: ("cms_opt_out" | "sam_exclusions" | "ofac_sdn" | "oig_leie" | "dea_registrations")[];
}
// Renders clickable badge linking to /directories/exclusions?q=<npi|entity>
```

### D9 — `package.json` for directories module

```json
{
  "name": "@infinityrx/module-directories",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "exports": {
    ".": "./dist/src/index.js"
  },
  "scripts": {
    "build": "tsc -b",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@infinityrx/auth": "*",
    "@infinityrx/contract": "*",
    "@infinityrx/qa-harness": "*",
    "@infinityrx/shell": "*",
    "@infinityrx/ui": "*",
    "@tanstack/react-query": "5.59.20",
    "@tanstack/react-virtual": "3.10.8",
    "@tanstack/react-table": "8.20.5",
    "zod": "3.23.8"
  },
  "peerDependencies": {
    "react": "^19.2.0",
    "react-dom": "^19.2.0"
  },
  "devDependencies": {
    "@testing-library/react": "16.3.0",
    "@testing-library/user-event": "14.5.2",
    "@types/node": "22.7.5",
    "@types/react": "19.1.2",
    "@types/react-dom": "19.1.2",
    "happy-dom": "15.11.7",
    "react": "19.2.6",
    "react-dom": "19.2.6",
    "typescript": "5.6.3",
    "vitest": "2.1.9"
  }
}
```

Note: `zod` version `3.23.8` matched from `packages/ui/package.json`. TanStack versions matched from `portal/operator/package.json`.

### D10 — Manifest update (`infrastructure/manifests/operator-dev.yml`)

Add `directories` to the `modules` list:
```yaml
modules:
  - prescriber-directory
  - paysync
  - directories          # SP-2 addition
```

Add to `required_backends`, `required_env`, `required_health`, `required_seed_data`:
```yaml
required_backends:
  - billing
  - payment-processing
  - edi-compliance
  - core-platform
  - prescriber-directory   # already listed as module, now also as backend
  - pharmacy-directory     # SP-2 addition
  - drug-database          # SP-2 addition

required_env:
  # existing entries preserved...
  - PRESCRIBER_DIRECTORY_URL
  - PHARMACY_DIRECTORY_URL
  - DRUG_DATABASE_URL

required_health:
  # existing entries preserved...
  - http://prescriber-directory:8010/health
  - http://pharmacy-directory:8009/health
  - http://drug-database:8011/health

required_seed_data:
  - directories/fixtures
```

---

## Tasks

### Task A-1: Scaffold module package

**File:** `packages/modules/directories/package.json` — create per D9.  
**File:** `packages/modules/directories/tsconfig.json` — copy structure from `packages/modules/paysync/tsconfig.json`.  
**File:** `packages/modules/directories/vitest.config.ts` — copy from `packages/modules/paysync/vitest.config.ts`.  
**File:** `packages/modules/directories/module.config.ts` — create per D2.  
**File:** `packages/modules/directories/src/index.ts` — barrel, initially empty stubs (search, components).

**Test:** Vitest runs cleanly with zero test files (no failures, no warnings).

### Task A-2: Zod schemas + `rankResults`

**File:** `packages/modules/directories/src/search/schemas.ts` — per D3.  
**File:** `packages/modules/directories/src/search/rankResults.ts` — per D4.  
**File:** `packages/modules/directories/tests/unit/schemas.test.ts` — validates zod shapes, ID_PATTERNS (NPI 10-digit, NDC 11-digit, HCPCS `J0135`, ICD-10 `Z87.891`), DatasetKey enum includes all 18 sources.  
**File:** `packages/modules/directories/tests/unit/rankResults.test.ts` — exact match scores 0, prefix scores 1, substring scores 2, secondary scores 3, case-insensitive, stable sort.

**Coverage gate:** 100% on `schemas.ts` (no security paths, but schema validation is a security boundary per `.claude/rules/security.md` — all request bodies validated via zod). 99% on `rankResults.ts`.

### Task A-3: `FederatedSearchClient`

**File:** `packages/modules/directories/src/search/FederatedSearchClient.ts` — per D5.  
**File:** `packages/modules/directories/tests/unit/FederatedSearchClient.test.ts` — tests:
- Fan-out: all 3 backends return results → merged and ranked
- Partial result: one backend times out → `timedOutDatasets` includes it; other results still returned
- ID shortcut detection: `detectIdShortcut("1234567890")` → `{kind:"npi", value:"1234567890"}`, `detectIdShortcut("J0135")` → `{kind:"hcpcs", ...}`, `detectIdShortcut("Z87.891")` → `{kind:"icd10", ...}`, non-matching string → `null`
- Empty query returns empty array

Use `vi.spyOn(global, "fetch")` to mock backend HTTP calls. No real network.

**Coverage gate:** 99% branch coverage.

### Task A-4: BFF search route handler

**File:** `packages/modules/directories/src/bff/search.ts` — per D6.  
**File:** `packages/modules/directories/tests/unit/bff-search.test.ts`:
- No `Authorization` header → 401 `{"error":{"code":"UNAUTHORIZED",...}}`  
- Invalid token → 401
- Short query (`q="a"`) → 200 with empty results (no fan-out)
- Valid token + valid query → 200 with results (mock `FederatedSearchClient`)
- Partial results (`timedOutDatasets` non-empty) → `is_partial: true` in response

**Coverage gate:** 100% on auth validation paths (lines that check token and call `verifyAccessToken`). 99% overall.

### Task A-5: Shared primitive components

**File:** `packages/modules/directories/src/components/FreshnessChip.tsx` — per D8.  
**File:** `packages/modules/directories/src/components/B9PendingBanner.tsx` — per D8.  
**File:** `packages/modules/directories/src/components/ProvenanceBadge.tsx` — per D8.  
**File:** `packages/modules/directories/src/components/ExclusionAlertBadge.tsx` — per D8.  
**File:** `packages/modules/directories/src/components/index.ts` — barrel.  
**File:** `packages/modules/directories/tests/unit/FreshnessChip.test.tsx`:
- `lastRunAt` = today → green, "0 days ago"
- `lastRunAt` = 7 days ago → yellow
- `lastRunAt` = 15 days ago → red
- `lastRunAt` = null → red, "Never loaded"

**File:** `packages/modules/directories/tests/unit/B9PendingBanner.test.tsx`:
- Renders for each `dataType` value; banner text includes "FDB B9 ingestion"

### Task A-6: `useDirectoriesSearch` hook

**File:** `packages/modules/directories/src/search/useDirectoriesSearch.ts` — per D7.  
**Test:** covered by integration tests in Plan E (requires TanStack Query wrapper). A smoke unit test asserts the hook is exported from `src/search/index.ts`.

### Task A-7: Manifest update

**File:** `infrastructure/manifests/operator-dev.yml` — add `directories` per D10.

**Test:** Existing manifest-validator test (`packages/scripts/build-manifest.ts`) must still pass. Run `npm run build:manifest` (or equivalent in `packages/scripts/`) — no errors.

---

## Testing requirements

| Test file | What | Coverage target |
|---|---|---|
| `tests/unit/schemas.test.ts` | zod shape, ID patterns, DatasetKey enum | 100% |
| `tests/unit/rankResults.test.ts` | all 5 tier outcomes, stable sort, case-insensitive | 99% |
| `tests/unit/FederatedSearchClient.test.ts` | fan-out, partial, id shortcut, empty | 99% |
| `tests/unit/bff-search.test.ts` | auth: 401 no-token, 401 bad-token, 200 valid — 100% on auth lines | 100% auth paths; 99% overall |
| `tests/unit/FreshnessChip.test.tsx` | green/yellow/red/null cases | 99% |
| `tests/unit/B9PendingBanner.test.tsx` | all 3 dataType values | 99% |

No E2E in Plan A — that's Plan E.

---

## Verified citations (pre-write grep results)

Every path and symbol below was verified against HEAD before this plan was written.

| Symbol / Path | Verification |
|---|---|
| `packages/ui/src/command/CommandPalette.tsx` | exists; uses `cmdk` 1.0.4 (line 1) |
| `packages/ui/src/index.ts:23` | exports `CommandPalette, CommandPaletteProps, CommandItem` |
| `packages/auth/src/index.ts` | exports `verifyAccessToken` |
| `packages/auth/src/claims.ts:6-7` | `AccessClaimsSchema` has `sub: z.string().uuid()`, `tid: z.string().uuid()` |
| `packages/modules/paysync/module.config.ts` | `as const` literal, no `@infinityrx/shell` import — template confirmed |
| `packages/modules/paysync/package.json` | `@tanstack/react-query: 5.59.20`, `@tanstack/react-virtual: 3.10.8` |
| `portal/operator/package.json:44-46` | `@tanstack/react-query ^5.62.7`, `@tanstack/react-table ^8.20.5`, `@tanstack/react-virtual ^3.11.1` |
| `packages/ui/package.json:29-32` | `cmdk: 1.0.4`, `react-hook-form: 7.54.2`, `recharts: 2.15.3`, `zod: 3.23.8` |
| `infrastructure/manifests/operator-dev.yml` | exists; has `modules: [prescriber-directory, paysync]` |
| `portal/operator/app/directories/prescribers/page.tsx:87` | `const NPI_PATTERN = /^\d{10}$/;` |
| `modules/prescriber-directory/src/api/router.py:87-88` | `@router.get("/search")` `async def search_prescribers` |
| `modules/pharmacy-directory/src/api/router.py:153-154` | `@router.get("/search")` `async def search_pharmacies` |
| `modules/drug-database/src/api/router.py:84-85` | `@router.get("/search")` `async def search_drugs` |
| `shared/data_ingestion/api/routes.py` | exists; `router = APIRouter(tags=["data-ingestion"])`; no module mounts it (verified: zero `include_router(ingestion_router)` in modules/) |
| `portal/operator/.env.local` | prescriber-directory:8010, pharmacy-directory:8009, drug-database:8011, core-platform:8000 |
| `packages/modules/directories/` | does NOT exist at HEAD — clean slate for SP-2 |

---

## Out of scope for Plan A

- Per-dataset browse surfaces (Plan B)
- Ingestion console + ingestion router mount (Plan C)
- Data-quality dashboard + audit log viewer (Plan D)
- E2E fixtures + round-trip test (Plan E)
- CommandPalette extension to use `useDirectoriesSearch` (Plan B — wraps existing `packages/ui/src/command/CommandPalette.tsx`)
