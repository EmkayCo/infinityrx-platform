# SP-0 Decision Spike — Gateway Extraction Decision

**Status:** Drafted 2026-05-15. Sub-decision 3 of 4 in the SP-0 spike. Pending codex consult.
**Addresses:** Gateway half of codex BLOCK #2 from the main SP-0 spec gate review. With this committed, BLOCK #2 closes in full (framework half: `2026-05-15-sp0-decision-spike-framework.md`, sub-decision 2).
**Decision:** **Defer** gateway extraction. Keep `packages/contract` as a shared TypeScript package consumed by each portal's BFF (Approach C from main spec §5.1). Schedule a candidate future SP-Gateway-Extraction *only* if defined trigger conditions fire.

---

## 1. The decision being made

The main SP-0 spec brainstorming evaluated three topologies (§5.1):
- **A** — Next.js BFF as the spine (welded to one client)
- **B** — Dedicated API Gateway service (standalone service, language-agnostic)
- **C** — Portable typed contract layer + Next.js BFF host (shared package, extractable to gateway later) — *the locked decision*

Approach C was picked because, at brainstorm time, the portal was the only consumer of the spine. Codex BLOCK #2 then surfaced that the user's "client and provider portals coming" requirement means **three confirmed consumers** are coming, which weakens the "premature gateway" argument. The framework re-evaluation task (§10) was supposed to also decide whether to extract the contract layer into a standalone gateway now.

This artifact decides that question: **do we extract now, or stay as a package?**

## 2. What each shape delivers

| Capability | Shared TS package (Approach C, current) | Standalone gateway service (Approach B) |
|---|---|---|
| Single source of typed clients | ✅ via package import | ✅ via gateway endpoints |
| Cross-portal coherence (all 3 portals see same contracts) | ✅ they import the same package | ✅ they hit the same gateway |
| Auth contract enforcement | ✅ each BFF imports `packages/auth` | ✅ centralized at the gateway |
| Centralized rate limiting / telemetry / observability | Partial — each BFF must enforce; lint + contract tests are the discipline mechanism | ✅ centralized once |
| Language-agnostic consumers (mobile native, partner APIs, non-TS) | ❌ requires gateway to add | ✅ HTTP/JSON contract, any language |
| Operational burden | Zero new services | One new service to deploy/monitor/version/rollback |
| Latency | Direct BFF → backend HTTP | Extra hop: BFF → gateway → backend |
| Build/deploy independence per portal | Each portal builds its own (per per-client instance manifest) | Each portal builds + the gateway is a shared dependency that must be deployed first |
| Per-customer instance isolation | Each instance has its own BFF processes (per the dedicated-instance model) | Each instance also needs its own gateway service — multiplies the instance footprint |
| Cost to extract later from C | Bounded — pure refactor; `packages/contract` is already framework-agnostic, the gateway wraps it | N/A (already extracted) |

## 3. Why defer wins for SP-0

### The shared package satisfies "three confirmed consumers"

The "premature gateway" argument was: "you only have one consumer today." Codex was right to push on that — three are coming. **But the gateway's central value over a shared package is *language-agnostic consumers*, not just *multiple consumers*.** All three confirmed portals (operator, client, provider) are TypeScript/Next.js apps that can import the same shared package.

A gateway delivers value when:
- A *non-TypeScript* client needs the backends (mobile native iOS/Android, partner API integrations, embedded device clients).
- Cross-cutting concerns *cannot* be enforced via per-portal-BFF discipline + CI.
- Versioning the contract becomes a coordination problem across portals (would require a publish/deprecate workflow).

None of these are true today. All three are future-conditional.

### Per-customer instance economics

The dedicated-instance deployment model (main spec §5.3) compounds the gateway's operational cost. A gateway service deployed *once* in a shared SaaS model is one new service. A gateway service deployed *per customer instance* is N new services — one per InfinityRx customer. That's a real ops multiplier.

The shared package adds zero per-customer-instance services.

### Foundation-phase risk discipline

SP-0 is the foundation. Adding a new standalone service *during* the foundation build:
- Adds a single point of failure on the integration path the rest of SP-0 depends on.
- Adds deployment ordering complexity (gateway must be live before any portal route works).
- Adds an entire deploy/monitor/version surface to the SP-0 plan that wasn't scoped in.

The package shape has zero of that risk. The gateway shape can be extracted *after* SP-0 ships, with the contract package as the basis.

### Extraction-later is bounded

`packages/contract` is framework-agnostic by sub-decision 2's mandate (no `next/*` imports, enforced by lint). A future gateway service is mechanical to build *because* of that: it wraps the same typed clients in HTTP route handlers, exposes the contract as endpoints, and each portal's BFF becomes a thin HTTP client of the gateway instead of a direct package consumer.

Migration cost from package → gateway, when triggered: similar to the framework-migration estimate (weeks), but bounded to BFF wiring + adding one new service. The verticals don't change.

## 4. Trigger conditions to revisit

Defer is *not* permanent. Reopen the gateway extraction decision when any of these fire:

| Trigger | Signal | Decision impact |
|---|---|---|
| **First non-TypeScript client needs the backends** | A mobile native app (iOS Swift, Android Kotlin) is scoped, OR a third-party partner integration is signed that needs to call backend APIs directly | Open SP-Gateway-Extraction immediately — the package can't serve a non-TS client |
| **Contract-package versioning becomes a coordination problem** | A schema change needs to land in operator before client/provider, OR backwards-incompatible contract changes need a publish/deprecate flow across N portal repos | Open SP-Gateway-Extraction — the gateway centralizes the contract surface so portals consume by endpoint, not by package version |
| **Cross-cutting concerns can't be enforced via per-BFF discipline** | Rate limiting / observability / cost attribution / per-customer billing instrumentation needs to be enforced in *one* place that the portals can't bypass | Open SP-Gateway-Extraction — gateway becomes the choke point |
| **Backend tokens need to be validated by a non-portal source** | A non-portal service (a scheduled job runner, a partner webhook receiver, etc.) needs to validate JWTs against the same contract | Open SP-Gateway-Extraction — gateway absorbs token-validation as a shared service |
| **Operational pain from N portal BFFs deploying independently** | Coordinating contract changes across 3 portal deploys becomes ≥1 incident per quarter | Open SP-Gateway-Extraction — single gateway deploy replaces N portal-BFF deploys for contract changes |

None of these are visible today.

## 5. What this decision pins for the SP-0 plan

| Pinned | Implication |
|---|---|
| `packages/contract` is a shared TypeScript package, not a service | Plan scope: build a package, publish to internal registry (or workspace), import from `portal/operator` |
| Each portal app embeds the package in its own BFF route handlers | Plan scope: BFF route handlers live in `packages/modules/*/src/bff/*.ts`, mounted by shell in `portal/operator/app/api/...` per framework decision (sub-decision 2) |
| Auth/rate-limit/telemetry/observability enforced per-BFF, gated by contract tests + lint rules | Plan scope: contract tests in each portal app's CI assert each BFF route correctly enforces auth/cache/rate-limit per the contract's policy data |
| No new service in the SP-0 deployment topology | Plan scope: SP-0 deploys = the operator portal Next.js app + the 13 backend services + Redis + Postgres. No gateway service |
| Future SP-Gateway-Extraction is a candidate roadmap item, not committed work | Roadmap implication: gateway is a *triggered* SP, not a sequenced one |

## 6. Closing original BLOCK #2

The main spec's codex BLOCK #2 was: "framework + gateway decisions are too late for plan-writing." With:

- **Sub-decision 2** (framework half) committed `14d847a`: stay Next.js, framework-agnostic spine, tripwires defined.
- **Sub-decision 3** (gateway half, this artifact): defer gateway extraction, contract stays as a shared package, trigger conditions defined.

…both halves of BLOCK #2 are now settled before plan-writing. The SP-0 plan can be written honestly.

## 7. Out-of-scope (NOT decided here)

- The exact `packages/contract` API surface (which client functions exist, what they return) — that's main spec §6.1 + the verticals (SP-1+).
- The composition mechanism + tree-shaking + per-module BFF mount details — **sub-decision 4** (composition).
- Future gateway technology choice if triggered (FastAPI, Bun, Cloudflare Workers, Envoy-as-config, etc.) — deferred to SP-Gateway-Extraction when it opens.

## 8. Cross-references

- Codex pass-1 BLOCK #2 in `2026-05-14-sp0-integration-foundation-design.md`
- Sub-decision 2 outcome: `2026-05-15-sp0-decision-spike-framework.md` (v3, committed `14d847a`)
- Sub-decision 1 outcome: `2026-05-15-sp0-decision-spike-auth-interface.md` (v4, committed `b876c3b`)
- Main spec §5.1 (Approach C, the locked topology)
- Main spec §5.3 (per-customer dedicated-instance deployment model — the economics-multiplier for gateway-per-instance)
- Main spec §6.1 (packages/contract responsibilities)
