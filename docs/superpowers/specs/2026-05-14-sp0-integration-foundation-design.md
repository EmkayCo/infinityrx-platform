# SP-0 — Integration Foundation & Stabilization

**Status:** Brainstormed; pending codex spec review at the gate before plan-writing.
**Date:** 2026-05-14
**Owner:** Mike
**Sub-project of:** Operator Portal & Platform Frontend milestone (decomposed 2026-05-14)
**Replaces:** —

---

## 1. Problem statement

The InfinityRx operator portal has ~130 routes scaffolded across 15 domains (accounting, admin/paysync, analytics, billing, claims, clients, directories, edi, medical-claims, network, payments, programs, reclaimrx, reporting, settings). The Next.js app launches, you can click through it — but only ~4 of the ~13 backend modules are actually wired (per `.env.local`: prescriber-directory, pharmacy-directory, drug-database, core-platform), and even those backends are not reliably running. The rest of the portal is mock data.

The user's framing: *"We have a good skin, but the functionality is just not there."*

Beyond the immediate operator-portal gap, the system is intended to become a **portfolio**: more backend modules will land, **client portals** and **provider portals** will be added, and **medical EDI** is yet to be built. Each module needs to work both **coherently** (when combined into a full platform) and **independently** (sold as a standalone product a customer can purchase on its own). When a customer purchases the platform — full, partial, or standalone — they get their own **dedicated environment and instance**, not a slice of a shared multi-tenant production plane.

SP-0 closes the gap between today's skin-without-spine state and a foundation that supports the portfolio future.

---

## 2. Goals

1. Deliver a **reusable integration spine** every vertical builds on (the frontend↔backend contract, BFF, caching, backend health/run story, test harness).
2. Make the existing portal **usable and testable** in the project's full sense — automated coverage + a manual QA harness.
3. Establish the **canonical end-state auth/token contract**. B12's tactical shim work folds into this; SP-0 owns the final answer.
4. Define the **per-client deployment composition mechanism** — how a customer's purchased module set becomes a deployable instance.
5. Establish the **performance posture**: interactive surfaces lightning-fast (<150ms transitions, <100ms search-as-you-type even on 7M-record tables); heavy analytical/report pages get fast first paint + honest loading states.
6. Establish the **testing posture**: automated CI coverage (per project gates) + manual QA harness for human verification.

## 3. Non-goals (explicitly out of SP-0)

- Building the **client portal** or **provider portal** applications (future SPs).
- Building any vertical's full UI (SP-1…SP-5 cover those).
- Building the **no-code program designer** (SP-6).
- Migrating backend services or database schemas.
- Performance benchmarking and load testing.
- Visual regression testing, mutation testing.
- Building **medical EDI** (separate track, future SP).

---

## 4. Locked decisions (brainstorming output)

| # | Decision | Choice |
|---|---|---|
| D1 | Center of gravity | Architecture spine first |
| D2 | Performance bar | Interactive surfaces lightning, heavy pages honest first-paint + loading states |
| D3 | Testable bar | Both automated coverage AND manual QA harness |
| D4 | Auth scope line | SP-0 owns the canonical end-state auth/token contract; B12 stops the bleeding tactically |
| D5 | Topology | Approach C — portable typed contract layer + Next.js BFF host (framework-agnostic spine, hosted by Next.js for now) |
| D6 | Module independence | Commercial/product separability: modules sellable as standalone products |
| D7 | Deployment model | Per-customer dedicated environment + instance; composition happens at build/deploy time, not runtime entitlements gating |
| D8 | Portal audiences | Three per instance: operator (ops staff), client (plan-sponsor clients, scoped to their data), provider (pharmacies/prescribers) |
| D9 | Framework re-evaluation | Next.js is kept for SP-0; a **formal re-evaluation is an explicit early SP-0 task** with portfolio criteria, real hydration-bug data, and a codex consult. The re-eval also decides whether to extract the contract layer into a standalone gateway now that three portal consumers are confirmed |

These decisions are inputs to the plan; if any are revisited, this spec must be revised first.

---

## 5. Architecture

### 5.1 Two layers, two cross-cutting deliverables

**Layer 1 — `packages/contract` and siblings (the portable spine).**
Framework-agnostic TypeScript packages. Zero Next.js imports. This is the spine. Verticals "build on the spine" literally — they `import` these packages.

**Layer 2 — Next.js BFF host (`portal/operator`).**
The portal's server layer (Next.js route handlers and server components) consumes the contract package: instantiates clients with real config, owns server-side caching (Next cache + Redis read-through per the contract's declared policy), injects auth tokens, exposes the BFF routes the React frontend calls. The frontend **never** calls backends directly. `proxy.ts` stays as the auth-gate edge.

**Cross-cutting deliverable A — Backend run/health story.**
Standardized `/health` on every backend, a `services-health` aggregator BFF route, `docker-compose` orchestration that brings all 13 backends up cleanly with one command. Solves "backends not reliably running."

**Cross-cutting deliverable B — Test harness.**
Automated test pyramid + the `qa-harness` package usable in dev mode in any portal.

### 5.2 Repo structure

```
portal/
  packages/
    contract/     ← backend clients, cache policy, mock/real toggle, health   (shared)
    auth/         ← canonical auth/token contract                              (shared)
    ui/           ← design system + components → portals look coherent         (shared)
    qa-harness/   ← manual QA harness toolkit                                  (shared)
    shell/        ← thin portal host: routing, auth, layout, module mounting   (shared)
    modules/
      reclaimrx/  ← self-contained feature-package: routes, components,
      paysync/        contract-client usage, tests, BFF route handlers,
      claims/         module.config.ts — the composition unit
      billing/
      directories/
      ...
  operator/       ← FULL composition (shell + all module packages) — dev target + reference
  client/         ← FUTURE SP: thin app for plan-sponsor audience
  provider/       ← FUTURE SP: thin app for pharmacy/prescriber audience
```

The existing `@infinityrx/portal-shared` is the seed of the shared-package pattern; SP-0 either grows it into this shape or starts new packages alongside (decision at plan time).

### 5.3 Per-client instance composition (the "modules as products" mechanism)

A **deployment manifest** per customer instance declares the modules included:

```json
{ "modules": ["reclaimrx", "paysync"] }
```

At build time, the build reads the manifest, the shell imports only the listed module packages, their routes register, their BFF handlers mount, their contract clients initialize. Modules **not** in the manifest are tree-shaken out — their code, routes, BFF handlers, contract clients all absent from the built artifact. A standalone-ReclaimRx instance ships zero PaySync code.

Operator portal in dev = manifest with all modules. Standalone-product instances = subset.

### 5.4 Three portal audiences per instance

Within any one customer instance:
- **Operator portal** — the customer's ops staff, running their PBM business.
- **Client portal** — the customer's plan-sponsor clients, scoped to **their** book of business via the existing `tenant_id` isolation (defense-in-depth on top of the dedicated-instance separation).
- **Provider portal** — pharmacies and prescribers interacting with the customer's environment.

All three apps compose from the same shared packages (coherent); each is independently built/tested/deployed (independent). SP-0 builds only the operator portal as first consumer; client and provider portals are future SPs that slot into this structure.

---

## 6. Components

### 6.1 `packages/contract`

Owns the entire frontend↔backend contract surface.

- **Typed backend clients** — one per backend service (~13: prescriber-directory, pharmacy-directory, drug-database, core-platform, billing, payment-processing, reclaimrx, reporting, dataiq, ai-nlp, member-management, edi-compliance, medical-claims).
- **Mock/real toggle** — each client has a `RealImpl` + `MockImpl` behind a common interface; config selects which, per-domain.
- **Cache policy** — declarative per-resource: TTL, cache key, invalidation tags, behavior on backend-down (`stale-ok` | `fail-fast` | `fall-back-to-mock`). Consumed by the BFF's cache adapter.
- **Error envelope** — `{error:{code, message, field?, correlation_id}}` per `.claude/rules/error-handling.md`. zod-validated at the boundary.
- **Request/response schemas** — zod schemas shared with backend contract docs.
- **Telemetry hooks** — tracing/logging integration points.
- **Health model** — per-backend probe definition feeding the `services-health` aggregator.

### 6.2 `packages/auth`

Owns the canonical end-state auth/token contract (D4). **B12's `_shim/auth` refactor (B12 S1) and b10-test JWT minting (B12 S3) fold here once B12 lands its tactical fixes.**

- JWT shape and claims (`tenant_id`, `user_id`, `scopes`, `module_entitlements`), expiry, refresh model.
- Token mint and validate primitives — single source shared with backend's JWT secret.
- MFA gate contract (per `.claude/rules/hipaa-2026.md`).
- Session model (timeout, concurrent-session limits per `.claude/rules/hipaa-2026.md`).
- Dev-JWT path (the `mintDevJwt` currently in `portal/operator`, formalized here).

### 6.3 `packages/ui`

The shared design system. Built on the existing stack (Radix UI, shadcn primitives, dnd-kit, recharts, react-hook-form + zod, TanStack Table, TanStack Virtual).

- Component library.
- Page shells, navigation primitives, command palette host (the existing `cmdk` integration).
- **dnd-kit primitives — the foundation for the future no-code program builder (SP-6 builds on these; SP-0 ships the primitives, not the builder).**
- Chart, table, form wrappers.
- Design tokens (colors, spacing, typography) so the three portals look coherent.

### 6.4 `packages/qa-harness`

The manual QA harness, usable in dev/staging builds of any portal; omitted from prod builds.

| Tool | What it does |
|---|---|
| QA mode toggle | Portal renders with visible "QA MODE" chrome; non-prod only |
| Request/response inspector | Per-page overlay: route, timing, payload, headers, cache hit/miss, mock-or-real, the backend that served it |
| Health dashboard | Live state of all backends (from `services-health`) — green/yellow/red per service, last response time, last error |
| Mock/real toggle per domain | UI to flip any single backend client between real and mock at runtime — without redeploying |
| Module composition viewer | "This build contains: reclaimrx, paysync, directories" — proves the deployment manifest produced the expected artifact |
| Test data factory bindings | Buttons to seed safe, non-PHI fixtures into the dev DB ("seed: 1 tenant + 10 prescribers + 5 claims, B1 paid") |
| `correlation_id` quick-jump | Copy current request's correlation_id; open matching backend log entry in one click |

### 6.5 `packages/shell`

Thin host. Owns:
- App-level routing and layout.
- Auth integration (consumes `packages/auth`).
- **Module registration and mounting** — modules register their routes via `module.config.ts`; shell composes them.
- Top nav and navigation tree built from registered modules.
- Cross-cutting UI (toasts, error boundaries, the command palette host).
- BFF route handlers — Next.js `app/api/` route handlers that consume `packages/contract`. **Module-owned BFF routes live with the module package** and are mounted by the shell.

The shell is deliberately small. It composes; it doesn't do features.

### 6.6 `packages/modules/<name>`

Each module is a vertical product slice:
- Routes (the page tree for the module).
- Components (module-specific UI, importing from `packages/ui`).
- Hooks (data fetching via TanStack Query backed by contract clients).
- Tests (unit, integration, contract).
- **A `module.config.ts`** exporting metadata: name, routes, nav entry, required backends, required entitlements.
- **The module's portion of the BFF** — its `app/api/<module>/...` route handlers, owned by the module package and mounted by the shell.

When a module is omitted from the deployment manifest, its routes, components, hooks, BFF handlers, and contract-client wiring all vanish from the built artifact.

### 6.7 Portal apps (`portal/operator`, future `client`, `provider`)

Each is a thin Next.js (today) app:
- Imports `packages/shell` + the module packages listed in its deployment manifest.
- App-level config: audience scope (operator/client/provider), branding, auth profile.

`operator` is the dev target and the reference full composition (all modules). `client` and `provider` are **not built in SP-0**; SP-0 only establishes the structure so they slot in cleanly.

### 6.8 Backend run/health story (cross-cutting infrastructure)

- Standardized `/health` endpoint on every backend service (matches the project's existing health-check patterns).
- `services-health` aggregator route in the BFF — fans out to each backend's `/health`, aggregates, returns a status snapshot.
- `docker-compose.yml` orchestration that brings all 13 backends + Postgres + Redis up cleanly with `docker compose up`. Drives backend reliability for dev, CI, and the qa-harness dashboard.

### 6.9 Test harness (cross-cutting infrastructure)

See Section 9 for the full testing model. Concretely SP-0 delivers:
- **Pillar 1** — Automated test pyramid: unit, contract, integration, E2E suites with the project's existing coverage gates (100% on auth/security/financial/PHI paths; 99% branch elsewhere).
- **Pillar 2** — The `packages/qa-harness` package (see §6.4).

### 6.10 The deployment manifest

A small declarative file per customer instance:

```json
{
  "instance_name": "customer-acme-prod",
  "modules": ["reclaimrx", "paysync"],
  "audience": "operator",
  "auth_profile": "production",
  "branding": { ... }
}
```

Tracked in the project's existing environment-config pattern (alongside `.env.dev`, `.env.mock`, `.env.prod`). The build system reads it to compose `shell + selected module packages + their backend services + their DB schemas` into the deployable artifact for that customer's instance.

---

## 7. Data flow

### 7.1 Canonical request — prescriber lookup (the perf-critical path)

```
User types in search box   (operator portal — directories module page)
        │
        ▼
TanStack Query hook        usePrescriberSearch(q)   ← in packages/modules/directories
        │
        ▼
GET /api/directories/prescribers/search?q=...
        │
        ▼
BFF route handler          ← lives WITH the module package, mounted by shell into app/api/
   • unpacks auth context from packages/auth: { tenantId, userId, scopes, moduleEntitlements }
   • entitlement guard: this instance has 'directories' enabled?
   • cache lookup per contract's declared policy (Next cache / Redis read-through)
        │ miss
        ▼
Contract client            prescriberClient.search({ tenantId, query })   ← from packages/contract
   • zod-validate request
   • inject Bearer token per the canonical auth contract
   • HTTP → prescriber-directory FastAPI (:8010)
   • zod-validate response  →  typed result OR structured error envelope
        │
        ▼
BFF writes to cache (if cacheable) → returns to client
        │
        ▼
TanStack Query caches client-side → component renders virtualized list
```

**Performance sources on this path:** zod-validated typed payloads (no shape surprises), declared cache policy hitting Redis on the BFF, TanStack Query client cache + dedup, `react-virtual` rendering. Cache hits are zero-roundtrip; result updates don't full-re-render.

### 7.2 Auth token flow

Login (operator portal) → `next-auth` issues canonical JWT per `packages/auth` contract (mint primitives shared with backend) → token in httpOnly cookie → every BFF request `proxy.ts` extracts/validates → BFF forwards as `Authorization: Bearer …` to backend → backend validates against the same shared JWT secret. **One contract definition, one mint/validate primitive, used in three places — `packages/auth` is the single source of truth.**

### 7.3 Cache + invalidation

Reads consult the cache per the contract's declared policy (TTL, cache key, tags). Writes (mutations) go through the contract client too; on success the client emits **invalidation tags** — the BFF cache subscribes and purges matching keys, and the mutation hook tells TanStack Query to refetch dependent queries client-side. Cache stampedes on big-data lookups (the 7M-prescribers case) are handled by single-flight in the contract client.

### 7.4 Mock/real toggle

Per-domain config (per module, set in the deployment manifest or env) selects between `RealImpl` and `MockImpl` of each backend client *at the contract layer*. Everything above the contract is identical in both modes — same hook, same BFF route, same cache. Switching one module to mock doesn't affect any other. The qa-harness exposes this toggle at runtime in dev.

### 7.5 Build-time composition

```
Deployment manifest  →  { "modules": ["reclaimrx", "paysync"] }
        │
        ▼
Build reads manifest  →  shell imports listed module packages only
        │
        ▼
   Module packages' routes register
   Module packages' BFF handlers mount
   Module packages' contract clients initialize
   Module packages' nav entries appear
        │
        ▼
Modules not in manifest are tree-shaken out — their code, routes,
BFF handlers, contract clients all absent from the built artifact
```

That is the "customer buys just ReclaimRx" mechanic, concretely: tree-shaking against a declarative manifest, no runtime entitlements gating, no dead code shipped to a standalone customer.

---

## 8. Error handling

### 8.1 Error envelope

Existing project standard (`.claude/rules/error-handling.md`), lives in `packages/contract`:

```ts
{ error: { code: string, message: string, field?: string, correlation_id: string } }
```

HTTP status mapping is the existing project standard (400/401/403/404/409/422/429/500). The envelope is zod-validated at every layer boundary.

### 8.2 Categories and ownership

| Category | Where detected | Where handled |
|---|---|---|
| **Auth failure** (expired/invalid token) | `packages/auth` middleware on BFF | Redirect to login, clear session, preserve callback URL |
| **Entitlement failure** (module not in this instance) | Module guard in BFF route | Typed `ModuleNotAvailable` → friendly empty state, not a 403 page |
| **Validation failure** (bad request) | zod at contract boundary (both directions) | Field-level error returned to form, component shows inline |
| **Backend unavailable** (connect refused, 5xx, timeout) | Contract client | Per cache policy: stale-while-revalidate if available; else `BackendUnavailable` error with backend name surfaced in qa-harness |
| **Internal / unexpected** | Anywhere | Caught by module's error boundary; full context logged server-side; user sees `correlation_id`, never a stack |

### 8.3 Backend-down resilience modes

Declared per-domain in the cache policy:
- **`stale-ok`** — serve cached data with a soft "data may be outdated" banner. Staleness-tolerant reads (drug lookups, reference data).
- **`fail-fast`** — return `BackendUnavailable` immediately. Mutations, money paths.
- **`fall-back-to-mock`** — contract switches to its mock impl for this request only, surfaces a visible "mock data shown — [backend] is down" banner in dev/QA. **Off in production.**

The `services-health` aggregator + qa-harness health dashboard make backend-down state observable, not invisible.

### 8.4 Module-scoped error boundaries

Each module package mounts its routes inside its own React error boundary in the shell. A broken module renders a contained "this module has an error — `correlation_id` ABC" panel; **the rest of the portal stays alive**. This is the "coherent + independent" guarantee at the failure level — ReclaimRx going sideways cannot take down PaySync's screens.

### 8.5 `correlation_id` thread

Every BFF route mints (or accepts from headers) a `correlation_id`, attaches to the contract call, forwards to backend, logs at every layer with structured `{correlation_id, tenant_id, user_id, module, action}` — subsystem-prefixed keys per LESSON-005. Errors surfaced to the user always include it; qa-harness exposes a one-click "copy + open the matching backend log entry."

### 8.6 PHI safety in errors

Error messages are pre-classified by the backend (`safe_user_facing` vs `internal_only`) — only `safe_user_facing` ever reaches the envelope. The envelope is zod-validated at the contract boundary; PHI-shaped fields (per `.claude/rules/phi-compliance.md`: name, DOB, SSN, address, phone, email) are stripped if they somehow appear. Contract-layer guard *and* a backend rule — defense in depth, matches the project's HIPAA 2026 posture.

### 8.7 UX policy

| Severity | UX |
|---|---|
| Validation (field) | Inline under the field, blocks submit |
| Validation (form) | Top-of-form banner, blocks submit |
| Recoverable (backend-down, transient) | Toast + retry button + `correlation_id` in toast detail |
| Module-fatal | Module error boundary panel (rest of portal alive) |
| Auth/session | Modal or redirect to login |

### 8.8 Retry policy

Idempotent reads auto-retry once on 5xx/network with backoff (in the contract client). **Mutations never auto-retry** — the user retries with the original `correlation_id` so server-side idempotency keys work. Rate-limited (429) requests respect `Retry-After`.

### 8.9 Dev/QA vs production visibility

qa-harness shows full error context: request, response, headers, timing, the backend that failed, the cache state, the mock/real flag. Production strips internal context — users see code, message, `correlation_id`, no stack.

---

## 9. Testing

### 9.1 Pillar 1 — Automated test pyramid

| Layer | What's tested | Where it lives | When it runs |
|---|---|---|---|
| **Unit** | Pure logic in shared packages: auth token mint/validate, cache policy resolution, error envelope assembly, zod schemas, mock impls themselves | Co-located: `packages/<name>/tests/` | Every PR (fast) |
| **Contract** | Each typed client in `packages/contract` against a real backend (or its declared mock) — verifies the contract still holds | `packages/contract/tests/contract/` | Every PR (fast; requires docker-compose backends up) |
| **Integration** | BFF routes through the full stack: shell + module package + contract → real backend → DB. Applies **LESSON-006** at the portal layer — every BFF route exercised via the real app factory, never via fixture-only paths | Per module: `packages/modules/<name>/tests/integration/` | Every PR (medium) |
| **E2E** | Playwright through a real portal app: real auth, real backends (docker-compose), real DB. The qa-harness mode also runs in this stack so the QA tooling itself is tested | `portal/operator/tests/e2e/` (existing Playwright config) | PR + pre-merge (slowest) |

### 9.2 Coverage gates

Apply existing project policy unchanged:
- `packages/auth`, `packages/contract` (auth/error/security paths), any module touching money (paysync, billing, claims) → **100%**.
- All other active code → **99% branch**.
- Excluded: unimplemented module placeholders (per existing `pyproject.toml` pattern, mirrored in portal package configs).

### 9.3 Pillar 2 — `packages/qa-harness`

Detailed in §6.4. SP-0 ships the package; each portal includes it in dev/staging builds and omits in prod.

### 9.4 Test data strategy

| Need | Source |
|---|---|
| Unit tests of frontend logic | The contract layer's **mock impls** (zod-validated, shape-faithful to real) |
| Contract/integration/E2E tests | **Real backends via docker-compose**, seeded with synthetic non-PHI data via factory fixtures |
| Manual exploration / dogfooding | qa-harness test data factory bindings + mock toggle |
| Performance reality-check (7M-record paths) | Deferred to the directories vertical (SP-1) — not in SP-0 |

**No PHI in test data, ever** — synthetic data factories per `.claude/rules/phi-compliance.md`. Tests that need claims/members generate them at runtime.

### 9.5 CI integration

- **Per-PR (fast lane):** lint, type-check, unit tests, contract tests against docker-compose backends.
- **Per-PR (medium lane):** integration tests through the BFF.
- **Pre-merge (slow lane):** Playwright E2E + coverage report against the existing auto-gate.
- **Cross-composition matrix:** representative deployment manifests build + smoke-test in CI — at minimum `["all"]` (operator full), `["reclaimrx"]` (standalone), and one minimal subset — proves the composition mechanic actually works.

### 9.6 Explicitly NOT in SP-0

Load/perf benchmarking, visual regression, mutation testing. They become their own efforts later. SP-0 ships the test harness and the coverage gate; perf benchmarking comes when verticals hit the 7M-record paths for real.

---

## 10. Early SP-0 internal task: framework re-evaluation

Per D9, the first internal task within SP-0 execution is a formal framework re-evaluation. Criteria are now **portfolio-level**, not single-app:

- **Real data inputs:** measured hydration-bug rate in the existing portal (B10.1 audit, B12 S7 login hydration mismatch, the `.env.local` notes about RSC); RSC complexity tax; build/dev-loop times.
- **Portfolio fit:** the chosen framework must serve operator + client + provider portals coherently, support per-customer build-time composition, and support tree-shaking of unused module packages.
- **Codex consult** required (Werkbench L3 decision-gate policy).
- **Gateway decision:** with three confirmed portal consumers, the re-evaluation must explicitly decide whether to extract the contract layer into a **standalone API gateway service** (Approach B from brainstorming) *now*, or defer.
- Candidates to evaluate: Next.js (current), Vite + TanStack Router/Start as SPA + thin BFF, Remix/React Router 7.

Outputs of this task feed back into the SP-0 plan before further structural work commences.

---

## 11. Scope discipline

SP-0 builds:
- The shared packages (`contract`, `auth`, `ui`, `qa-harness`, `shell`).
- The first portal app (`portal/operator`) as the reference consumer / dev target.
- **One reference module package** scaffolded end-to-end (proposed: ReclaimRx, since it's already a working backend with rich behavior) — proving `module.config.ts`, BFF route mounting, contract-client usage, mock/real toggle, tests, and tree-shaking against the composition manifest all work. SP-1…SP-5 create their own module packages following the established pattern; SP-0 does **not** pre-scaffold all 13.
- The deployment manifest mechanism + CI cross-composition matrix exercising `["reclaimrx"]` standalone vs `["all"]` operator-full vs one minimal subset.
- Backend run/health story + standardized `/health` + `services-health` aggregator.
- The test harness (both pillars).
- The framework re-evaluation outcome (§10).

SP-0 does **not** build:
- Client or provider portal apps.
- Any vertical's full UI.
- The no-code program designer.
- Medical EDI.
- Performance benchmarking infrastructure.

---

## 12. Open questions / known unknowns

These are unresolved or deferred to plan time / future SPs. The codex spec-review gate (§13) is expected to surface more.

1. **Framework re-evaluation outcome.** Whether SP-0 stays Next.js or migrates to a Vite-SPA shape. Resolved by the §10 task before further plan work commences.
2. **Gateway extraction timing.** Whether the contract layer becomes a standalone API gateway in SP-0 or after the second portal consumer materializes.
3. **Boundary with existing `@infinityrx/portal-shared`.** Does SP-0 grow that package into the proposed structure, or start new packages alongside? Determined at plan time.
4. **Per-domain cache TTLs and invalidation tag designs.** Declared as data in `packages/contract`; concrete values set during the verticals (SP-1+) — SP-0 ships the *mechanism*.
5. **Module entitlement claim shape in the JWT.** Build-time composition handles the "what's deployed" question; whether runtime auth-claim entitlements add anything (e.g., for sub-tenant feature flags within a customer's instance) is open.
6. **Deployment manifest schema details.** Beyond `{modules: [...]}`, what else does it carry — branding, audience, auth profile, backend endpoints? Plan time.
7. **Where the standalone product's branding lives.** Per-instance branding likely lives in the deployment manifest; whether `packages/ui` exposes a theme contract or each module brings branding hooks is open.
8. **The pre-existing legacy paths in the graphify graph** (`/Users/Dev/...`, Desktop-rooted) — orthogonal to SP-0 but flagged as cleanup at some point.

---

## 13. Cross-references

**Project rules (binding):**
- `CLAUDE.md` — project principles, module table, environment architecture, auto-gate
- `.claude/rules/architecture.md` — module structure, shared code, dependencies, API rules, LESSON-006 integration-test rule
- `.claude/rules/code-standards.md` — naming, error handling, imports, dead code, LESSON-005 logging keys
- `.claude/rules/error-handling.md` — error envelope, HTTP status codes, internal error handling
- `.claude/rules/event-bus.md` — publishing, consuming, reliability, contracts
- `.claude/rules/financial-precision.md` — Decimal, penny allocation, batch totals
- `.claude/rules/hipaa-2026.md` — MFA, encryption, audit, sessions
- `.claude/rules/performance.md` — DB indexes, async SQLAlchemy, caching, query budgets
- `.claude/rules/phi-compliance.md` — PHI encryption, logging, access logging, API responses
- `.claude/rules/security.md` — auth, input validation, secrets, middleware
- `.claude/rules/surgical-changes.md` — scope discipline
- `.claude/rules/tenant-isolation.md` — DB queries, Redis, events, API, testing
- `.claude/rules/testing.md` — coverage requirements, SQLAlchemy fixture pattern, UUID workaround

**Existing code that SP-0 builds on or consumes:**
- `portal/operator/lib/bff.ts` — starting point for the BFF host
- `portal/operator/proxy.ts` — auth-gate edge middleware
- `portal/operator/.env.local`, `.env.dev`, `.env.mock`, `.env.prod` — environment config pattern that the deployment manifest extends
- `@infinityrx/portal-shared` — existing shared package; the seed of the proposed package structure

**Adjacent work in flight:**
- `waves/B12/` — tactical auth shim fixes whose end-state lands in `packages/auth`

**Decomposition context:**
- Sub-project of an Operator Portal & Platform Frontend milestone decomposed 2026-05-14 into SP-0 (this) + SP-1 Directories + SP-2 PaySync + SP-3 Billing/Accounting/Analytics + SP-4 ReclaimRx + SP-5 Claims/Adjudication + SP-6 No-code program designer + SP-7 Medical EDI, plus future SP-Client-Portal and SP-Provider-Portal.

---

## 14. Next steps

1. **Codex spec review** (task #11) — Sections 5–9 especially (architecture, components, data flow, error handling, testing). Mike accepted Sections 4 and 5 of brainstorming provisionally; the codex gate is the substantive review for those. Run via gstack `/codex` (or `/codex:review`).
2. **Fold revisions** if codex flags anything; iterate until concerns are addressed or accepted as open.
3. **Invoke writing-plans** to produce the SP-0 implementation plan. The framework re-evaluation (§10) is the plan's first task.
4. **Pre-execution:** B12 lingering bug fixes land (task #9) — B12's auth-shim slices feed into `packages/auth` rather than persisting.
5. **Execute SP-0** with the spec as the authoritative input.

---

*End of spec.*
