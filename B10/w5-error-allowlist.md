# W5 Visual QA — Error Allowlist

**Wave:** B10  **Phase:** W5.5  **Generated:** 2026-05-12  **Branch:** `wave/B10-w5`

This document classifies console errors, page errors, and failed requests that
the W5.6 triage step will encounter when running
`portal/operator/scripts/capture-w5-screenshots.ts` against the operator portal
in `next start` mode with mock data enabled.

Three buckets:

- **§1 Global allowlist** — noise that applies to every route. Triage ignores.
- **§2 Per-family allowlist** — noise specific to particular route families.
- **§3 Hard FAIL** — always counts as a finding, never allowed.

The allowlist is **speculative** at W5.5 (written before W5.6 runs). After
the first capture run, anything not predicted here that turns out to be
benign gets added; anything predicted here that turns out to be a real bug
gets demoted to §3.

---

## §1 Global allowlist (applies to all routes)

| Pattern | Source | Why acceptable |
|---|---|---|
| Console warning: `[mock] unmatched: <METHOD> <path>` | `portal/shared/lib/mock-data/index.ts:53` | The mock layer logs a warning when it falls back to an empty shell for an unhandled endpoint. Routes typically call 5–15 endpoints; not all have explicit handlers. Mock layer returns `{items:[],total:0}` or `{}` — page renders an empty state, not a crash. |
| Network failed: `GET /api/auth/session 401` (single occurrence pre-auth) | NextAuth Credentials provider | Browser context fetches the session before our explicit sign-in completes. The capture script signs in once via `authenticateB10TestBypass` before any navigation, so post-auth /api/auth/session returns 200. A single 401 during the auth handshake is normal. |
| Network failed: `GET /api/auth/_log` (404) | NextAuth dev-mode logger absence | NextAuth's client-side error logger POSTs to `/api/auth/_log`; the endpoint only exists in dev mode. Under `next start` (production), 404 is normal. |
| Console warning: `Image with src "..." has either width or height modified` | Next.js Image component | Tailwind responsive image styling occasionally trips this. Visual is correct; warning is advisory. Acceptable while next/image isn't tightened. |
| Console warning: `Extra attributes from the server: data-darkreader-*` | Browser extension residue (only if test profile carries the ext) | Dark Reader and similar extensions inject attributes that cause hydration delta. Capture runs in a clean Playwright context so this should not appear; allowlisted defensively. |
| Console warning: `[Fast Refresh] rebuilding` | Next.js dev mode only | Will NOT appear under `next start`. Allowlisted only as defense if someone accidentally captures against `npm run dev`. |

## §2 Per-route-family allowlist

### `/admin/network/pay-to-entities/[entityId]` — placeholder route

- HTTP 404 from the detail page or its API calls is acceptable.
- Page should render a "not found" empty state, not a crash boundary.
- Console errors related to missing entity data are acceptable.

**Hard requirement:** page must render SOME content (heading or 404 layout),
not white-screen.

### `/admin/paysync/bank-settlements/[settlementId]` — placeholder route

Same shape as above. `paysync-api.getBankSettlement(settlementId)` will fail
at the mock layer; the route should fall back to a not-found view.

### `/admin/paysync/reconciliations/[reconId]` — placeholder route

Same shape. Reconciliations are per-cycle in the real API; the by-reconId
shape doesn't resolve in mock data. Empty-state allowed.

### `/admin/paysync/echo` and `/admin/paysync/email-templates`

If a route family relies on backend-only configuration (Echo Health
integration, SMTP template store), expect "no data" empty states. Network
failures on the underlying mock endpoints are §1-allowlisted as `[mock] unmatched`.

### `/analytics/*` routes — chart-heavy

- `recharts` console warnings about deprecated props (`SVGElement.tagName`)
  are acceptable. Chart library; not our code path.
- Initial chart render may log a `useLayoutEffect` warning in SSR
  pre-hydration — acceptable.

### `/reporting/library/[templateId]` and `/reporting/viewer/[reportId]`

- iframe-based report previews may fail to load source content under mock.
  Empty preview pane acceptable.
- `Content-Security-Policy` warnings for the iframe origin acceptable.

### `/edi/transactions/[id]` and `/edi/partners/[id]`

- EDI segment-rendering may log `key` warnings if the segment library uses
  index-based keys. Acceptable; not a behavior issue.

### `/api/auth/[...nextauth]` — EXCLUDED route

Not captured. The W5.3 classification marks this `exclude`; the capture
script skips it. Documented here for completeness.

## §3 Hard FAIL (always a finding)

These always count as a W5.6 finding regardless of route. No allowlist.

| Finding | Why hard-fail |
|---|---|
| `TypeError: Cannot read properties of undefined/null` | Indicates a missing field guard. Real bug. |
| `ReferenceError: X is not defined` | Indicates broken import or hoisting issue. Real bug. |
| `RangeError: Invalid time value` | Date parsing got a non-Date input. Real bug. |
| `SyntaxError` from JSON parsing | API contract violation or malformed mock data. Real bug. |
| Visible `[object Object]` text in rendered body | Stringification escape. Real bug. |
| Visible `undefined` or `null` text in rendered body | Missing guard or fallback. Real bug. |
| Visible `NaN` in numeric/currency display | Decimal/format path broken. Real bug. |
| HTTP 5xx on the page-load HTML response | Server error on the route itself. Real bug. |
| Playwright navigation timeout > 30s | Page never reached `networkidle`. Either real bug or §1 noise eating the budget. |
| White-screen / no `<h1>` rendered | Either crash boundary triggered or layout broken. Real bug. |
| React error #185 (suspending without boundary) | Suspense misuse. Real bug. |
| React error #418 / #423 (hydration mismatch with content) | Real hydration bug — content differs SSR vs client. |
| Failed request to `/api/auth/callback/b10-test` | Auth path broken. Real bug. |

## How W5.6 triage uses this doc

`B10/w5-capture-results.json` (written by W5.4) has per-route arrays:
`console_errors`, `page_errors`, `failed_requests`. The W5.6 step:

1. Group findings by route family.
2. For each finding, check against §1 (any match → ignore), then §2 (any
   route-family-scoped match → ignore), then §3 (any match → record as
   FIX-NOW).
3. Anything left over is **NEW SIGNAL** — surface to user. Either:
   - Promote to §3 (it's a bug → fix)
   - Add to §1 or §2 (it's benign noise → allowlist + document)

The allowlist is meant to be a LIVING document throughout W5.6 and W6. Every
W5.6 capture pass should result in at most one of:

- Empty new-signal set → §1/§2 fully covered the noise → W5 closes clean
- Small new-signal set → triage each, decide ALLOWLIST or FIX, repeat
- Large new-signal set → escalate to user; either app has real bugs or
  allowlist was too restrictive

## Open prediction risks

Items I'm guessing about; W5.6 will confirm:

1. **`next start` console verbosity differs from `next dev`.** Production
   mode suppresses many advisory warnings; the allowlist may be over-broad
   relative to actual W5.6 noise.
2. **`requestfailed` event vs `response` 4xx/5xx.** Playwright's
   `requestfailed` fires on transport-level failures (DNS, refused, aborted),
   not on 4xx/5xx responses. A 404 from `/api/auth/_log` may show up as a
   normal completed response, not a failed request — would need to inspect
   `page.on("response")` if we want to catch HTTP-level failures separately.
   Reserved as a W5.6 refinement.
3. **Tanstack Query retry behavior.** Initial render may issue multiple
   parallel requests; if retries trip on the first run, count multiplies.
4. **Hydration mismatch noise from B10 W4.6 absorption.** The W4.6 refactor
   changed auth module shape; if any client component imports the moved
   symbols incorrectly, hydration may diverge. Speculative — `tsc` passed,
   so static shape is fine.

## Cross-references

- `B10/w5-fixture-map.json` — W5.3 output, consumed by capture script.
- `portal/operator/scripts/verify-w5-fixtures.ts` — W5.3 gate.
- `portal/operator/scripts/capture-w5-screenshots.ts` — W5.4 capture.
- `portal/shared/lib/mock-data/index.ts` — mock layer (source of `[mock] unmatched`).
- `portal/shared/lib/auth-b10-test-bypass.ts` — auth path used by capture.
- `portal/operator/tests/fixtures/mock-session.ts` — analogous Playwright auth helper for dev-bypass.
- Werkbench overlay `waves/B10/STATE.md` — W5 multi-session plan.
