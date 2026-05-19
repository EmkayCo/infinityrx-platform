# Pharmacy Directory Crash Diagnosis
**Date:** 2026-05-18
**Branch:** wave/B10-w5
**Investigator:** Agent subagent (systematic-debugging Iron Law)

---

## Repro Steps (Exact Commands Run)

```bash
# 1. Start Next.js dev server (main repo portal)
cd portal/operator
SKIP_PREBUILD=1 /path/to/portal/node_modules/.bin/next dev --turbopack --port 3099

# 2. Hit the pharmacy list page
curl -s --max-time 10 http://localhost:3099/directories/pharmacies
# → HTTP 307 → http://localhost:3000/login?callbackUrl=%2Fdirectories%2Fpharmacies

# 3. Hit the BFF API route directly (no auth header)
curl -s http://localhost:3099/api/directories/pharmacies
# → HTTP 401: {"error":{"code":"UNAUTHORIZED","message":"Authentication required",...}}

# 4. Check pharmacy backend availability
curl http://localhost:8009/health
# → Connection refused (backend NOT running)
```

---

## Observed Error

Three layered failures:

1. **Server starts but reports a Turbopack error** (non-fatal in dev mode, server continues):
   ```
   Error: Next.js inferred your workspace root, but it may not be correct.
   We couldn't find the Next.js package (next/package.json) from the project directory:
   .../portal/operator/app
   ```
   (This is a worktree-specific issue — worktree lacks node_modules. Main repo starts fine.)

2. **Navigating to `/directories/pharmacies`**: HTTP 307 redirect to `http://localhost:3000/login?callbackUrl=/directories/pharmacies`
   - Root cause: `NEXTAUTH_URL=http://localhost:3000` in `.env.local`, but server runs on port 3099 during dev.
   - When served on port 3000 (standard), the auth redirect works — the page renders.

3. **Once authenticated and page renders** (the real crash the user sees): the page component calls the backend **directly** from the browser, hitting two bugs (see root cause below).

---

## Evidence Collected

### File: `portal/operator/app/directories/pharmacies/page.tsx`
```tsx
import { PharmaciesListPage } from "@infinityrx/module-directories";

export default function Page() {
  return <PharmaciesListPage />;  // No props passed — uses all defaults
}
```

### File: `packages/modules/directories/src/surfaces/pharmacies/PharmaciesListPage.tsx` (lines 27–46)
```tsx
export function PharmaciesListPage({
  pharmacyDirectoryUrl = "http://localhost:8009",  // hardcoded default, no prop from portal
}: PharmaciesListPageProps) {
  const { data: pharmacies = [], isLoading } = useQuery<PharmacySearchHit[]>({
    queryFn: async () => {
      const params = new URLSearchParams({ limit: "100" });
      if (search) params.set("q", search);  // q only added if non-empty
      const url = `${pharmacyDirectoryUrl}/api/v1/pharmacies/search?${params.toString()}`;
      const resp = await fetch(url);  // direct browser→backend call (not via BFF)
      // ...
      const data = (await resp.json()) as { results?: PharmacySearchHit[] };
      return data.results ?? [];  // reads .results — but backend returns .pharmacies
    },
  });
}
```

### File: `modules/pharmacy-directory/src/api/router.py` (lines 153–162)
```python
@router.get("/search", response_model=PharmacyListResponse)
async def search_pharmacies(
    q: str = Query(..., min_length=2),  # REQUIRED, min 2 chars — 422 if missing
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
) -> Any:
    pharmacies = await svc.search_by_name(q, limit=limit, offset=offset)
    return {"pharmacies": pharmacies, "total": len(pharmacies)}  # key is "pharmacies" not "results"
```

### File: `modules/pharmacy-directory/src/api/schemas.py` (lines 41–43)
```python
class PharmacyListResponse(BaseModel):
    pharmacies: list[PharmacyResponse]  # field is "pharmacies", NOT "results"
    total: int
```

### File: `portal/operator/.env.local`
```
NEXT_PUBLIC_USE_MOCK_DATA=false  # real backend calls enabled
PHARMACY_DIRECTORY_URL not set   # BFF uses this for server-side calls; component ignores it
```

### File: `portal/operator/app/api/directories/pharmacies/route.ts`
```ts
export function GET(request: NextRequest) {
  return getPharmacies(request);  // calls BFF handler
}
```

### File: `packages/modules/directories/src/bff/pharmacies.ts` (line 52)
```ts
// getPharmacies (exported as GET from BFF) proxies to /stats, NOT /search
const backendUrl = `${pharmacyDirectoryUrl}/api/v1/pharmacies/stats?x-tenant-id=...`;
```

**Note:** `pharmacyDirectoryUrl` in the BFF uses `process.env.PHARMACY_DIRECTORY_URL ?? "http://pharmacy-directory:8009"` — the hostname `pharmacy-directory` is a Docker service name (not `localhost`). In local dev without Docker, this URL is unreachable unless `PHARMACY_DIRECTORY_URL=http://localhost:8009` is set in `.env.local`.

### Git status (noise items)
- `portal/operator/middleware.ts` — **deleted** (` D` in git). The `middleware.ts.disabled` (untracked) is the original file renamed. This means Next.js runs with NO custom middleware at all — auth is handled only by NextAuth session checks inside pages.
- `packages/modules/directories/module.config.js` / `.d.ts` — untracked compiled artifacts from `tsc -b`. Not harmful but they're build artifacts that should be in `.gitignore`.
- `packages/modules/prescriber-directory/module.config.js` / `.d.ts` — same pattern.

---

## Root Cause Hypothesis

**Primary cause (confidence: HIGH):**

The `PharmaciesListPage` component has a **response key mismatch**: it reads `data.results` but the `pharmacy-directory` backend returns `data.pharmacies`. Since `results` is undefined, the component always renders an empty list (`[]`) — no error boundary fires, no visible crash, just a blank page with no pharmacies and a loading spinner that resolves to "0 results."

**Secondary cause (confidence: HIGH):**

The initial page load calls `GET /api/v1/pharmacies/search` **without a `q` parameter** (because `search` state is empty and the code only adds `q` when non-empty). The backend declares `q: str = Query(..., min_length=2)` — required, minimum 2 chars. The backend returns HTTP **422 Unprocessable Entity** on the initial load, which causes `resp.ok` to be false, throwing `Error: pharmacies search failed: 422`. This error is caught by React Query and surfaces as a query error (not an unhandled exception), so the page renders as an error state or empty state depending on the error boundary.

**Tertiary cause (confidence: MEDIUM):**

The `PharmaciesListPage` component calls the **pharmacy-directory backend directly from the browser** at `http://localhost:8009` — bypassing the BFF entirely. This violates the architecture (BFF pattern) and means:
- Auth headers (Bearer JWT, x-tenant-id) are NOT sent to the backend from the browser.
- The backend's CORS policy must allow `http://localhost:3000` — if CORS is not configured, all requests fail with CORS error.
- The BFF route at `/api/directories/pharmacies` exists and proxies to `/api/v1/pharmacies/stats` (not search) — it is essentially unused by this page.

**Fourth issue (confidence: HIGH):**

The BFF `pharmacies.ts` is wired to the **wrong backend endpoint**: it proxies to `/api/v1/pharmacies/stats` but the route file is named and documented as a pharmacy search handler. The BFF should proxy to `/api/v1/pharmacies/search`.

---

## Proposed Fix (DO NOT APPLY — orchestrator to decide)

### Fix A: Response key mismatch (primary — must fix)

**File:** `packages/modules/directories/src/surfaces/pharmacies/PharmaciesListPage.tsx`

**Before (line 42):**
```tsx
const data = (await resp.json()) as { results?: PharmacySearchHit[] };
return data.results ?? [];
```

**After:**
```tsx
const data = (await resp.json()) as { pharmacies?: PharmacySearchHit[] };
return data.pharmacies ?? [];
```

### Fix B: Optional q parameter with empty search support (primary — must fix)

Two options:
1. Make `q` optional on the backend (`q: str | None = Query(default=None, min_length=2)`) and return all results when q is absent.
2. Make the frontend skip the query when search is empty (show empty state or prompt), or always require a search term before querying.

Recommended: **Option 2 — frontend guard**: don't fire the query when `search` is empty (use `enabled: !!search && search.length >= 2`). This avoids changing the backend contract.

**File:** `packages/modules/directories/src/surfaces/pharmacies/PharmaciesListPage.tsx`

**Before (line 34):**
```tsx
const { data: pharmacies = [], isLoading } = useQuery<PharmacySearchHit[]>({
  queryKey: ["pharmacies", search],
  queryFn: async () => {
    const params = new URLSearchParams({ limit: "100" });
    if (search) params.set("q", search);
```

**After:**
```tsx
const { data: pharmacies = [], isLoading } = useQuery<PharmacySearchHit[]>({
  queryKey: ["pharmacies", search],
  enabled: search.length >= 2,
  queryFn: async () => {
    const params = new URLSearchParams({ limit: "100", q: search });
```

### Fix C: Route through BFF instead of calling backend directly (architectural — secondary)

The page should call `/api/directories/pharmacies?q=...` (Next.js BFF route) instead of `http://localhost:8009/api/v1/pharmacies/search`. This requires:
1. Fixing the BFF route to proxy to `/search` instead of `/stats`.
2. Updating `PharmaciesListPage` to accept a relative URL prop or call `/api/directories/pharmacies` directly.

**File:** `packages/modules/directories/src/bff/pharmacies.ts` (line 52)

**Before:**
```ts
const backendUrl = `${pharmacyDirectoryUrl}/api/v1/pharmacies/stats?x-tenant-id=${encodeURIComponent(tid)}`;
```

**After:**
```ts
const q = req.nextUrl.searchParams.get("q") ?? "";
const limit = req.nextUrl.searchParams.get("limit") ?? "20";
const backendUrl = `${pharmacyDirectoryUrl}/api/v1/pharmacies/search?q=${encodeURIComponent(q)}&limit=${limit}&x-tenant-id=${encodeURIComponent(tid)}`;
```

**Note:** Fix C is the correct architectural fix but is larger in scope. Fixes A+B will restore the page to a working state immediately and can ship first.

---

## Noise Discovered

1. `portal/operator/middleware.ts` is deleted from git (` D`). The renamed `middleware.ts.disabled` is untracked. This is intentional (auth middleware disabled for this wave) but the rename was not committed — git still tracks the deletion as unstaged. Should be committed or the `.disabled` file removed.

2. `packages/modules/directories/module.config.js`, `module.config.d.ts`, `module.config.d.ts.map`, `module.config.js.map` — compiled TypeScript artifacts generated by `tsc -b`. These are untracked build artifacts that should be in `.gitignore` if not already.

3. The BFF `pharmacies.ts` is misnamed/misdocumented — the file comment says "pharmacy stats" but the route at `/api/directories/pharmacies` is expected to serve pharmacy search. The `getPharmacies` export name implies search, not stats.
