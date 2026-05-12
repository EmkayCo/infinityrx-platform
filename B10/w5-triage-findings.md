# W5.6 Triage Findings — InfinityRx Operator Portal Visual QA

**Wave:** B10  **Phase:** W5.6  **Date:** 2026-05-12  **Branch:** `wave/B10-w5`
**Captured against:** local `npm run start` on `:3000` with `B10_TEST_MODE=true`,
`NEXT_PUBLIC_USE_MOCK_DATA=true`.

## Capture summary

| Metric | Value |
|---|---|
| Total routes | 133 (106 static + 27 dynamic) |
| Captured cleanly | 125 |
| Hard-failed (30s timeout, no screenshot) | 8 |
| Routes with React hydration error #418 | 34 |
| Routes with `console_errors` count > 0 | 24 |
| Routes with `page_errors` count > 0 | 18 |
| Total `failed_requests` events | 3,488 |
| `failed_requests` that were prefetch cancellations | 3,488 (100%) |
| `failed_requests` that were real failures | 0 |

Output artifacts:
- `B10/w5-fixture-map.json` (W5.3 — 26 dynamic routes classified)
- `B10/w5-error-allowlist.md` (W5.5 — updated §1 with prefetch carve-out)
- `B10/w5-capture-results.json` (full per-route capture data)
- `B10/w5-screenshots/*.png` (125 screenshots)

## Allowlist update from this run

The W5.5 speculative allowlist held up well. **One addition** based on real signal:

- **§1 added:** `requestfailed` with `net::ERR_ABORTED` for page URLs (not `/api/`).
  Empirical: 3,488 of 3,488 `failed_requests` were prefetch cancellations from
  next/link's prefetch-on-hover behavior firing during Playwright route navigation.
  Zero real network failures. The high `netfail` counts per route in the log
  output are entirely this category.

No allowlist entries were promoted to §3. All §1/§2 entries proved out.

## §3 HARD FAIL — Real bugs surfaced

### Category A — 30s timeout (route never reaches networkidle), 8 routes

These pages either hit an error boundary while a fetch keeps retrying, or have a
broken initial render that traps the page in an infinite loop. Either way, the
W5 capture never gets a stable screenshot.

| Route | Console signal | Family |
|---|---|---|
| `/admin/network/banking-discrepancies` | `TypeError: Cannot read properties of undefined (reading 'length')` at chunk `8269` | A1 (shared chunk) |
| `/admin/network/chain-membership` | React #418 hydration mismatch | A2 (hydration) |
| `/admin/network/pay-to-entities` | `TypeError: Cannot read properties of undefined (reading 'length')` at chunk `8269` | A1 (shared chunk) |
| `/admin/network/pay-to-entities/[entityId]` | `TypeError: t.map is not a function` (detail-page-specific) | A3 (route-specific) |
| `/admin/network/tenant-ach-origination` | 404 only; no JS error captured | A4 (timeout-no-signal) |
| `/medical-claims/claims/[id]` | 404 only; no JS error captured | A4 (timeout-no-signal) |
| `/payments/batches/[id]` | React #418 hydration mismatch | A2 (hydration) |
| `/reporting/viewer/[reportId]` | 404 only; no JS error captured | A4 (timeout-no-signal) |

**Family A1 — shared-chunk undefined.length crash (3 routes affected).**
All three pages crash on the same chunk hash `8269-cbde6c40e0786d1f.js:1:15153`.
Same stack frame. This is a **shared dependency** (utility, hook, or component
imported by all three admin/network pages) that doesn't guard against
undefined/null input. Mock data for these admin/network pages doesn't exist in
the seed catalog — the component is being handed `undefined` and tries to read
`.length`. ROOT CAUSE: missing null guard in the shared dependency, OR
unhandled empty-state in the admin/network layout/loader. Fix once → all three
pages unblock.

**Family A2 — React #418 hydration mismatch (2 timeouts; see also Category B).**
Hydration error #418 means the server-rendered HTML differs from the
client-rendered output, and content (not just attributes) differs.

**Family A3 — `/admin/network/pay-to-entities/[entityId]` `t.map is not a function`.**
Specific to the detail page. The component expects an array but gets something
else (undefined, null, or non-array). Detail-page-specific because the list page
also crashes via A1 in the same family.

**Family A4 — `tenant-ach-origination`, `medical-claims/claims/[id]`, `reporting/viewer/[reportId]`.**
Console shows ONLY 404 noise (the W5.5-allowlisted `Failed to load resource`).
No JS-level error captured. These hit the 30s timeout from a different cause —
likely a route-level loader that keeps retrying when the mock layer returns no
data. Capture script could be extended in a follow-up to also log `console.warn`
and `response` events to disambiguate.

### Category B — React hydration error #418, 34 routes (32 captured cleanly + 2 also timing out)

The `chain-membership` and `payments/batches/[id]` overlap with Category A.
The remaining **32 routes hit #418 but still produced a screenshot**. So the
hydration error happens, the page reconciles, and rendering completes — but the
SSR vs client HTML diverged.

Affected routes (full list — also written to `B10/w5-capture-results.json`):

```
/accounting/payments               /admin/config/change-sets
/admin/encryption                  /admin/network/chain-membership  (also Category A)
/admin/paysync/cycle-schedules     /admin/paysync/gl-account-mappings
/admin/paysync/invoice-sequences   /admin/system-health
/billing/cycles/[id]               /billing/invoices
/clients/fees                      /directories/drugs
/directories/members               /directories/members/[id]
/directories/pharmacies            /directories/pharmacies/[npi]
/directories/prescribers           /edi/certs
/edi/monitor                       /login
/medical-claims/site-of-care       /network/credentialing
/payments/batches/[id]   (also Category A)   /payments/nacha
/programs                          /programs/budget
/programs/enrollment               /reclaimrx/investigations
/reclaimrx/risk                    /reclaimrx/wizard
/reporting/scheduled               /settings/dashboard
/settings/notifications            /settings/shortcuts
```

**Common root-cause patterns for #418** (no specific component identified yet —
needs a follow-up investigation):

1. **Date/time formatting during SSR** — `new Date().toLocaleString()` produces
   different output on the server (UTC) and client (browser timezone). Calls
   visible in `/admin/paysync` console error (`Cannot read properties of
   undefined (reading 'toLocaleString')`).
2. **Theme detection during SSR** — `useTheme()` or similar resolving to
   different values pre-hydration.
3. **Browser-only state read at SSR** — `localStorage.getItem(...)` or
   `window.matchMedia(...)` returning placeholder during SSR.
4. **Random IDs in client components** — `useId()` mismatches if a child
   re-orders, or `crypto.randomUUID()` called during render.

These need a separate investigation wave. The cluster pattern (34 routes from
many unrelated areas) strongly suggests a **shared layout or provider**
(probably `<RootLayout>`, `<Providers>`, or `<Sidebar>`) is the SSR/client
divergence source — not 34 individual page bugs.

### Category C — Route-specific TypeErrors (cleanly captured but with errors)

| Route | Error | Likely root cause |
|---|---|---|
| `/admin/government-programs` | `Cannot convert undefined or null to object` at `Object.keys` | Component reading keys of an undefined config object — missing null guard. |
| `/admin/paysync` | `Cannot read properties of undefined (reading 'toLocaleString')` | KPI card formatting an undefined date/time — needs default value or null guard. |
| `/admin/paysync/bank-settlements/[settlementId]` | `m.reduce is not a function` | Component expects array, gets undefined or non-array. Same family as A3. |

These pages **still rendered** (screenshot exists) but threw a JS error. The
errors are real bugs — they indicate a missing-null-guard or wrong-shape
expectation. Production users would see a half-rendered page or an error
boundary in these spots.

## Triage classification

Per W5.5 plan: each finding → FIX-NOW | DEFER-TO-W6 | ACCEPT.

| Finding | Severity | Classification | Rationale |
|---|---|---|---|
| A1 (3 admin/network pages, shared chunk crash) | HIGH | **FIX-NOW** | Shared component breaks an entire route family. Easy fix once root cause is found. |
| A3 (`pay-to-entities/[entityId]`) | MEDIUM | **FIX-NOW** | Specific detail page crash. Same `t.map is not a function` family. |
| C (3 route-specific TypeErrors) | MEDIUM | **FIX-NOW** | Visible JS errors. Easy null-guard or default-value fixes per-route. |
| B (34 hydration #418 errors) | HIGH (volume) | **DEFER-TO-W6 follow-up wave** | Almost certainly a shared layout/provider issue. Single root cause, big blast radius. Needs its own investigation cycle (W5 was visual capture; this is JS architecture). |
| A2 (chain-membership, payments/batches/[id] hydration + timeout) | HIGH | Tracked under B — these timeouts are likely the worst case of the #418 problem | Same fix as B. |
| A4 (3 routes timeout with no JS signal) | UNKNOWN | **NEEDS-MORE-DATA** | Capture script doesn't log `console.warn` or HTTP response detail. Re-capture with extended capture before classifying. |
| Cancelled prefetches (3,488) | NOISE | **ACCEPT** | Normal Next.js link prefetch behavior. Allowlisted in §1. |

## Recommended next steps

1. **W5.6 closes with this finding doc + allowlist update.** Captures landed, triage done.
2. **W6 closeout work** can pick up the 6 FIX-NOW items (A1, A3, C) as targeted
   pre-ship fixes (they're surgical — null guards + array-checks).
3. **B10.1 / next wave: hydration audit.** The 34-route #418 cluster is its own
   wave. Likely a single shared-component fix (RootLayout / Providers / Sidebar)
   resolves all 34. But it needs proper investigation — not a W6 drive-by.
4. **W5.6.1 follow-up** (optional): extend `capture-w5-screenshots.ts` to also
   log `console.warn` and HTTP response codes per request. Will resolve the
   3 A4 routes' "timeout-with-no-signal" status.

## Comparison to W4 phase claims

The W4 phase verified portal "boots cleanly, /api/auth/providers lists b10-test,
positive/negative sign-in works, 95 backend routes mounted." Per STATE.md.

W5.6 shows: portal infrastructure is sound (auth works, mock layer works, 95%
of routes render). But **6 hard bugs + 34 hydration errors** were never
surfaced because nobody visited all 133 routes systematically. This is the
boomerang from W4's "boots cleanly" — true at the auth layer, false at the
visual layer for a third of the application.

This is why W5 exists.

## Cross-references

- `B10/w5-fixture-map.json` — W5.3 gate output
- `B10/w5-error-allowlist.md` — W5.5 allowlist (updated this session with prefetch carve-out)
- `B10/w5-capture-results.json` — full per-route capture data
- `B10/w5-screenshots/` — 125 PNGs
- `portal/operator/scripts/verify-w5-fixtures.ts` (commit `6cca5ab`)
- `portal/operator/scripts/capture-w5-screenshots.ts` (commit `0edbf02`)
- Werkbench overlay `waves/B10/STATE.md` — W5 multi-session plan
