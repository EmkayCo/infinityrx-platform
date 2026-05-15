# SP-0 Decision Spike — Framework Decision v3

**Status:** v3 drafted 2026-05-15. v2 closed 4 of 7 pass-1 findings but pass-2 surfaced honest-evidence problems: wrong `randDelay` path, an "allowlisted" claim that contradicts the repo's actual allowlist (which classifies #418 as a real bug), and a root-cause attribution that conflicts with the W5 triage's actual hypotheses. v3 rewrites §3 to ground evidence in repo-primary sources, demote the external Werkbench claim to "one hypothesis among several," and show the decision holds under every candidate cause.

**Sub-decision 2 of 4 in the SP-0 spike.** Addresses the framework half of codex BLOCK #2 from the main SP-0 spec gate review. The gateway half is settled in sub-decision 3.

**Decision:** Stay on **Next.js (App Router + RSC)** for SP-0. Lock spine packages framework-agnostic. Schedule a candidate future SP-Framework-Migration *only* if defined tripwires trigger after SP-0 ships.

---

## v2 → v3 changes (codex pass-2 response)

| Pass-2 finding | v3 fix |
|---|---|
| PARTIAL BLOCK: evidence not fully repo-corroborated; `randDelay` path wrong; "allowlisted in §1" contradicts the actual allowlist; mock-data root cause not in W5 triage | §3 rewritten: repo-primary sources cited line-by-line; external Werkbench claim demoted to "one hypothesis"; W5 triage's five actual hypotheses included; correct `randDelay` path at `portal/shared/lib/mock-data/index.ts:17`; allowlist correctly summarized as classifying #418 as a real bug (not noise) |
| PARTIAL CONCERN: tripwires depend on SP-0 deliverables not yet shipped | §5: explicit "bootstrapping gap" subsection — pre-qa-harness signals are proxy-grade (manual Playwright sweeps + bug-tracker labels), full tripwires activate after SP-0's qa-harness lands. Decision is *commit-now*, *monitor-after* |
| PARTIAL CONCERN: thin-adapter BFF contract still "roughly" specified | §6: contract concretized — handler signature pinned, enforcement listed as concrete adoption items (lint rule referencing sub-decision 4, conformance test in `packages/auth/tests/` per sub-decision 1's pattern) |

## v1 → v2 changes (codex pass-1 response — retained for audit)

| Pass-1 finding | v2 fix |
|---|---|
| BLOCK: evidence base not auditable as cited | §3 grounds evidence in repo-internal `B10/w5-triage-findings.md`; quotes external STATE.md verbatim with provenance |
| BLOCK: artifact overclaimed "closes BLOCK #2" | §1 + §10: this handles the **framework half** only |
| CONCERN: tripwires not measurable | §5: thresholds and sources made concrete |
| CONCERN: portability leaks into module BFF handlers | §6: thin-adapter contract |
| CONCERN: `.env.local` mischaracterized | §3: removed |
| NIT: `next/auth` typo | fixed to `next-auth` |
| NIT: migration cost driver understated | §4: real drivers listed |

---

## 1. What this artifact decides (and what it doesn't)

The main SP-0 spec was circular in §10: the framework re-evaluation was the first SP-0 task, but its output reshapes the plan. Codex BLOCK #2 demanded the decision get settled *before* plan-writing, and bundled framework + gateway together.

This artifact settles **the framework half**: Next.js stays for SP-0, with concrete future-migration tripwires. The **gateway half** (whether to extract `packages/contract` into a standalone API gateway service now, given three confirmed portal consumers are coming) is settled in **sub-decision 3** of the same spike. BLOCK #2 closes when both sub-decisions are committed.

## 2. Candidates evaluated

| Option | Description | Migration cost (130 routes + adapters) | Eliminates hydration cluster? | Portfolio fit |
|---|---|---|---|---|
| **A. Stay Next.js (App Router + RSC)** | Current state. v16.2 in `portal/operator/package.json` | None | Partial — localized fixes per W5 triage's hypotheses address most causes; mock→real cutover (SP-0 work) addresses any data-timing component | Adequate; SSR/SEO unused; RSC tax is real but capped |
| B. Migrate to Vite + TanStack Start (SPA, optional SSR) | No RSC boundary | Real — weeks; drivers in §4 | Partial — eliminates the 3 SSR-specific candidate causes (date/time, theme, browser-only state); does NOT fix the 2 framework-agnostic candidate causes (random IDs, shared provider divergence) | Strong long-term; TanStack family heavily used |
| C. Migrate to Remix / React Router 7 | Server loaders, no RSC | Real, smaller than B | Same partial as A for SSR causes | Adequate |

## 3. Evidence base (repo-internal where possible; external claims marked)

### Primary evidence: `B10/w5-triage-findings.md` (repo-internal)

| Source line | Claim |
|---|---|
| `:14` | "Routes with React hydration error #418: 34" — measured in W5 visual-capture pass |
| `:84` | "Category B — React hydration error #418, 34 routes (32 captured cleanly + 2 also timing out)" |
| `:88-121` | "the hydration error happens, the page reconciles, and rendering completes" — visible-but-recoverable, not fatal |
| `:113` | **Five candidate root causes hypothesized** (verbatim, no specific component identified): date/time formatting during SSR · theme detection during SSR · browser-only state read at SSR · random IDs in client components · **shared layout/provider divergence** (`<RootLayout>`, `<Providers>`, `<Sidebar>`) |
| `:126` | "The cluster pattern (34 routes from many unrelated areas) strongly suggests a shared layout or provider is the SSR/client divergence source — not 34 individual page bugs" |
| `:154` | HIGH priority by volume, recommended for dedicated B10.1 audit |

### Primary evidence: `B10/w5-error-allowlist.md` (repo-internal)

`:102`: "React error #418 / #423 (hydration mismatch with content) — Real hydration bug — content differs SSR vs client." **Classified as a real bug, NOT allowlisted as benign.** This corrects v2's incorrect claim.

### `randDelay` actual location

Repo: `portal/shared/lib/mock-data/index.ts:17`. The mock-data layer simulates 80-250ms network latency. v2's claim that this lives in `portal/operator/lib/data/store.ts` was wrong — that file is a server-side cache/aggregation loader.

### External claim: B10.1 audit closeout (Werkbench-tracked, outside repo)

The B10.1 audit closeout at `~/Documents/Code Projects/Werkbench/projects/infinityrx-platform/waves/B10/STATE.md` (outside repo, outside codex's sandbox) claims:

> "34-route React #418 hydration cluster — reframed as timing-race non-determinism, not a real bug. Pages still render. Race depends on intersection of mock-data `randDelay` with React hydration window. Allowlisted in `B10/w5-error-allowlist.md` §1. Real elimination requires per-page Tanstack Query server-side prefetching — deferred."

**This external claim is not corroborated by the repo's primary evidence.** Two specific conflicts:

1. The allowlist (`B10/w5-error-allowlist.md:102`) classifies #418 as a real bug. The external claim says it was allowlisted as benign. These contradict.
2. The W5 triage (`B10/w5-triage-findings.md:113`) hypothesizes five candidate causes; none of them are mock-data `randDelay`. The external claim names mock-data timing as *the* cause.

Treat the external claim as **one hypothesis**, not adjudicated truth. Until a follow-up investigation pinpoints the actual cause, the framework decision must hold regardless of which hypothesis is right.

### Production-runtime corroboration

`waves/B10/w4-6-probe-results.md` (Werkbench-tracked) shows `next start` boots cleanly in 7s, all NextAuth providers register, end-to-end auth flow works at the protocol level. Whatever the hydration cluster is, it is not preventing the framework from running in production-mode at the runtime layer.

### The decision holds across all candidate causes

| Candidate cause | SSR-specific? (migration to pure-SPA fixes it) | Cheapest fix |
|---|---|---|
| Date/time formatting during SSR | Yes | Localized: `'use client'` on date components OR consistent server-side TZ formatting |
| Theme detection during SSR | Yes | Localized: client-only mounted theme provider with `useEffect`-deferred read |
| Browser-only state at SSR | Yes | Localized: `'use client'` on components reading `localStorage`/`window.matchMedia` |
| Random IDs in client components | No (framework-agnostic) | Use `useId()` correctly; avoid `crypto.randomUUID()` during render |
| Shared layout/provider divergence | No (framework-agnostic) | Localize divergence behind a client boundary |
| External claim: mock-data `randDelay` | No (cause-agnostic) | Eliminated automatically by SP-0's mock→real cutover |

Three of six candidates are SSR-specific and would be eliminated by Vite-SPA. The other three are framework-agnostic. **Under no candidate cause is migration the cheapest fix:** the SSR-specific causes are addressable with localized `'use client'` boundaries (hours of work per component), the framework-agnostic causes require the same localized fixes in any framework, and the external mock-data claim is fixed by SP-0's mock→real cutover regardless of framework. Migration costs weeks (§4); the localized fixes cost hours each.

## 4. Migration cost drivers (if A is ever reversed)

The actual cost of leaving Next.js concentrates in:

1. **Auth/session semantics.** `portal/shared/lib/auth.ts` (Auth.js v5 with 4 Credentials providers + jwt/session callbacks + dev-bypass + b10-test + refresh path) needs a non-Next.js adapter. The auth interface contract (sub-decision 1, `b876c3b`) is framework-agnostic; the *implementation* is Next.js-shaped.
2. **BFF adapter shape.** Next.js route handlers become whatever the target uses (TanStack Start API routes, Remix `action`/`loader`, etc.). Per the thin-adapter contract (§6), each module's BFF handler is already framework-agnostic; only the per-route adapter file changes.
3. **Route mounting and composition.** File-based routing maps cleanly. Module-package mounting (sub-decision 4) is framework-specific in its codegen.
4. **Cache behavior.** Next.js cache + Redis read-through reshapes into TanStack Query SSR/loaders or Remix loaders. Invalidation tag plumbing rewires.
5. **Test infrastructure.** Playwright stays; fixtures and the `qa-harness` package are framework-aware in cookie/session/route handling.
6. **`portal/shared/lib/`** currently carries Next.js + Auth.js assumptions per `portal/shared/README.md`'s `transpilePackages` note.

Bounded but real. Weeks of work for a competent team. Today's evidence doesn't justify spending it.

## 5. Tripwires (with explicit bootstrapping gap)

Stay-on-A is *not* permanent. SP-0 ships instrumentation that observes the framework's actual cost; if it crosses these thresholds, reopen the decision.

### Bootstrapping gap (honest about what exists today)

The full tripwires depend on SP-0 deliverables (`packages/qa-harness`, the `correlation_id` thread) that ship as part of SP-0 itself. **Pre-SP-0-shipping, the tripwires use proxy-grade signals only:**

- Manual Playwright console-error sweep (same shape as W5's `B10/w5-capture-results.json`) — captures `console_errors`, `page_errors`, `failed_requests` per route.
- Bug-tracker labels for `framework:rsc-boundary` and `framework:hydration` issues.
- `next dev --turbopack` HMR timing — captured manually when slowdown is noticed.

These are *crude* compared to the full instrumentation, but they exist today and produced the W5 finding that drove this decision in the first place.

### Tripwires (activate after qa-harness ships, full fidelity)

| Tripwire | Signal source (post-SP-0) | Threshold | Decision impact |
|---|---|---|---|
| Hydration #418/#419/#422 rate **post mock→real cutover** | `qa-harness` console-error stream + Playwright sweep | ≥2 distinct hydration-related routes per month, sustained over a quarter, after real-backend cutover for that domain | Open SP-Framework-Migration scoped review |
| Server/client boundary defects | Bug tracker label `framework:rsc-boundary` on any vertical-blocking issue | ≥1 vertical-blocking defect per quarter | Same |
| Dev-loop pain | HMR latency instrumentation in dev mode | Average HMR > 5s sustained over 2 weeks of active development | Same |
| Localized-fix-cost-exceeded threshold | When the cumulative `'use client'` / boundary fixes for hydration causes (per §3 table) exceed 1 engineering-week | When threshold crossed | Comparative cost vs. migration; if migration is cheaper, reopen |

## 6. What this decision pins for the SP-0 plan

| Pinned | Implication |
|---|---|
| Portal apps stay Next.js (App Router, v16.2) | Plan can use Next.js-specific patterns for the BFF host without hedging |
| BFF lives in Next.js route handlers (`app/api/`) | `packages/shell` hosts the route-handler infrastructure, mounted by module packages per main spec §5.1 |
| Auth stays on `next-auth` v5 (Auth.js) | `packages/auth` is the contract (sub-decision 1, `b876c3b`); next-auth is the adapter implementation |
| `packages/contract` / `auth` / `ui` / `qa-harness` MUST remain framework-agnostic | No `next/*` imports. Discipline enforced by a lint rule (sub-decision 4 will define it) |
| `packages/shell` MAY import Next.js | It's the framework adapter |
| `packages/modules/<name>` BFF handlers are framework-agnostic functions; **a thin Next.js route-file adapter per route** imports and invokes the handler | Migration touches adapters (≤5 lines each), not handlers |

### The thin-adapter BFF contract (concrete)

Every module's BFF route exports a pure handler function:

```ts
// packages/modules/<name>/src/bff/<route>.ts
import type { BFFRequest, BFFResponse } from "@infinityrx/portal-contract";

export async function handleSearch(req: BFFRequest<SearchInput>): Promise<BFFResponse<SearchOutput>> {
  // pure logic — no Next.js imports
}
```

The Next.js route file is a 3-5 line adapter:

```ts
// portal/operator/app/api/<module>/<route>/route.ts
import { handleSearch } from "@infinityrx/module-<name>/bff/<route>";
import { adaptNextRoute } from "@infinityrx/portal-shell/next-adapter";

export const POST = adaptNextRoute(handleSearch);
```

**Enforcement (concrete, not aspirational):**

- **ESLint rule** in `packages/contract/eslint.config.js`, `packages/auth/eslint.config.js`, `packages/ui/eslint.config.js`, `packages/qa-harness/eslint.config.js`, and `packages/modules/*/eslint.config.js`: forbid any `import` from `next/*`, `next-auth/*`, `@auth/*`. Defined in sub-decision 4 alongside the lint rule that forbids cross-module imports.
- **Conformance test** in `packages/modules/<name>/tests/bff-contract.test.ts`: imports the module's handler functions directly (no Next.js context), instantiates a fake `BFFRequest`, asserts the handler returns a valid `BFFResponse`. If the handler depends on Next.js APIs, this test fails at the module's own gate.
- **Per-module conformance** is part of the CI cross-composition matrix (main spec §9, sub-decision 4): a build with `["module-X"]` must pass that module's bff-contract test.

## 7. Out-of-scope (NOT decided here)

- Standalone API gateway extraction → **sub-decision 3** (gateway).
- Composition mechanism + tree-shaking + the no-`next/*` lint rule's actual config → **sub-decision 4** (composition). Codex's original BLOCK #1 is sub-decision 4's problem.
- Future migration target if A is reversed (Vite+TanStack vs Remix/RR7) → deferred until tripwire triggers.

## 8. Cross-references

- Codex pass-1 BLOCK #2 in `2026-05-14-sp0-integration-foundation-design.md`
- Codex pass-1 + pass-2 reviews of this artifact (in conversation; archived in spike history)
- Main spec §5.1 (Approach C — portable contract layer + Next.js BFF host)
- Sub-decision 1 outcome: `2026-05-15-sp0-decision-spike-auth-interface.md` (v4 committed `b876c3b`)
- `B10/w5-triage-findings.md` (repo-internal — 34-route #418 finding; five candidate root causes)
- `B10/w5-error-allowlist.md` (repo-internal — classifies #418 as real bug at line 102)
- `portal/shared/lib/mock-data/index.ts:17` (repo-internal — actual `randDelay` location)
- Werkbench-tracked `waves/B10/STATE.md` (external — B10.1 audit closeout, claim demoted to one hypothesis)
- `waves/B10/w4-6-probe-results.md` (Werkbench-tracked — `next start` runtime verified)
- `portal/operator/package.json` (Next.js 16.2, Auth.js v5, TanStack family, Radix, dnd-kit, cmdk)
- `portal/operator/next.config.ts` (migration touch site)
- `portal/shared/lib/auth.ts` (current next-auth implementation — migration touch site)
