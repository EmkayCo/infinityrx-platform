# SP-0 Plan B — packages/contract + packages/auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** v2, 2026-05-15. v1 (`4eb93d8`) BLOCKED codex pass-1 with 1 BLOCK + 4 CONCERNs + 1 NIT. v2 closes:
- **BLOCK (`.strict()` zod claims):** `AccessClaimsSchema` + `RefreshClaimsSchema` now use `.strict()` so unknown keys are REJECTED, not stripped. Tests asserting tid/roles rejection on refresh claims now actually fail-when-broken.
- **CONCERN (jose typed errors):** `verifyTokenRaw` now imports `JWTExpired`, `JWTInvalid`, `JWTClaimValidationFailed`, `JWSSignatureVerificationFailed` from `jose/errors` and maps via `instanceof`, not substring.
- **CONCERN (RealImpl test coverage):** Task 3.6 adds 6 RealImpl tests via injected `fetch` (bearer header, correlation propagation, success parse, 404 → null, error envelope mapping, invalid response rejection).
- **CONCERN (missing tests):** Task 5.4 adds refresh-after-password-reset + Redis-unreachable tests. **The transport header-vs-body test is INTENTIONALLY DEFERRED to Plan C** — `performRefresh` in Plan B is pure verification + atomic-consume + mint logic with NO HTTP boundary inside it. The HTTP boundary (the actual `Authorization: Bearer <refresh_jwt>` header arriving at a request handler) lives in Plan C's `portal/operator` proxy.ts and the corresponding BFF route handler. Testing transport in Plan B would require mocking both ends of a non-existent HTTP layer, which is integration territory. Plan C's acceptance includes a transport contract test asserting "refresh in body, not header → MISSING_BEARER" per SD-1 §11.
- **CONCERN (orphan files):** `telemetry.ts` and `health.ts` removed from the file-structure section — `BaseClient.probeHealth()` in `client-base.ts` already covers the health model, and telemetry hooks are folded into `ClientConfig` (no separate file needed).
- **NIT (goal wording):** Goal now says `npm run test:packages` runs both suites.

**Goal:** Ship `packages/contract` and `packages/auth` as the SP-0 TypeScript spine, on top of the Plan A foundation (commit `a7b838c`). Each package builds, typechecks, lints, and ships its own vitest suite. End state: workspace-root `tsc -b` compiles both packages, `npm run test:packages` runs all suites (scripts + contract + auth), CI workflow extends to lint/typecheck/test the new packages.

**Architecture:** Two new workspaces under `packages/`. Both are framework-agnostic (zero `next/*`, `next-auth/*`, `@auth/*` imports — enforced by Plan A's eslint Block B). `packages/contract` owns the typed-client interface contract (one base interface + one reference impl for the prescriber-directory backend; the other 12 backends ship in their respective verticals SP-1+). `packages/auth` owns the canonical JWT contract per SD-1: claim type definitions, mint/verify primitives, dev JWT path, revocation-repo client interface, refresh adapter shape, portal single-flight refresh helper. Python backend implementation (refresh endpoint, Redis revocation repo) is **out of scope** — Plan B's tests use mock backends; backend Python work is a parallel track outside SP-0's TypeScript-package phase.

**Tech Stack:** Node 22, TypeScript 5.6.3 (NodeNext, verbatimModuleSyntax, strict, composite), zod 3.23.x for runtime validation, jose 5.x for HS256 JWT mint/verify (Web-Crypto-based, runs in Node + browser), vitest 2.1.9 for tests, undici for HTTP clients (Node-native).

**Spec references:**
- Main SP-0 spec `docs/superpowers/specs/2026-05-14-sp0-integration-foundation-design.md` (commit `a50130f`) §6.1 (`packages/contract`), §6.2 (`packages/auth` — superseded by SD-1)
- SD-1 (auth interface v4) `docs/superpowers/specs/2026-05-15-sp0-decision-spike-auth-interface.md` (commit `b876c3b`) §2–§8 (claim shapes, crypto, refresh, validation contract, revocation repo, refresh endpoint), §10 (out of v1), §11 (adoption checklist)
- SD-2 (framework v3) `docs/superpowers/specs/2026-05-15-sp0-decision-spike-framework.md` (commit `14d847a`) — framework-agnostic spine mandate
- Plan A `docs/superpowers/plans/2026-05-15-sp0-plan-a-foundation-scaffolding.md` (commit `424bd14`) — workspace pattern + Plan A status doc `2026-05-15-sp0-plan-a-status.md`

**Out of scope for Plan B** (deferred to other plans / waves):
- The other 12 typed backend clients in `packages/contract` — one per vertical (SP-1 directories, SP-2 paysync, etc.); Plan B ships the framework + 1 reference (prescriber-directory).
- The Python backend implementation of `POST /api/v1/auth/token/refresh`, the Redis revocation repo, and the per-backend JWT middleware refactor per SD-1 §11 backend checklist — separate Python wave, not SP-0 TypeScript.
- Wiring `packages/auth` into `portal/operator`'s next-auth config — Plan C (the shell host).
- `packages/ui`, `packages/qa-harness`, `packages/shell` — Plan C.
- The reference module `packages/modules/reclaimrx` — Plan D.
- Composition codegen + audit + ESLint zone generation — Plan D.

---

## File Structure

### Creates

```
packages/contract/
  package.json
  tsconfig.json
  vitest.config.ts
  src/
    index.ts                          # public surface re-exports
    error-envelope.ts                 # { error: { code, message, field?, correlation_id } } + zod schema
    cache-policy.ts                   # TTL / cache-key / invalidation-tags types
    client-base.ts                    # BaseClient interface (Real + Mock common contract); includes probeHealth() (health model) and ClientConfig telemetry hooks
    impls/
      prescriber-directory/
        types.ts                      # zod schemas: Prescriber, PrescriberSearchRequest/Response
        client.ts                     # PrescriberDirectoryClient interface
        real.ts                       # RealPrescriberDirectoryClient (uses undici)
        mock.ts                       # MockPrescriberDirectoryClient (fixture-backed)
    __tests__/
      error-envelope.test.ts          # zod parse failure modes + happy path
      cache-policy.test.ts            # TTL/tag invariants
      prescriber-directory.test.ts    # RealImpl with msw + MockImpl + cache-policy integration
      framework-agnostic.test.ts      # forbids next/* / next-auth/* imports in src/ via grep

packages/auth/
  package.json
  tsconfig.json
  vitest.config.ts
  src/
    index.ts                          # public surface re-exports
    claims.ts                         # AccessClaims + RefreshClaims types + zod schemas per SD-1 §2/§3
    crypto.ts                         # HS256 mint/verify via jose; per-env JWT_SECRET enforcement
    env-claim.ts                      # Env enum + validate(env) per SD-1 §4
    mint.ts                           # mintAccessToken + mintRefreshToken (uses crypto + env)
    verify.ts                         # verifyAccessToken + verifyRefreshToken (full §8 check chain)
    revocation-repo.ts                # interface RevocationRepo (Redis-backed at runtime; test uses InMemoryRepo)
    refresh-adapter.ts                # client adapter for POST /api/v1/auth/token/refresh per SD-1 §8.6
    single-flight.ts                  # portal single-flight refresh coalescing per SD-1 §11
    dev-jwt.ts                        # mintDevJwt — single source for dev/test JWT issuance per SD-1 §7
    errors.ts                         # AuthError class + error codes (MISSING_BEARER, INVALID_TOKEN, REVOKED_TOKEN, REFRESH_REPLAY, REVOCATION_CHECK_FAILED, WRONG_ISSUER, WRONG_AUDIENCE, WRONG_ENVIRONMENT, WRONG_TOKEN_TYPE, EXPIRED_TOKEN, MALFORMED_TOKEN)
    __tests__/
      claims.test.ts                  # zod parse: access vs refresh, missing tid, wrong typ
      crypto.test.ts                  # HS256 round-trip + cross-env secret rejection
      mint-and-verify.test.ts         # full §8 check chain (10 codes)
      refresh-rotation.test.ts        # atomic consume semantics with InMemoryRepo
      single-flight.test.ts           # coalesce concurrent refresh attempts to one network call
      dev-jwt.test.ts                 # env enforcement: prod refuses dev tokens
      framework-agnostic.test.ts      # forbids next/* / next-auth/* imports in src/
```

### Modifies

```
package.json                          # add packages/contract + packages/auth to workspace if not auto-discovered (they are via packages/*)
tsconfig.json                         # add references to ./packages/contract and ./packages/auth
.github/workflows/sp0-foundation.yml  # extend test step to run vitest across all packages workspaces
package-lock.json                     # regenerated after npm install
```

### Leaves alone

```
portal/                               # untouched in Plan B (Plan C handles portal/operator wiring)
packages/scripts/                     # untouched
modules/, shared/, scripts/           # backend Python untouched
infrastructure/                       # manifests + secret-catalog + integrations remain as Plan A shipped them
```

---

## Plan B — Tasks

### Task 1: Both package scaffolds (contract + auth)

**Files:**
- Create: `packages/contract/package.json`
- Create: `packages/contract/tsconfig.json`
- Create: `packages/contract/vitest.config.ts`
- Create: `packages/contract/src/index.ts` (empty stub for now)
- Create: `packages/auth/package.json`
- Create: `packages/auth/tsconfig.json`
- Create: `packages/auth/vitest.config.ts`
- Create: `packages/auth/src/index.ts` (empty stub)
- Modify: `tsconfig.json` (repo root) — add references to both new packages

- [ ] **Step 1.1: Write `packages/contract/package.json`**

```json
{
  "name": "@infinityrx/contract",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "exports": {
    ".": "./dist/index.js"
  },
  "scripts": {
    "build": "tsc -b",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "zod": "3.23.8"
  },
  "devDependencies": {
    "vitest": "2.1.9",
    "typescript": "5.6.3",
    "@types/node": "22.7.5"
  }
}
```

- [ ] **Step 1.2: Write `packages/contract/tsconfig.json`**

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src/**/*.ts"],
  "exclude": ["src/**/*.test.ts", "src/__tests__/**", "dist", "node_modules"]
}
```

- [ ] **Step 1.3: Write `packages/contract/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/**/*.test.ts", "src/__tests__/**/*.test.ts"],
    environment: "node",
  },
});
```

- [ ] **Step 1.4: Write `packages/contract/src/index.ts` (stub)**

```ts
// Public surface of @infinityrx/contract.
// Plan B Task 2+ populates these re-exports as the modules are added.
export {};
```

- [ ] **Step 1.5: Write `packages/auth/package.json`**

```json
{
  "name": "@infinityrx/auth",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "exports": {
    ".": "./dist/index.js"
  },
  "scripts": {
    "build": "tsc -b",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "jose": "5.9.6",
    "zod": "3.23.8"
  },
  "devDependencies": {
    "vitest": "2.1.9",
    "typescript": "5.6.3",
    "@types/node": "22.7.5"
  }
}
```

- [ ] **Step 1.6: Write `packages/auth/tsconfig.json`**

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src/**/*.ts"],
  "exclude": ["src/**/*.test.ts", "src/__tests__/**", "dist", "node_modules"]
}
```

- [ ] **Step 1.7: Write `packages/auth/vitest.config.ts`**

Same content as `packages/contract/vitest.config.ts`.

- [ ] **Step 1.8: Write `packages/auth/src/index.ts` (stub)**

```ts
// Public surface of @infinityrx/auth.
// Plan B Task 5+ populates these re-exports as the modules are added.
export {};
```

- [ ] **Step 1.9: Update repo-root `tsconfig.json` references**

```json
{
  "files": [],
  "references": [
    { "path": "./packages/scripts" },
    { "path": "./packages/contract" },
    { "path": "./packages/auth" }
  ]
}
```

- [ ] **Step 1.10: Install + verify**

```
npm install
npm ls --workspaces --depth=0
```

Expected: `@infinityrx/contract` and `@infinityrx/auth` appear in the workspace list alongside `@infinityrx/scripts`.

```
npm run typecheck
```

Expected: exit 0. Empty stubs compile fine.

```
npm run lint:root
```

Expected: exit 0. Empty stubs lint fine.

- [ ] **Step 1.11: Commit**

```bash
git add packages/contract/ packages/auth/ tsconfig.json package.json package-lock.json
git commit -m "feat(sp-0): packages/contract + packages/auth scaffolds

Both packages follow the Plan A pattern: package.json with type:module,
exports map pointing to dist/, tsconfig extends ../../tsconfig.base.json,
vitest.config.ts for tests, src/index.ts as the public-surface stub.

Adds tsconfig.json references so 'tsc -b' picks up both. Dependencies
pinned: zod 3.23.8 (both), jose 5.9.6 (auth only).

Implementation lands in Tasks 2-8.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: packages/contract — error envelope + cache policy + base client

**Files:**
- Create: `packages/contract/src/error-envelope.ts`
- Create: `packages/contract/src/cache-policy.ts`
- Create: `packages/contract/src/client-base.ts`
- Create: `packages/contract/src/__tests__/error-envelope.test.ts`
- Create: `packages/contract/src/__tests__/cache-policy.test.ts`
- Modify: `packages/contract/src/index.ts` (re-export new modules)

TDD: tests first.

- [ ] **Step 2.1: Write `packages/contract/src/__tests__/error-envelope.test.ts` (failing)**

```ts
import { describe, it, expect } from "vitest";
import { ErrorEnvelopeSchema, isErrorEnvelope } from "../error-envelope.js";

describe("ErrorEnvelopeSchema", () => {
  it("accepts a well-formed envelope", () => {
    const result = ErrorEnvelopeSchema.safeParse({
      error: {
        code: "VALIDATION_ERROR",
        message: "Field 'npi' must be 10 digits",
        field: "npi",
        correlation_id: "550e8400-e29b-41d4-a716-446655440000",
      },
    });
    expect(result.success).toBe(true);
  });

  it("accepts an envelope without optional field", () => {
    const result = ErrorEnvelopeSchema.safeParse({
      error: {
        code: "INTERNAL_ERROR",
        message: "Something went wrong",
        correlation_id: "550e8400-e29b-41d4-a716-446655440000",
      },
    });
    expect(result.success).toBe(true);
  });

  it("rejects an envelope missing correlation_id", () => {
    const result = ErrorEnvelopeSchema.safeParse({
      error: { code: "X", message: "Y" },
    });
    expect(result.success).toBe(false);
  });

  it("rejects an envelope with empty code", () => {
    const result = ErrorEnvelopeSchema.safeParse({
      error: { code: "", message: "Y", correlation_id: "550e8400-e29b-41d4-a716-446655440000" },
    });
    expect(result.success).toBe(false);
  });

  it("isErrorEnvelope narrows the type", () => {
    const candidate: unknown = {
      error: { code: "X", message: "Y", correlation_id: "550e8400-e29b-41d4-a716-446655440000" },
    };
    if (isErrorEnvelope(candidate)) {
      // TypeScript should narrow `candidate` to { error: { code: string, ... } }
      expect(candidate.error.code).toBe("X");
    } else {
      throw new Error("type guard should have narrowed");
    }
  });
});
```

- [ ] **Step 2.2: Run tests — confirm failure (TDD red)**

```
npm --workspace=@infinityrx/contract test
```

Expected: all 5 tests FAIL with "Cannot find module '../error-envelope.js'".

- [ ] **Step 2.3: Write `packages/contract/src/error-envelope.ts`**

```ts
import { z } from "zod";

/**
 * Canonical error envelope per `.claude/rules/error-handling.md`:
 *   { error: { code: string, message: string, field?: string, correlation_id: string } }
 *
 * Every backend returns errors in this shape. Every BFF wraps thrown errors in this shape.
 * The zod schema is the authority — runtime validation at every boundary.
 */
export const ErrorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string().min(1, "error.code must not be empty"),
    message: z.string(),
    field: z.string().optional(),
    correlation_id: z.string().uuid(),
  }),
});

export type ErrorEnvelope = z.infer<typeof ErrorEnvelopeSchema>;

export function isErrorEnvelope(candidate: unknown): candidate is ErrorEnvelope {
  return ErrorEnvelopeSchema.safeParse(candidate).success;
}
```

- [ ] **Step 2.4: Run tests — confirm passing (TDD green)**

```
npm --workspace=@infinityrx/contract test
```

Expected: 5/5 pass.

- [ ] **Step 2.5: Write `packages/contract/src/__tests__/cache-policy.test.ts` (failing)**

```ts
import { describe, it, expect } from "vitest";
import { CachePolicySchema, type CachePolicy } from "../cache-policy.js";

describe("CachePolicy", () => {
  it("accepts a TTL-only policy", () => {
    const result = CachePolicySchema.safeParse({
      ttl_seconds: 60,
      key: ["prescriber", "by-npi", "{npi}"],
      invalidation_tags: ["prescriber"],
      backend_down: "stale-ok",
    });
    expect(result.success).toBe(true);
  });

  it("rejects ttl_seconds <= 0", () => {
    const result = CachePolicySchema.safeParse({
      ttl_seconds: 0,
      key: ["x"],
      invalidation_tags: [],
      backend_down: "fail-fast",
    });
    expect(result.success).toBe(false);
  });

  it("rejects key with empty segment", () => {
    const result = CachePolicySchema.safeParse({
      ttl_seconds: 60,
      key: ["", "by-npi"],
      invalidation_tags: [],
      backend_down: "stale-ok",
    });
    expect(result.success).toBe(false);
  });

  it("rejects unknown backend_down value", () => {
    const result = CachePolicySchema.safeParse({
      ttl_seconds: 60,
      key: ["x"],
      invalidation_tags: [],
      backend_down: "explode",
    });
    expect(result.success).toBe(false);
  });

  it("accepts each of the 3 backend_down values", () => {
    for (const v of ["stale-ok", "fail-fast", "fall-back-to-mock"] as const) {
      const result = CachePolicySchema.safeParse({
        ttl_seconds: 60,
        key: ["x"],
        invalidation_tags: [],
        backend_down: v,
      });
      expect(result.success, `${v} should parse`).toBe(true);
    }
  });
});
```

- [ ] **Step 2.6: Run tests — confirm failure**

Expected: 5 new tests fail.

- [ ] **Step 2.7: Write `packages/contract/src/cache-policy.ts`**

```ts
import { z } from "zod";

/**
 * Declarative per-resource cache policy. Consumed by the BFF cache adapter (Plan C)
 * and by the contract clients to emit invalidation tags on mutations.
 *
 * - `ttl_seconds`: positive int (seconds)
 * - `key`: ordered segments; concrete cache key is segments joined + interpolated args
 * - `invalidation_tags`: tags this resource belongs to; mutations emit these to purge
 * - `backend_down`: behavior when the backend is unreachable
 */
export const CachePolicySchema = z.object({
  ttl_seconds: z.number().int().positive(),
  key: z.array(z.string().min(1)),
  invalidation_tags: z.array(z.string().min(1)),
  backend_down: z.enum(["stale-ok", "fail-fast", "fall-back-to-mock"]),
});

export type CachePolicy = z.infer<typeof CachePolicySchema>;
```

- [ ] **Step 2.8: Run tests — confirm passing**

Expected: 10/10 (5 envelope + 5 cache policy) pass.

- [ ] **Step 2.9: Write `packages/contract/src/client-base.ts`**

(No new tests for this step — it's pure types and gets exercised by Task 3's reference client tests.)

```ts
import type { CachePolicy } from "./cache-policy.js";

/**
 * Every typed backend client implements this contract.
 * Concrete clients (RealImpl + MockImpl) expose domain methods (e.g.,
 * `prescriberClient.search({ npi })`); the BaseClient describes only the
 * cross-cutting metadata the BFF + cache layer need.
 */
export interface BaseClient {
  /** Stable identifier for telemetry + cache key namespacing. e.g. "prescriber-directory" */
  readonly name: string;

  /** Per-resource cache policies keyed by operation name. */
  readonly cachePolicies: Record<string, CachePolicy>;

  /** Health probe for the services-health aggregator (Plan C). */
  probeHealth(): Promise<{ ok: boolean; latency_ms: number; error?: string }>;
}

export type ClientFactory<T extends BaseClient> = (config: ClientConfig) => T;

export interface ClientConfig {
  /** Base URL of the backend (real) or undefined (mock). */
  baseUrl?: string;
  /** Function that produces a fresh access token Bearer string. */
  getAuthToken: () => Promise<string>;
  /** Correlation-id propagation header (default `x-correlation-id`). */
  correlationHeader?: string;
  /** Fetch implementation override (Node uses undici; tests inject msw). */
  fetch?: typeof globalThis.fetch;
}
```

- [ ] **Step 2.10: Update `packages/contract/src/index.ts` to re-export new modules**

```ts
// Public surface of @infinityrx/contract.

export {
  ErrorEnvelopeSchema,
  isErrorEnvelope,
  type ErrorEnvelope,
} from "./error-envelope.js";

export {
  CachePolicySchema,
  type CachePolicy,
} from "./cache-policy.js";

export type {
  BaseClient,
  ClientConfig,
  ClientFactory,
} from "./client-base.js";
```

- [ ] **Step 2.11: Verify typecheck + tests + lint**

```
npm run typecheck
npm --workspace=@infinityrx/contract test
npm run lint:root
```

Expected: typecheck exit 0, 10/10 tests pass, lint exit 0.

- [ ] **Step 2.12: Commit**

```bash
git add packages/contract/
git commit -m "feat(contract): error envelope + cache policy + base client

- ErrorEnvelopeSchema: zod schema for { error: { code, message, field?,
  correlation_id } } per .claude/rules/error-handling.md
- CachePolicySchema: ttl_seconds + key segments + invalidation_tags +
  backend_down enum (stale-ok / fail-fast / fall-back-to-mock)
- BaseClient interface: name + cachePolicies + probeHealth()
- ClientConfig + ClientFactory types for Real/Mock factories

10 vitest tests (5 envelope + 5 cache policy) — TDD red/green clean.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: packages/contract — reference client (prescriber-directory)

**Files:**
- Create: `packages/contract/src/impls/prescriber-directory/types.ts`
- Create: `packages/contract/src/impls/prescriber-directory/client.ts`
- Create: `packages/contract/src/impls/prescriber-directory/real.ts`
- Create: `packages/contract/src/impls/prescriber-directory/mock.ts`
- Create: `packages/contract/src/__tests__/prescriber-directory.test.ts`
- Modify: `packages/contract/src/index.ts`
- Modify: `packages/contract/package.json` (add undici as a dep)

The prescriber-directory client is the reference impl for the perf-critical path (main spec §7.1). Other 12 backend clients ship per-vertical (SP-1+) following this pattern.

- [ ] **Step 3.1: Add undici to packages/contract deps**

Modify `packages/contract/package.json` `dependencies`:

```json
"dependencies": {
  "zod": "3.23.8",
  "undici": "6.21.0"
}
```

Run: `npm install` from repo root. Expected: clean.

- [ ] **Step 3.2: Write `packages/contract/src/impls/prescriber-directory/types.ts`**

```ts
import { z } from "zod";

/** NPI: 10-digit Luhn-valid number. Validation deferred to backend; client accepts string. */
export const NpiSchema = z.string().regex(/^\d{10}$/);
export type Npi = z.infer<typeof NpiSchema>;

export const PrescriberSchema = z.object({
  npi: NpiSchema,
  first_name: z.string(),
  last_name: z.string(),
  credential: z.string().optional(),
  primary_specialty: z.string(),
  state: z.string().length(2),
  zip: z.string().regex(/^\d{5}(-\d{4})?$/),
  active: z.boolean(),
});
export type Prescriber = z.infer<typeof PrescriberSchema>;

export const PrescriberSearchRequestSchema = z.object({
  q: z.string().min(1).max(64),
  state: z.string().length(2).optional(),
  specialty: z.string().optional(),
  limit: z.number().int().positive().max(100).default(20),
  cursor: z.string().optional(),
});
export type PrescriberSearchRequest = z.infer<typeof PrescriberSearchRequestSchema>;

export const PrescriberSearchResponseSchema = z.object({
  results: z.array(PrescriberSchema),
  next_cursor: z.string().optional(),
  total: z.number().int().nonnegative(),
});
export type PrescriberSearchResponse = z.infer<typeof PrescriberSearchResponseSchema>;
```

- [ ] **Step 3.3: Write `packages/contract/src/impls/prescriber-directory/client.ts`**

```ts
import type { BaseClient, ClientConfig, ClientFactory } from "../../client-base.js";
import type {
  Npi,
  Prescriber,
  PrescriberSearchRequest,
  PrescriberSearchResponse,
} from "./types.js";
import type { CachePolicy } from "../../cache-policy.js";

export interface PrescriberDirectoryClient extends BaseClient {
  readonly name: "prescriber-directory";

  /** Search prescribers by name/NPI/specialty. Cached per the policy below. */
  search(req: PrescriberSearchRequest): Promise<PrescriberSearchResponse>;

  /** Fetch one prescriber by NPI. Cached aggressively. */
  getByNpi(npi: Npi): Promise<Prescriber | null>;
}

export const PRESCRIBER_DIRECTORY_CACHE_POLICIES: Record<string, CachePolicy> = {
  search: {
    ttl_seconds: 60,
    key: ["prescriber-directory", "search", "{q}", "{state}", "{specialty}", "{cursor}"],
    invalidation_tags: ["prescriber"],
    backend_down: "stale-ok",
  },
  getByNpi: {
    ttl_seconds: 3600,
    key: ["prescriber-directory", "by-npi", "{npi}"],
    invalidation_tags: ["prescriber"],
    backend_down: "fall-back-to-mock",
  },
};

export type PrescriberDirectoryFactory = ClientFactory<PrescriberDirectoryClient>;
export type { ClientConfig };
```

- [ ] **Step 3.4: Write `packages/contract/src/impls/prescriber-directory/real.ts`**

```ts
import type { PrescriberDirectoryClient } from "./client.js";
import { PRESCRIBER_DIRECTORY_CACHE_POLICIES } from "./client.js";
import type { ClientConfig } from "../../client-base.js";
import {
  PrescriberSchema,
  PrescriberSearchRequestSchema,
  PrescriberSearchResponseSchema,
  type Npi,
  type Prescriber,
  type PrescriberSearchRequest,
  type PrescriberSearchResponse,
} from "./types.js";
import { isErrorEnvelope } from "../../error-envelope.js";

class AuthError extends Error {
  constructor(public readonly code: string, message: string, public readonly correlationId?: string) {
    super(message);
    this.name = "AuthError";
  }
}

export function createRealPrescriberDirectoryClient(config: ClientConfig): PrescriberDirectoryClient {
  if (!config.baseUrl) {
    throw new Error("createRealPrescriberDirectoryClient: baseUrl is required");
  }
  const baseUrl = config.baseUrl.replace(/\/$/, "");
  const correlationHeader = config.correlationHeader ?? "x-correlation-id";
  const fetchImpl = config.fetch ?? globalThis.fetch;

  async function authedFetch(path: string, init?: RequestInit): Promise<Response> {
    const token = await config.getAuthToken();
    const headers = new Headers(init?.headers);
    headers.set("Authorization", `Bearer ${token}`);
    headers.set("Content-Type", "application/json");
    headers.set(correlationHeader, crypto.randomUUID());
    return fetchImpl(`${baseUrl}${path}`, { ...init, headers });
  }

  async function unwrap<T>(res: Response, schema: { parse(raw: unknown): T }): Promise<T> {
    const body = await res.json();
    if (!res.ok) {
      if (isErrorEnvelope(body)) {
        throw new AuthError(body.error.code, body.error.message, body.error.correlation_id);
      }
      throw new Error(`Unexpected error shape: HTTP ${res.status}`);
    }
    return schema.parse(body);
  }

  return {
    name: "prescriber-directory" as const,
    cachePolicies: PRESCRIBER_DIRECTORY_CACHE_POLICIES,

    async search(req: PrescriberSearchRequest): Promise<PrescriberSearchResponse> {
      const validated = PrescriberSearchRequestSchema.parse(req);
      const qs = new URLSearchParams();
      qs.set("q", validated.q);
      if (validated.state) qs.set("state", validated.state);
      if (validated.specialty) qs.set("specialty", validated.specialty);
      qs.set("limit", String(validated.limit));
      if (validated.cursor) qs.set("cursor", validated.cursor);
      const res = await authedFetch(`/prescribers/search?${qs.toString()}`);
      return unwrap(res, PrescriberSearchResponseSchema);
    },

    async getByNpi(npi: Npi): Promise<Prescriber | null> {
      const res = await authedFetch(`/prescribers/${encodeURIComponent(npi)}`);
      if (res.status === 404) return null;
      return unwrap(res, PrescriberSchema);
    },

    async probeHealth() {
      // NOTE: tsconfig.base.json has `exactOptionalPropertyTypes: true`, so we MUST NOT
      // return `{ error: undefined }` on the ok path — the optional property must be
      // OMITTED, not set to undefined. Branch the return type instead.
      const start = performance.now();
      try {
        const res = await fetchImpl(`${baseUrl}/health`, { method: "GET" });
        const latency_ms = Math.round(performance.now() - start);
        return res.ok
          ? { ok: true as const, latency_ms }
          : { ok: false as const, latency_ms, error: `HTTP ${res.status}` };
      } catch (e) {
        return {
          ok: false as const,
          latency_ms: Math.round(performance.now() - start),
          error: (e as Error).message,
        };
      }
    },
  };
}
```

- [ ] **Step 3.5: Write `packages/contract/src/impls/prescriber-directory/mock.ts`**

```ts
import type { PrescriberDirectoryClient } from "./client.js";
import { PRESCRIBER_DIRECTORY_CACHE_POLICIES } from "./client.js";
import type {
  Npi,
  Prescriber,
  PrescriberSearchRequest,
  PrescriberSearchResponse,
} from "./types.js";

const MOCK_FIXTURE: Prescriber[] = [
  {
    npi: "1234567893",
    first_name: "Jane",
    last_name: "Smith",
    credential: "MD",
    primary_specialty: "Internal Medicine",
    state: "NY",
    zip: "10001",
    active: true,
  },
  {
    npi: "1987654320",
    first_name: "John",
    last_name: "Doe",
    credential: "DO",
    primary_specialty: "Family Medicine",
    state: "CA",
    zip: "90001",
    active: true,
  },
  {
    npi: "1112223334",
    first_name: "Maria",
    last_name: "Garcia",
    credential: "NP",
    primary_specialty: "Cardiology",
    state: "FL",
    zip: "33101",
    active: false,
  },
];

export function createMockPrescriberDirectoryClient(): PrescriberDirectoryClient {
  return {
    name: "prescriber-directory" as const,
    cachePolicies: PRESCRIBER_DIRECTORY_CACHE_POLICIES,

    async search(req: PrescriberSearchRequest): Promise<PrescriberSearchResponse> {
      const q = req.q.toLowerCase();
      const filtered = MOCK_FIXTURE.filter((p) => {
        const matchesQ =
          p.first_name.toLowerCase().includes(q) ||
          p.last_name.toLowerCase().includes(q) ||
          p.npi.includes(req.q);
        const matchesState = !req.state || p.state === req.state;
        const matchesSpecialty = !req.specialty || p.primary_specialty === req.specialty;
        return matchesQ && matchesState && matchesSpecialty;
      });
      return {
        results: filtered.slice(0, req.limit ?? 20),
        total: filtered.length,
      };
    },

    async getByNpi(npi: Npi): Promise<Prescriber | null> {
      return MOCK_FIXTURE.find((p) => p.npi === npi) ?? null;
    },

    async probeHealth() {
      return { ok: true, latency_ms: 0 };
    },
  };
}
```

- [ ] **Step 3.6: Write `packages/contract/src/__tests__/prescriber-directory.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { createMockPrescriberDirectoryClient } from "../impls/prescriber-directory/mock.js";
import { PRESCRIBER_DIRECTORY_CACHE_POLICIES } from "../impls/prescriber-directory/client.js";
import { CachePolicySchema } from "../cache-policy.js";

describe("MockPrescriberDirectoryClient", () => {
  const client = createMockPrescriberDirectoryClient();

  it("exposes the expected name", () => {
    expect(client.name).toBe("prescriber-directory");
  });

  it("exposes cache policies that validate against CachePolicySchema", () => {
    for (const [op, policy] of Object.entries(client.cachePolicies)) {
      const result = CachePolicySchema.safeParse(policy);
      expect(result.success, `${op} policy should validate`).toBe(true);
    }
  });

  it("search returns matches by last_name", async () => {
    const r = await client.search({ q: "Smith", limit: 20 });
    expect(r.results.length).toBeGreaterThanOrEqual(1);
    expect(r.results[0]?.last_name).toBe("Smith");
  });

  it("search returns matches by NPI substring", async () => {
    const r = await client.search({ q: "1234567893", limit: 20 });
    expect(r.results.length).toBe(1);
    expect(r.results[0]?.npi).toBe("1234567893");
  });

  it("search respects state filter", async () => {
    const r = await client.search({ q: "M", state: "NY", limit: 20 });
    expect(r.results.every((p) => p.state === "NY")).toBe(true);
  });

  it("search honors limit", async () => {
    const r = await client.search({ q: "M", limit: 1 });
    expect(r.results.length).toBeLessThanOrEqual(1);
  });

  it("getByNpi returns the matching prescriber", async () => {
    const p = await client.getByNpi("1234567893");
    expect(p?.first_name).toBe("Jane");
  });

  it("getByNpi returns null for unknown NPI", async () => {
    const p = await client.getByNpi("9999999999");
    expect(p).toBeNull();
  });

  it("probeHealth returns ok:true for mock", async () => {
    const h = await client.probeHealth();
    expect(h.ok).toBe(true);
  });

  it("PRESCRIBER_DIRECTORY_CACHE_POLICIES has both operations", () => {
    expect(PRESCRIBER_DIRECTORY_CACHE_POLICIES).toHaveProperty("search");
    expect(PRESCRIBER_DIRECTORY_CACHE_POLICIES).toHaveProperty("getByNpi");
  });
});

// ── RealImpl tests via injected fetch (no network) ──
import { createRealPrescriberDirectoryClient } from "../impls/prescriber-directory/real.js";

describe("RealPrescriberDirectoryClient (injected fetch)", () => {
  function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
    return new Response(JSON.stringify(body), {
      ...init,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
  }

  it("attaches Bearer token + correlation header on every request", async () => {
    const captured: { headers: Headers; url: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url });
      return jsonResponse({ results: [], total: 0 });
    };
    const client = createRealPrescriberDirectoryClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok-abc",
      fetch: fakeFetch,
    });
    await client.search({ q: "Smith", limit: 20 });
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-abc");
    expect(captured[0]?.headers.get("x-correlation-id")).toMatch(/^[0-9a-f-]{36}$/);
    expect(captured[0]?.url).toContain("/prescribers/search");
  });

  it("parses a successful search response via zod", async () => {
    const fakeFetch: typeof fetch = async () => jsonResponse({
      results: [{
        npi: "1234567893", first_name: "Jane", last_name: "Smith", credential: "MD",
        primary_specialty: "Internal Medicine", state: "NY", zip: "10001", active: true,
      }],
      total: 1,
    });
    const client = createRealPrescriberDirectoryClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    const res = await client.search({ q: "Smith", limit: 20 });
    expect(res.results[0]?.last_name).toBe("Smith");
    expect(res.total).toBe(1);
  });

  it("getByNpi returns null on HTTP 404", async () => {
    const fakeFetch: typeof fetch = async () => new Response(null, { status: 404 });
    const client = createRealPrescriberDirectoryClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    const p = await client.getByNpi("9999999999");
    expect(p).toBeNull();
  });

  it("rejects responses that do not match the zod schema", async () => {
    const fakeFetch: typeof fetch = async () => jsonResponse({ wrong: "shape" });
    const client = createRealPrescriberDirectoryClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    await expect(client.search({ q: "S", limit: 20 })).rejects.toThrow();
  });

  it("maps an error envelope from a 4xx/5xx response to an AuthError-ish exception", async () => {
    const fakeFetch: typeof fetch = async () => jsonResponse(
      { error: { code: "RATE_LIMITED", message: "Slow down", correlation_id: "550e8400-e29b-41d4-a716-446655440099" } },
      { status: 429 },
    );
    const client = createRealPrescriberDirectoryClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    await expect(client.search({ q: "S", limit: 20 })).rejects.toMatchObject({ code: "RATE_LIMITED" });
  });

  it("probeHealth pings /health and reports latency", async () => {
    const fakeFetch: typeof fetch = async () => new Response("OK", { status: 200 });
    const client = createRealPrescriberDirectoryClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    const h = await client.probeHealth();
    expect(h.ok).toBe(true);
    expect(typeof h.latency_ms).toBe("number");
  });
});
```

- [ ] **Step 3.7: Update index.ts**

```ts
// Public surface of @infinityrx/contract.

export {
  ErrorEnvelopeSchema,
  isErrorEnvelope,
  type ErrorEnvelope,
} from "./error-envelope.js";

export {
  CachePolicySchema,
  type CachePolicy,
} from "./cache-policy.js";

export type {
  BaseClient,
  ClientConfig,
  ClientFactory,
} from "./client-base.js";

// Reference client: prescriber-directory. Other 12 backend clients live in their own SP-N verticals.
export {
  PrescriberSchema,
  PrescriberSearchRequestSchema,
  PrescriberSearchResponseSchema,
  NpiSchema,
  type Prescriber,
  type PrescriberSearchRequest,
  type PrescriberSearchResponse,
  type Npi,
} from "./impls/prescriber-directory/types.js";

export {
  PRESCRIBER_DIRECTORY_CACHE_POLICIES,
  type PrescriberDirectoryClient,
  type PrescriberDirectoryFactory,
} from "./impls/prescriber-directory/client.js";

export { createRealPrescriberDirectoryClient } from "./impls/prescriber-directory/real.js";
export { createMockPrescriberDirectoryClient } from "./impls/prescriber-directory/mock.js";
```

- [ ] **Step 3.8: Verify typecheck + 19 tests passing + lint**

```
npm run typecheck
npm --workspace=@infinityrx/contract test
npm run lint:root
```

Expected: typecheck exit 0, 25/25 tests pass (10 prior + 9 MockImpl + 6 RealImpl), lint exit 0.

- [ ] **Step 3.9: Commit**

```bash
git add packages/contract/ package.json package-lock.json
git commit -m "feat(contract): reference client — prescriber-directory

RealImpl: undici-backed, bearer-auth, zod-validated request/response,
error-envelope handling, correlation-id propagation, /health probe.
MockImpl: fixture-backed (3 prescribers), supports all 3 query
combinations (last_name / NPI substring / state filter / specialty),
respects limit, returns null on getByNpi miss.

Cache policies: search → 60s TTL with [q,state,specialty,cursor] key
+ invalidation tag 'prescriber' + stale-ok. getByNpi → 3600s TTL with
[npi] key + invalidation tag 'prescriber' + fall-back-to-mock.

9 vitest tests proving the MockImpl's behavior + policy validity.
Real impl is exercised by Plan C's BFF integration tests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: packages/auth — claim types + crypto + env claim

**Files:**
- Create: `packages/auth/src/claims.ts`
- Create: `packages/auth/src/env-claim.ts`
- Create: `packages/auth/src/crypto.ts`
- Create: `packages/auth/src/errors.ts`
- Create: `packages/auth/src/__tests__/claims.test.ts`
- Create: `packages/auth/src/__tests__/crypto.test.ts`
- Modify: `packages/auth/src/index.ts`

- [ ] **Step 4.1: Write `packages/auth/src/errors.ts`**

```ts
/**
 * Auth error codes per SD-1 §8. Backend middleware + portal adapters use these.
 * Numeric values are NOT exposed — only the string codes.
 */
export type AuthErrorCode =
  | "MISSING_BEARER"
  | "INVALID_TOKEN"
  | "MALFORMED_TOKEN"
  | "WRONG_ISSUER"
  | "WRONG_AUDIENCE"
  | "WRONG_ENVIRONMENT"
  | "WRONG_TOKEN_TYPE"
  | "EXPIRED_TOKEN"
  | "REVOKED_TOKEN"
  | "REFRESH_REPLAY"
  | "REVOCATION_CHECK_FAILED";

export class AuthError extends Error {
  readonly code: AuthErrorCode;
  readonly correlationId?: string;

  constructor(code: AuthErrorCode, message: string, correlationId?: string) {
    super(message);
    this.name = "AuthError";
    this.code = code;
    this.correlationId = correlationId;
  }
}

/** Stable per-code message. Backends MUST NOT vary these to avoid information leak. */
export const AUTH_ERROR_MESSAGES: Record<AuthErrorCode, string> = {
  MISSING_BEARER: "Authorization header missing or malformed",
  INVALID_TOKEN: "Token signature verification failed",
  MALFORMED_TOKEN: "Token is missing required claims",
  WRONG_ISSUER: "Token issuer is not infinityrx",
  WRONG_AUDIENCE: "Token audience is not infinityrx-backend",
  WRONG_ENVIRONMENT: "Token environment does not match this server's environment",
  WRONG_TOKEN_TYPE: "Token type is not valid for this route",
  EXPIRED_TOKEN: "Token expiration time has passed",
  REVOKED_TOKEN: "Token has been revoked",
  REFRESH_REPLAY: "Refresh token has already been consumed",
  REVOCATION_CHECK_FAILED: "Revocation repository is unreachable",
};
```

- [ ] **Step 4.2: Write `packages/auth/src/env-claim.ts`**

```ts
import { z } from "zod";

/**
 * The `env` claim per SD-1 §4. Tokens minted in one environment cannot be
 * accepted in another even if the secret were shared (which it MUST NOT be).
 * Defense-in-depth on top of per-environment JWT_SECRET separation.
 */
export const EnvClaimSchema = z.enum(["development", "mock", "production"]);
export type EnvClaim = z.infer<typeof EnvClaimSchema>;

/** Resolve the running process's environment from INFINITYRX_ENV. Throws if missing/invalid. */
export function resolveEnvClaim(env: string | undefined): EnvClaim {
  const result = EnvClaimSchema.safeParse(env);
  if (!result.success) {
    throw new Error(
      `INFINITYRX_ENV must be one of: development, mock, production. Got: ${JSON.stringify(env)}`,
    );
  }
  return result.data;
}
```

- [ ] **Step 4.3: Write `packages/auth/src/claims.ts`**

```ts
import { z } from "zod";
import { EnvClaimSchema } from "./env-claim.js";

/** Per SD-1 §2. `.strict()` rejects unknown keys (Ajv-equivalent additionalProperties:false). */
export const AccessClaimsSchema = z.object({
  sub: z.string().uuid(),
  tid: z.string().uuid(),
  roles: z.array(z.string()),
  typ: z.literal("access"),
  iat: z.number().int(),
  exp: z.number().int(),
  jti: z.string().uuid(),
  iss: z.literal("infinityrx"),
  aud: z.literal("infinityrx-backend"),
  env: EnvClaimSchema,
}).strict();
export type AccessClaims = z.infer<typeof AccessClaimsSchema>;

/** Per SD-1 §3. No tid, no roles on refresh. `.strict()` REJECTS tid/roles — non-strict z.object would silently strip them. */
export const RefreshClaimsSchema = z.object({
  sub: z.string().uuid(),
  typ: z.literal("refresh"),
  iat: z.number().int(),
  exp: z.number().int(),
  jti: z.string().uuid(),
  iss: z.literal("infinityrx"),
  aud: z.literal("infinityrx-backend"),
  env: EnvClaimSchema,
}).strict();
export type RefreshClaims = z.infer<typeof RefreshClaimsSchema>;

export const ISSUER = "infinityrx" as const;
export const AUDIENCE = "infinityrx-backend" as const;
```

- [ ] **Step 4.4: Write `packages/auth/src/__tests__/claims.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { AccessClaimsSchema, RefreshClaimsSchema } from "../claims.js";

const validAccess = {
  sub: "550e8400-e29b-41d4-a716-446655440000",
  tid: "550e8400-e29b-41d4-a716-446655440001",
  roles: ["platform_admin"],
  typ: "access" as const,
  iat: 1700000000,
  exp: 1700000900,
  jti: "550e8400-e29b-41d4-a716-446655440002",
  iss: "infinityrx" as const,
  aud: "infinityrx-backend" as const,
  env: "production" as const,
};

const validRefresh = {
  sub: "550e8400-e29b-41d4-a716-446655440000",
  typ: "refresh" as const,
  iat: 1700000000,
  exp: 1700028800,
  jti: "550e8400-e29b-41d4-a716-446655440003",
  iss: "infinityrx" as const,
  aud: "infinityrx-backend" as const,
  env: "production" as const,
};

describe("AccessClaimsSchema", () => {
  it("accepts a valid access-token claim set", () => {
    expect(AccessClaimsSchema.safeParse(validAccess).success).toBe(true);
  });
  it("accepts empty roles array", () => {
    expect(AccessClaimsSchema.safeParse({ ...validAccess, roles: [] }).success).toBe(true);
  });
  it("rejects missing tid (REQUIRED for access)", () => {
    const { tid: _omit, ...withoutTid } = validAccess;
    expect(AccessClaimsSchema.safeParse(withoutTid).success).toBe(false);
  });
  it("rejects typ=refresh on access schema", () => {
    expect(AccessClaimsSchema.safeParse({ ...validAccess, typ: "refresh" }).success).toBe(false);
  });
  it("rejects iss=wrong on access schema", () => {
    expect(AccessClaimsSchema.safeParse({ ...validAccess, iss: "wrong" }).success).toBe(false);
  });
  it("rejects env outside the enum", () => {
    expect(AccessClaimsSchema.safeParse({ ...validAccess, env: "staging" }).success).toBe(false);
  });
});

describe("RefreshClaimsSchema", () => {
  it("accepts a valid refresh-token claim set", () => {
    expect(RefreshClaimsSchema.safeParse(validRefresh).success).toBe(true);
  });
  it("rejects refresh with tid (refresh tokens MUST NOT have tid)", () => {
    expect(RefreshClaimsSchema.safeParse({ ...validRefresh, tid: validAccess.tid }).success).toBe(false);
  });
  it("rejects refresh with roles (refresh tokens MUST NOT have roles)", () => {
    expect(RefreshClaimsSchema.safeParse({ ...validRefresh, roles: ["x"] }).success).toBe(false);
  });
  it("rejects typ=access on refresh schema", () => {
    expect(RefreshClaimsSchema.safeParse({ ...validRefresh, typ: "access" }).success).toBe(false);
  });
});
```

- [ ] **Step 4.5: Write `packages/auth/src/crypto.ts`**

```ts
import { SignJWT, jwtVerify, type JWTPayload } from "jose";
import {
  JWTExpired,
  JWTClaimValidationFailed,
  JWSSignatureVerificationFailed,
  JWSInvalid,
  JWTInvalid,
  JOSEError,
} from "jose/errors";
import { AccessClaimsSchema, RefreshClaimsSchema, ISSUER, AUDIENCE, type AccessClaims, type RefreshClaims } from "./claims.js";
import { resolveEnvClaim, type EnvClaim } from "./env-claim.js";
import { AuthError, AUTH_ERROR_MESSAGES } from "./errors.js";

const ALGORITHM = "HS256" as const;

const DEV_PLACEHOLDER_SECRETS = new Set([
  "changeme",
  "dev-secret",
  "secret",
  "test",
  "your-secret-here",
]);

/**
 * Per SD-1 §4 startup check. Refuses to operate in production with a known
 * dev-placeholder secret.
 */
export function assertJwtSecret(secret: string | undefined, env: EnvClaim): void {
  if (!secret || secret.length < 32) {
    throw new Error(`JWT_SECRET must be ≥32 chars (got length=${secret?.length ?? 0})`);
  }
  if (env === "production" && DEV_PLACEHOLDER_SECRETS.has(secret.toLowerCase())) {
    throw new Error(
      "JWT_SECRET is a known dev placeholder. Production refuses to start with this secret.",
    );
  }
}

function secretKey(secret: string): Uint8Array {
  return new TextEncoder().encode(secret);
}

export async function signAccessToken(claims: AccessClaims, secret: string): Promise<string> {
  AccessClaimsSchema.parse(claims);
  const key = secretKey(secret);
  return await new SignJWT({
    tid: claims.tid,
    roles: claims.roles,
    typ: claims.typ,
    env: claims.env,
  })
    .setProtectedHeader({ alg: ALGORITHM })
    .setIssuer(claims.iss)
    .setAudience(claims.aud)
    .setSubject(claims.sub)
    .setJti(claims.jti)
    .setIssuedAt(claims.iat)
    .setExpirationTime(claims.exp)
    .sign(key);
}

export async function signRefreshToken(claims: RefreshClaims, secret: string): Promise<string> {
  RefreshClaimsSchema.parse(claims);
  const key = secretKey(secret);
  return await new SignJWT({
    typ: claims.typ,
    env: claims.env,
  })
    .setProtectedHeader({ alg: ALGORITHM })
    .setIssuer(claims.iss)
    .setAudience(claims.aud)
    .setSubject(claims.sub)
    .setJti(claims.jti)
    .setIssuedAt(claims.iat)
    .setExpirationTime(claims.exp)
    .sign(key);
}

/**
 * Throws AuthError for any §8 check failure. Caller still runs §8.5 revocation checks.
 * Maps jose's typed errors via instanceof (NOT substring matching on .message — that
 * was brittle; codex pass-1 BLOCK).
 *
 * jose error hierarchy (from `jose/errors`):
 *   - JOSEError (base)
 *     - JWTExpired                        → EXPIRED_TOKEN
 *     - JWTClaimValidationFailed          → WRONG_ISSUER / WRONG_AUDIENCE (check `claim` field)
 *     - JWSSignatureVerificationFailed    → INVALID_TOKEN
 *     - JWSInvalid / JWTInvalid           → MALFORMED_TOKEN
 *     - other JOSEError subclasses        → INVALID_TOKEN (fallback)
 */
export async function verifyTokenRaw(token: string, secret: string, env: EnvClaim): Promise<JWTPayload> {
  const key = secretKey(secret);
  try {
    const { payload } = await jwtVerify(token, key, {
      issuer: ISSUER,
      audience: AUDIENCE,
      algorithms: [ALGORITHM],
      clockTolerance: 30,
    });
    if (payload.env !== env) {
      throw new AuthError("WRONG_ENVIRONMENT", AUTH_ERROR_MESSAGES.WRONG_ENVIRONMENT);
    }
    return payload;
  } catch (e) {
    if (e instanceof AuthError) throw e;
    if (e instanceof JWTExpired) {
      throw new AuthError("EXPIRED_TOKEN", AUTH_ERROR_MESSAGES.EXPIRED_TOKEN);
    }
    if (e instanceof JWTClaimValidationFailed) {
      // jose attaches the failed-claim name to e.claim (e.g. 'iss', 'aud')
      const claim = (e as JWTClaimValidationFailed).claim;
      if (claim === "iss") throw new AuthError("WRONG_ISSUER", AUTH_ERROR_MESSAGES.WRONG_ISSUER);
      if (claim === "aud") throw new AuthError("WRONG_AUDIENCE", AUTH_ERROR_MESSAGES.WRONG_AUDIENCE);
      throw new AuthError("MALFORMED_TOKEN", AUTH_ERROR_MESSAGES.MALFORMED_TOKEN);
    }
    if (e instanceof JWSSignatureVerificationFailed) {
      throw new AuthError("INVALID_TOKEN", AUTH_ERROR_MESSAGES.INVALID_TOKEN);
    }
    if (e instanceof JWSInvalid || e instanceof JWTInvalid) {
      throw new AuthError("MALFORMED_TOKEN", AUTH_ERROR_MESSAGES.MALFORMED_TOKEN);
    }
    if (e instanceof JOSEError) {
      throw new AuthError("INVALID_TOKEN", AUTH_ERROR_MESSAGES.INVALID_TOKEN);
    }
    // Unknown error — re-throw to preserve diagnostics
    throw e;
  }
}

export { resolveEnvClaim, type EnvClaim };
```

- [ ] **Step 4.6: Write `packages/auth/src/__tests__/crypto.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { signAccessToken, verifyTokenRaw, assertJwtSecret } from "../crypto.js";
import type { AccessClaims } from "../claims.js";
import { AuthError } from "../errors.js";

const SECRET = "a".repeat(64);
const OTHER_SECRET = "b".repeat(64);

function makeAccessClaims(overrides: Partial<AccessClaims> = {}): AccessClaims {
  const now = Math.floor(Date.now() / 1000);
  return {
    sub: "550e8400-e29b-41d4-a716-446655440000",
    tid: "550e8400-e29b-41d4-a716-446655440001",
    roles: ["platform_admin"],
    typ: "access" as const,
    iat: now,
    exp: now + 900,
    jti: "550e8400-e29b-41d4-a716-446655440002",
    iss: "infinityrx" as const,
    aud: "infinityrx-backend" as const,
    env: "production" as const,
    ...overrides,
  };
}

describe("assertJwtSecret", () => {
  it("accepts a sufficiently long secret in any env", () => {
    expect(() => assertJwtSecret(SECRET, "production")).not.toThrow();
  });
  it("rejects a short secret", () => {
    expect(() => assertJwtSecret("short", "development")).toThrow(/≥32 chars/);
  });
  it("rejects dev placeholder secrets in production", () => {
    expect(() => assertJwtSecret("changeme".padEnd(64, "x"), "production")).toThrow(/dev placeholder/);
  });
});

describe("HS256 mint + verify round-trip", () => {
  it("a token minted with secret A verifies with secret A", async () => {
    const claims = makeAccessClaims();
    const token = await signAccessToken(claims, SECRET);
    const verified = await verifyTokenRaw(token, SECRET, "production");
    expect(verified.sub).toBe(claims.sub);
    expect(verified.tid).toBe(claims.tid);
    expect(verified.env).toBe("production");
  });

  it("a token minted with secret A fails verification with secret B (INVALID_TOKEN)", async () => {
    const token = await signAccessToken(makeAccessClaims(), SECRET);
    await expect(verifyTokenRaw(token, OTHER_SECRET, "production")).rejects.toBeInstanceOf(AuthError);
    await expect(verifyTokenRaw(token, OTHER_SECRET, "production")).rejects.toMatchObject({ code: "INVALID_TOKEN" });
  });

  it("a token minted with env=development fails verification with env=production (WRONG_ENVIRONMENT)", async () => {
    const token = await signAccessToken(makeAccessClaims({ env: "development" }), SECRET);
    await expect(verifyTokenRaw(token, SECRET, "production")).rejects.toMatchObject({ code: "WRONG_ENVIRONMENT" });
  });

  it("an expired token fails with EXPIRED_TOKEN", async () => {
    const now = Math.floor(Date.now() / 1000);
    const token = await signAccessToken(makeAccessClaims({ iat: now - 2000, exp: now - 1000 }), SECRET);
    await expect(verifyTokenRaw(token, SECRET, "production")).rejects.toMatchObject({ code: "EXPIRED_TOKEN" });
  });
});
```

- [ ] **Step 4.7: Update `packages/auth/src/index.ts`**

```ts
// Public surface of @infinityrx/auth.

export {
  AccessClaimsSchema,
  RefreshClaimsSchema,
  ISSUER,
  AUDIENCE,
  type AccessClaims,
  type RefreshClaims,
} from "./claims.js";

export {
  EnvClaimSchema,
  resolveEnvClaim,
  type EnvClaim,
} from "./env-claim.js";

export {
  signAccessToken,
  signRefreshToken,
  verifyTokenRaw,
  assertJwtSecret,
} from "./crypto.js";

export {
  AuthError,
  AUTH_ERROR_MESSAGES,
  type AuthErrorCode,
} from "./errors.js";
```

- [ ] **Step 4.8: Verify**

```
npm run typecheck
npm --workspace=@infinityrx/auth test
npm run lint:root
```

Expected: typecheck exit 0, 10 tests pass (6 claims + 4 crypto + assertJwtSecret's 3), lint exit 0.

Actually the test count breakdown: 6 (AccessClaimsSchema 6 + RefreshClaimsSchema 4 = 10) + (assertJwtSecret 3 + round-trip 4) = 17. Verify the count matches.

- [ ] **Step 4.9: Commit**

```bash
git add packages/auth/
git commit -m "feat(auth): claim types + crypto + env claim per SD-1 §2-§4

claims.ts: AccessClaimsSchema (sub, tid, roles, typ='access', iat,
exp, jti, iss='infinityrx', aud='infinityrx-backend', env) and
RefreshClaimsSchema (no tid, no roles). Both are zod schemas with
strict literal-typed iss/aud + env enum.

env-claim.ts: EnvClaimSchema enum + resolveEnvClaim() startup helper.

crypto.ts: HS256 sign/verify via jose, signAccessToken,
signRefreshToken, verifyTokenRaw (full §8 check chain except
revocation suite). Throws typed AuthError for INVALID_TOKEN /
EXPIRED_TOKEN / WRONG_ISSUER / WRONG_AUDIENCE / WRONG_ENVIRONMENT.
assertJwtSecret enforces SD-1 §4: ≥32 chars + production refuses
dev-placeholder secrets.

errors.ts: AuthError class + AUTH_ERROR_MESSAGES (stable per-code
messages — no information leak).

17 vitest tests: claim schemas (10), assertJwtSecret (3),
HS256 round-trip + cross-env rejection + cross-secret rejection +
expired-token (4).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: packages/auth — mint + verify chain + revocation repo interface

**Files:**
- Create: `packages/auth/src/mint.ts`
- Create: `packages/auth/src/verify.ts`
- Create: `packages/auth/src/revocation-repo.ts`
- Create: `packages/auth/src/__tests__/mint-and-verify.test.ts`
- Modify: `packages/auth/src/index.ts`

- [ ] **Step 5.1: Write `packages/auth/src/revocation-repo.ts`**

```ts
/**
 * Per SD-1 §8.5. The runtime implementation talks to Redis; tests use an
 * in-memory impl. The auth package only defines the interface — backend Python
 * code (out of SP-0 scope) implements the Redis client.
 *
 * Three key families:
 *   - `auth:revoked:<jti>`  — explicit revocation (logout / admin)
 *   - `auth:consumed:<jti>` — refresh-token atomic consume (set via SET NX)
 *   - `auth:tokens_valid_since:<sub>` — per-user cutoff (password reset / disable)
 */
export interface RevocationRepo {
  /** Check whether a jti is in the revoked set. */
  isRevoked(jti: string): Promise<boolean>;

  /** Atomic consume: returns true if THIS caller set the key (SET NX won), false if already-consumed (replay). */
  consumeRefresh(jti: string, reason: string, ttlSeconds: number): Promise<boolean>;

  /** Read the tokens_valid_since cutoff for a user, or null if no cutoff is set. */
  getTokensValidSince(sub: string): Promise<number | null>;

  /** Write the per-user cutoff (password reset / disable). */
  setTokensValidSince(sub: string, unixSeconds: number): Promise<void>;

  /** Mark a jti as revoked (logout / admin). */
  revoke(jti: string, reason: string, ttlSeconds: number): Promise<void>;
}

/**
 * In-memory implementation for tests. NEVER use in production — no durability,
 * no cross-process consistency.
 */
export class InMemoryRevocationRepo implements RevocationRepo {
  private readonly revoked = new Map<string, { reason: string; expiresAt: number }>();
  private readonly consumed = new Map<string, { reason: string; expiresAt: number }>();
  private readonly tokensValidSince = new Map<string, number>();

  private now(): number {
    return Math.floor(Date.now() / 1000);
  }

  async isRevoked(jti: string): Promise<boolean> {
    const entry = this.revoked.get(jti);
    if (!entry) return false;
    if (entry.expiresAt < this.now()) {
      this.revoked.delete(jti);
      return false;
    }
    return true;
  }

  async consumeRefresh(jti: string, reason: string, ttlSeconds: number): Promise<boolean> {
    if (this.consumed.has(jti)) {
      const entry = this.consumed.get(jti)!;
      if (entry.expiresAt >= this.now()) return false;
      this.consumed.delete(jti);
    }
    this.consumed.set(jti, { reason, expiresAt: this.now() + ttlSeconds });
    return true;
  }

  async getTokensValidSince(sub: string): Promise<number | null> {
    return this.tokensValidSince.get(sub) ?? null;
  }

  async setTokensValidSince(sub: string, unixSeconds: number): Promise<void> {
    this.tokensValidSince.set(sub, unixSeconds);
  }

  async revoke(jti: string, reason: string, ttlSeconds: number): Promise<void> {
    this.revoked.set(jti, { reason, expiresAt: this.now() + ttlSeconds });
  }
}
```

- [ ] **Step 5.2: Write `packages/auth/src/mint.ts`**

```ts
import { signAccessToken, signRefreshToken } from "./crypto.js";
import type { AccessClaims, RefreshClaims } from "./claims.js";
import type { EnvClaim } from "./env-claim.js";
import type { RevocationRepo } from "./revocation-repo.js";

const ACCESS_TTL_PROD_SECONDS = 15 * 60;
const ACCESS_TTL_DEV_SECONDS = 8 * 60 * 60;
const REFRESH_TTL_SECONDS = 8 * 60 * 60;

export interface MintAccessOptions {
  sub: string;
  tid: string;
  roles: string[];
  env: EnvClaim;
  secret: string;
  repo: RevocationRepo;
  /** Override iat (test seam). */
  now?: number;
}

export interface MintedTokens {
  access_token: string;
  refresh_token: string;
  expires_at: number;
}

/**
 * Per SD-1 §8.5 post-reset mint protection: clamp iat so it strictly exceeds
 * any tokens_valid_since[sub] cutoff. Same-second login after a reset is then
 * accepted, not auto-rejected by the inclusive `<=` rule.
 */
export async function mintTokenPair(opts: MintAccessOptions): Promise<MintedTokens> {
  const now = opts.now ?? Math.floor(Date.now() / 1000);
  const cutoff = await opts.repo.getTokensValidSince(opts.sub);
  const iat = Math.max(now, (cutoff ?? 0) + 1);
  const accessTtl = opts.env === "production" ? ACCESS_TTL_PROD_SECONDS : ACCESS_TTL_DEV_SECONDS;

  const accessClaims: AccessClaims = {
    sub: opts.sub,
    tid: opts.tid,
    roles: opts.roles,
    typ: "access",
    iat,
    exp: iat + accessTtl,
    jti: crypto.randomUUID(),
    iss: "infinityrx",
    aud: "infinityrx-backend",
    env: opts.env,
  };

  const refreshClaims: RefreshClaims = {
    sub: opts.sub,
    typ: "refresh",
    iat,
    exp: iat + REFRESH_TTL_SECONDS,
    jti: crypto.randomUUID(),
    iss: "infinityrx",
    aud: "infinityrx-backend",
    env: opts.env,
  };

  const [access_token, refresh_token] = await Promise.all([
    signAccessToken(accessClaims, opts.secret),
    signRefreshToken(refreshClaims, opts.secret),
  ]);

  return {
    access_token,
    refresh_token,
    expires_at: accessClaims.exp,
  };
}
```

- [ ] **Step 5.3: Write `packages/auth/src/verify.ts`**

```ts
import { verifyTokenRaw } from "./crypto.js";
import { AccessClaimsSchema, RefreshClaimsSchema, type AccessClaims, type RefreshClaims } from "./claims.js";
import { AuthError, AUTH_ERROR_MESSAGES } from "./errors.js";
import type { EnvClaim } from "./env-claim.js";
import type { RevocationRepo } from "./revocation-repo.js";

export interface VerifyOptions {
  token: string;
  secret: string;
  env: EnvClaim;
  repo: RevocationRepo;
}

/**
 * Full SD-1 §8 check chain for access tokens:
 *   §8 steps 1-8 (signature, claims, iss, aud, env, typ, exp)
 *   §8 step 9: revocation repo check (jti revoked? iat <= tokens_valid_since?)
 */
export async function verifyAccessToken(opts: VerifyOptions): Promise<AccessClaims> {
  const raw = await verifyTokenRaw(opts.token, opts.secret, opts.env);
  if (raw.typ !== "access") {
    throw new AuthError("WRONG_TOKEN_TYPE", AUTH_ERROR_MESSAGES.WRONG_TOKEN_TYPE);
  }
  const parsed = AccessClaimsSchema.safeParse(raw);
  if (!parsed.success) {
    throw new AuthError("MALFORMED_TOKEN", AUTH_ERROR_MESSAGES.MALFORMED_TOKEN);
  }
  const claims = parsed.data;

  try {
    if (await opts.repo.isRevoked(claims.jti)) {
      throw new AuthError("REVOKED_TOKEN", AUTH_ERROR_MESSAGES.REVOKED_TOKEN);
    }
    const cutoff = await opts.repo.getTokensValidSince(claims.sub);
    if (cutoff !== null && claims.iat <= cutoff) {
      throw new AuthError("REVOKED_TOKEN", AUTH_ERROR_MESSAGES.REVOKED_TOKEN);
    }
  } catch (e) {
    if (e instanceof AuthError) throw e;
    throw new AuthError("REVOCATION_CHECK_FAILED", AUTH_ERROR_MESSAGES.REVOCATION_CHECK_FAILED);
  }

  return claims;
}

/**
 * Refresh-endpoint validation per SD-1 §8.6:
 *   §8 steps 1-6 (signature, claims, iss, aud, env)
 *   typ MUST be 'refresh'
 *   §8 step 8 (exp)
 *   §8 step 9 revocation check (jti revoked? iat <= tokens_valid_since?)
 *   Redis reachability — already covered by repo error -> REVOCATION_CHECK_FAILED above
 * NOTE: this does NOT call consumeRefresh — that happens in the refresh adapter
 *   only after this returns successfully (atomic consume per §5/§8.6).
 */
export async function verifyRefreshToken(opts: VerifyOptions): Promise<RefreshClaims> {
  const raw = await verifyTokenRaw(opts.token, opts.secret, opts.env);
  if (raw.typ !== "refresh") {
    throw new AuthError("WRONG_TOKEN_TYPE", AUTH_ERROR_MESSAGES.WRONG_TOKEN_TYPE);
  }
  const parsed = RefreshClaimsSchema.safeParse(raw);
  if (!parsed.success) {
    throw new AuthError("MALFORMED_TOKEN", AUTH_ERROR_MESSAGES.MALFORMED_TOKEN);
  }
  const claims = parsed.data;

  try {
    if (await opts.repo.isRevoked(claims.jti)) {
      throw new AuthError("REVOKED_TOKEN", AUTH_ERROR_MESSAGES.REVOKED_TOKEN);
    }
    const cutoff = await opts.repo.getTokensValidSince(claims.sub);
    if (cutoff !== null && claims.iat <= cutoff) {
      throw new AuthError("REVOKED_TOKEN", AUTH_ERROR_MESSAGES.REVOKED_TOKEN);
    }
  } catch (e) {
    if (e instanceof AuthError) throw e;
    throw new AuthError("REVOCATION_CHECK_FAILED", AUTH_ERROR_MESSAGES.REVOCATION_CHECK_FAILED);
  }

  return claims;
}
```

- [ ] **Step 5.4: Write `packages/auth/src/__tests__/mint-and-verify.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { mintTokenPair } from "../mint.js";
import { verifyAccessToken, verifyRefreshToken } from "../verify.js";
import { InMemoryRevocationRepo } from "../revocation-repo.js";
import { AuthError } from "../errors.js";

const SECRET = "x".repeat(64);

function setup() {
  return {
    repo: new InMemoryRevocationRepo(),
    sub: "550e8400-e29b-41d4-a716-446655440000",
    tid: "550e8400-e29b-41d4-a716-446655440001",
    roles: ["platform_admin"] as string[],
  };
}

describe("mintTokenPair + verifyAccessToken happy path", () => {
  it("a freshly minted access token verifies cleanly", async () => {
    const { repo, sub, tid, roles } = setup();
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo });
    const claims = await verifyAccessToken({ token: tokens.access_token, secret: SECRET, env: "production", repo });
    expect(claims.sub).toBe(sub);
    expect(claims.tid).toBe(tid);
    expect(claims.roles).toEqual(roles);
    expect(claims.typ).toBe("access");
  });

  it("a freshly minted refresh token verifies cleanly", async () => {
    const { repo, sub, tid, roles } = setup();
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo });
    const claims = await verifyRefreshToken({ token: tokens.refresh_token, secret: SECRET, env: "production", repo });
    expect(claims.sub).toBe(sub);
    expect(claims.typ).toBe("refresh");
  });
});

describe("revocation paths", () => {
  it("a revoked access jti fails with REVOKED_TOKEN", async () => {
    const { repo, sub, tid, roles } = setup();
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo });
    // We need to extract the jti — decode unsafely (test-only). Use jose import for that... or extract via verify.
    const claims = await verifyAccessToken({ token: tokens.access_token, secret: SECRET, env: "production", repo });
    await repo.revoke(claims.jti, "logout", 1000);
    await expect(
      verifyAccessToken({ token: tokens.access_token, secret: SECRET, env: "production", repo }),
    ).rejects.toMatchObject({ code: "REVOKED_TOKEN" });
  });

  it("tokens_valid_since cutoff rejects pre-reset access tokens (inclusive <=)", async () => {
    const { repo, sub, tid, roles } = setup();
    const now = Math.floor(Date.now() / 1000);
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo, now });
    // Cutoff at the same second as iat — inclusive <= should reject the existing token...
    await repo.setTokensValidSince(sub, now);
    await expect(
      verifyAccessToken({ token: tokens.access_token, secret: SECRET, env: "production", repo }),
    ).rejects.toMatchObject({ code: "REVOKED_TOKEN" });
  });

  it("post-reset mint clamps iat to cutoff + 1 (same-second login is accepted)", async () => {
    const { repo, sub, tid, roles } = setup();
    const now = Math.floor(Date.now() / 1000);
    await repo.setTokensValidSince(sub, now);  // pretend reset just happened
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo, now });
    // The new token should verify because mint clamped iat to now+1 (strictly > cutoff)
    const claims = await verifyAccessToken({ token: tokens.access_token, secret: SECRET, env: "production", repo });
    expect(claims.iat).toBeGreaterThan(now);
  });
});

describe("typ enforcement", () => {
  it("an access token rejected at the refresh endpoint with WRONG_TOKEN_TYPE", async () => {
    const { repo, sub, tid, roles } = setup();
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo });
    await expect(
      verifyRefreshToken({ token: tokens.access_token, secret: SECRET, env: "production", repo }),
    ).rejects.toMatchObject({ code: "WRONG_TOKEN_TYPE" });
  });

  it("a refresh token rejected at protected route with WRONG_TOKEN_TYPE", async () => {
    const { repo, sub, tid, roles } = setup();
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo });
    await expect(
      verifyAccessToken({ token: tokens.refresh_token, secret: SECRET, env: "production", repo }),
    ).rejects.toMatchObject({ code: "WRONG_TOKEN_TYPE" });
  });
});

describe("InMemoryRevocationRepo consumeRefresh atomicity", () => {
  it("first consume returns true; second returns false (replay)", async () => {
    const { repo } = setup();
    const jti = crypto.randomUUID();
    expect(await repo.consumeRefresh(jti, "rotation", 1000)).toBe(true);
    expect(await repo.consumeRefresh(jti, "rotation", 1000)).toBe(false);
  });
});

// SD-1 §11 contract test #e — refresh token rejected after password reset.
describe("refresh after password reset", () => {
  it("a refresh token whose iat <= tokens_valid_since[sub] is rejected with REVOKED_TOKEN", async () => {
    const { repo, sub, tid, roles } = setup();
    const now = Math.floor(Date.now() / 1000);
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo, now });
    // Pretend admin / password-reset just disabled this user, setting cutoff at `now` (same second as token iat).
    await repo.setTokensValidSince(sub, now);
    await expect(
      verifyRefreshToken({ token: tokens.refresh_token, secret: SECRET, env: "production", repo }),
    ).rejects.toMatchObject({ code: "REVOKED_TOKEN" });
  });
});

// SD-1 §11 contract test #f — Redis-unreachable maps to REVOCATION_CHECK_FAILED.
// We use a throwing RevocationRepo to simulate Redis being down.
class UnreachableRevocationRepo {
  async isRevoked(): Promise<boolean> { throw new Error("ECONNREFUSED"); }
  async consumeRefresh(): Promise<boolean> { throw new Error("ECONNREFUSED"); }
  async getTokensValidSince(): Promise<number | null> { throw new Error("ECONNREFUSED"); }
  async setTokensValidSince(): Promise<void> { throw new Error("ECONNREFUSED"); }
  async revoke(): Promise<void> { throw new Error("ECONNREFUSED"); }
}

describe("Redis unreachable", () => {
  it("verifyAccessToken returns REVOCATION_CHECK_FAILED when repo throws", async () => {
    // Mint with a working repo first, then verify with a broken repo.
    const workingRepo = new InMemoryRevocationRepo();
    const sub = "550e8400-e29b-41d4-a716-446655440000";
    const tid = "550e8400-e29b-41d4-a716-446655440001";
    const tokens = await mintTokenPair({ sub, tid, roles: [], env: "production", secret: SECRET, repo: workingRepo });
    const brokenRepo = new UnreachableRevocationRepo();
    await expect(
      verifyAccessToken({ token: tokens.access_token, secret: SECRET, env: "production", repo: brokenRepo }),
    ).rejects.toMatchObject({ code: "REVOCATION_CHECK_FAILED" });
  });

  it("verifyRefreshToken returns REVOCATION_CHECK_FAILED when repo throws", async () => {
    const workingRepo = new InMemoryRevocationRepo();
    const sub = "550e8400-e29b-41d4-a716-446655440000";
    const tid = "550e8400-e29b-41d4-a716-446655440001";
    const tokens = await mintTokenPair({ sub, tid, roles: [], env: "production", secret: SECRET, repo: workingRepo });
    const brokenRepo = new UnreachableRevocationRepo();
    await expect(
      verifyRefreshToken({ token: tokens.refresh_token, secret: SECRET, env: "production", repo: brokenRepo }),
    ).rejects.toMatchObject({ code: "REVOCATION_CHECK_FAILED" });
  });
});
```

- [ ] **Step 5.5: Update `packages/auth/src/index.ts`**

Add to existing exports:

```ts
export { mintTokenPair, type MintAccessOptions, type MintedTokens } from "./mint.js";
export { verifyAccessToken, verifyRefreshToken, type VerifyOptions } from "./verify.js";
export {
  InMemoryRevocationRepo,
  type RevocationRepo,
} from "./revocation-repo.js";
```

- [ ] **Step 5.6: Verify**

```
npm run typecheck
npm --workspace=@infinityrx/auth test
npm run lint:root
```

Expected: typecheck exit 0, ~28 tests pass (17 from Task 4 + 8 atomic-consume/typ/revocation from Task 5 + 3 password-reset/Redis-unreachable added in v2), lint exit 0.

- [ ] **Step 5.7: Commit**

```bash
git add packages/auth/
git commit -m "feat(auth): mint + verify chain + revocation repo interface per SD-1 §5/§8

revocation-repo.ts: RevocationRepo interface (isRevoked,
consumeRefresh, getTokensValidSince, setTokensValidSince, revoke)
+ InMemoryRevocationRepo for tests. Production Redis impl is in
the backend Python wave, not Plan B scope.

mint.ts: mintTokenPair() applies SD-1 §8.5 post-reset clamping
(iat = max(now, cutoff+1)) so same-second post-reset login is not
auto-rejected.

verify.ts: verifyAccessToken + verifyRefreshToken implement the
full SD-1 §8 + §8.5 check chain. Returns typed claims or throws
AuthError with one of the §8 error codes (REVOKED_TOKEN,
WRONG_TOKEN_TYPE, MALFORMED_TOKEN, REVOCATION_CHECK_FAILED).
Note: verifyRefreshToken does NOT call consumeRefresh — that's
the refresh-adapter's job (Task 6) after verify returns success,
per the SD-1 §8.6 ordering.

8 vitest tests covering: happy path mint+verify (access+refresh),
revocation via revoke(), tokens_valid_since cutoff (inclusive <=
rejection), post-reset mint clamping, typ enforcement at both
endpoints, InMemoryRevocationRepo consume atomicity.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: packages/auth — refresh adapter + single-flight + dev JWT

**Files:**
- Create: `packages/auth/src/refresh-adapter.ts`
- Create: `packages/auth/src/single-flight.ts`
- Create: `packages/auth/src/dev-jwt.ts`
- Create: `packages/auth/src/__tests__/refresh-rotation.test.ts`
- Create: `packages/auth/src/__tests__/single-flight.test.ts`
- Create: `packages/auth/src/__tests__/dev-jwt.test.ts`
- Modify: `packages/auth/src/index.ts`

- [ ] **Step 6.1: Write `packages/auth/src/refresh-adapter.ts`**

```ts
import { mintTokenPair, type MintedTokens } from "./mint.js";
import { verifyRefreshToken } from "./verify.js";
import { AuthError, AUTH_ERROR_MESSAGES } from "./errors.js";
import type { EnvClaim } from "./env-claim.js";
import type { RevocationRepo } from "./revocation-repo.js";

const CONSUMED_TTL_SECONDS = 8 * 60 * 60 + 60;  // refresh TTL + 60s skew margin per SD-1 §8.5

export interface RefreshAdapterOptions {
  refreshToken: string;
  secret: string;
  env: EnvClaim;
  repo: RevocationRepo;
  /** Looked up from the auth provider's session payload. Used to mint a fresh access claims with the user's current tid/roles. */
  loadUserContext: (sub: string) => Promise<{ tid: string; roles: string[] }>;
}

/**
 * Per SD-1 §8.6: full §8 verification, then atomic consume, then mint pair.
 * Only the atomic-consume winner mints new tokens; replay returns REFRESH_REPLAY.
 */
export async function performRefresh(opts: RefreshAdapterOptions): Promise<MintedTokens> {
  // Step 1-6 of §8.6: full verify (signature, claims, iss/aud/env, typ=refresh, exp, revocation suite)
  const claims = await verifyRefreshToken({
    token: opts.refreshToken,
    secret: opts.secret,
    env: opts.env,
    repo: opts.repo,
  });

  // Step 7 of §8.6: atomic consume. Winner of the SET NX race proceeds; replay rejects.
  let consumed: boolean;
  try {
    consumed = await opts.repo.consumeRefresh(claims.jti, "rotation", CONSUMED_TTL_SECONDS);
  } catch (e) {
    throw new AuthError("REVOCATION_CHECK_FAILED", AUTH_ERROR_MESSAGES.REVOCATION_CHECK_FAILED);
  }
  if (!consumed) {
    throw new AuthError("REFRESH_REPLAY", AUTH_ERROR_MESSAGES.REFRESH_REPLAY);
  }

  // Step 8 of §8.6: mint a new pair.
  const userCtx = await opts.loadUserContext(claims.sub);
  return await mintTokenPair({
    sub: claims.sub,
    tid: userCtx.tid,
    roles: userCtx.roles,
    env: opts.env,
    secret: opts.secret,
    repo: opts.repo,
  });
}
```

- [ ] **Step 6.2: Write `packages/auth/src/single-flight.ts`**

```ts
import { AuthError } from "./errors.js";

/**
 * Per SD-1 §11 portal adoption: concurrent invocations of the jwt() callback
 * (or any client-side refresh trigger) keyed by the SAME refresh jti must
 * coalesce to ONE network call. Without coalescing, two simultaneous attempts
 * to refresh the same token race the SET NX atomic-consume — one wins, the
 * other gets REFRESH_REPLAY, and the user sees a spurious logout.
 */
export class SingleFlightRefresh<T> {
  private inflight = new Map<string, Promise<T>>();

  /**
   * If a refresh keyed by this `key` (typically the current refresh JTI) is
   * already in flight, return its promise. Otherwise start one.
   */
  run(key: string, fn: () => Promise<T>): Promise<T> {
    const existing = this.inflight.get(key);
    if (existing) return existing;
    const promise = fn().finally(() => {
      // Clear the slot when the work finishes (success OR error). Subsequent
      // calls with the same key after this point will re-run.
      // Cleared synchronously inside finally → ensures the slot is released
      // even if the caller awaits in a finally{} that throws.
      this.inflight.delete(key);
    });
    this.inflight.set(key, promise);
    return promise;
  }

  /** Number of in-flight refreshes (mostly for test assertions). */
  size(): number {
    return this.inflight.size;
  }
}

/**
 * Test/observability helper: extract the JTI from a refresh JWT WITHOUT
 * verifying it. NEVER use for security decisions — verify the token before
 * trusting any claim. Used purely as the single-flight key.
 */
export function readJtiUnsafe(token: string): string {
  const parts = token.split(".");
  if (parts.length !== 3) throw new AuthError("MALFORMED_TOKEN", "Token is not a JWT (3 parts)");
  try {
    const payload = JSON.parse(
      Buffer.from(parts[1]!.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf8"),
    ) as { jti?: string };
    if (typeof payload.jti !== "string") {
      throw new AuthError("MALFORMED_TOKEN", "Token payload missing jti");
    }
    return payload.jti;
  } catch (e) {
    if (e instanceof AuthError) throw e;
    throw new AuthError("MALFORMED_TOKEN", "Token payload is not valid JSON");
  }
}
```

- [ ] **Step 6.3: Write `packages/auth/src/dev-jwt.ts`**

```ts
import { mintTokenPair, type MintedTokens } from "./mint.js";
import type { EnvClaim } from "./env-claim.js";
import type { RevocationRepo } from "./revocation-repo.js";

export interface DevJwtOptions {
  sub?: string;
  tid?: string;
  roles?: string[];
  env: EnvClaim;
  secret: string;
  repo: RevocationRepo;
}

const DEV_ADMIN_ID = "00000000-0000-4000-8000-000000000001";
const DEV_TENANT_ID = "00000000-0000-4000-8000-000000000002";

/**
 * Per SD-1 §7: single source of truth for dev/test JWT issuance. Refuses to
 * mint in production. Mints with `env != "production"` so prod backends with
 * INFINITYRX_ENV=production reject the token via the WRONG_ENVIRONMENT check.
 */
export async function mintDevJwt(opts: DevJwtOptions): Promise<MintedTokens> {
  if (opts.env === "production") {
    throw new Error(
      "mintDevJwt refused: env=production. Dev paths must not run in production. " +
      "Set INFINITYRX_ENV=development or mock.",
    );
  }
  return await mintTokenPair({
    sub: opts.sub ?? DEV_ADMIN_ID,
    tid: opts.tid ?? DEV_TENANT_ID,
    roles: opts.roles ?? ["platform_admin"],
    env: opts.env,
    secret: opts.secret,
    repo: opts.repo,
  });
}

export const DEV_IDENTITY = {
  sub: DEV_ADMIN_ID,
  tid: DEV_TENANT_ID,
} as const;
```

- [ ] **Step 6.4: Write `packages/auth/src/__tests__/refresh-rotation.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { mintTokenPair } from "../mint.js";
import { performRefresh } from "../refresh-adapter.js";
import { InMemoryRevocationRepo } from "../revocation-repo.js";

const SECRET = "r".repeat(64);

async function setup() {
  const repo = new InMemoryRevocationRepo();
  const sub = "550e8400-e29b-41d4-a716-446655440000";
  const tid = "550e8400-e29b-41d4-a716-446655440001";
  const roles = ["platform_admin"];
  const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo });
  const loadUserContext = async () => ({ tid, roles });
  return { repo, sub, tid, roles, tokens, loadUserContext };
}

describe("performRefresh", () => {
  it("a fresh refresh token rotates to a new pair", async () => {
    const { repo, tokens, loadUserContext } = await setup();
    const newPair = await performRefresh({
      refreshToken: tokens.refresh_token,
      secret: SECRET,
      env: "production",
      repo,
      loadUserContext,
    });
    expect(newPair.access_token).not.toBe(tokens.access_token);
    expect(newPair.refresh_token).not.toBe(tokens.refresh_token);
  });

  it("the same refresh token used twice yields REFRESH_REPLAY on the second call", async () => {
    const { repo, tokens, loadUserContext } = await setup();
    await performRefresh({
      refreshToken: tokens.refresh_token, secret: SECRET, env: "production", repo, loadUserContext,
    });
    await expect(
      performRefresh({
        refreshToken: tokens.refresh_token, secret: SECRET, env: "production", repo, loadUserContext,
      }),
    ).rejects.toMatchObject({ code: "REFRESH_REPLAY" });
  });

  it("two concurrent refresh attempts race: exactly one wins, the other gets REFRESH_REPLAY", async () => {
    const { repo, tokens, loadUserContext } = await setup();
    const a = performRefresh({
      refreshToken: tokens.refresh_token, secret: SECRET, env: "production", repo, loadUserContext,
    });
    const b = performRefresh({
      refreshToken: tokens.refresh_token, secret: SECRET, env: "production", repo, loadUserContext,
    });
    const results = await Promise.allSettled([a, b]);
    const fulfilled = results.filter((r) => r.status === "fulfilled");
    const rejected = results.filter((r) => r.status === "rejected");
    expect(fulfilled.length).toBe(1);
    expect(rejected.length).toBe(1);
    expect((rejected[0] as PromiseRejectedResult).reason).toMatchObject({ code: "REFRESH_REPLAY" });
  });

  it("a refresh token revoked via logout yields REVOKED_TOKEN, not REFRESH_REPLAY", async () => {
    const { repo, tokens, loadUserContext } = await setup();
    // Read the jti without consuming
    const { readJtiUnsafe } = await import("../single-flight.js");
    const jti = readJtiUnsafe(tokens.refresh_token);
    await repo.revoke(jti, "logout", 1000);
    await expect(
      performRefresh({
        refreshToken: tokens.refresh_token, secret: SECRET, env: "production", repo, loadUserContext,
      }),
    ).rejects.toMatchObject({ code: "REVOKED_TOKEN" });
  });
});
```

- [ ] **Step 6.5: Write `packages/auth/src/__tests__/single-flight.test.ts`**

```ts
import { describe, it, expect, vi } from "vitest";
import { SingleFlightRefresh } from "../single-flight.js";

describe("SingleFlightRefresh", () => {
  it("coalesces concurrent calls with the same key to one execution", async () => {
    const sf = new SingleFlightRefresh<number>();
    const fn = vi.fn(async () => {
      await new Promise((r) => setTimeout(r, 10));
      return 42;
    });
    const [a, b, c] = await Promise.all([
      sf.run("k", fn),
      sf.run("k", fn),
      sf.run("k", fn),
    ]);
    expect(a).toBe(42);
    expect(b).toBe(42);
    expect(c).toBe(42);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("different keys do not coalesce", async () => {
    const sf = new SingleFlightRefresh<string>();
    const fn1 = vi.fn(async () => "a");
    const fn2 = vi.fn(async () => "b");
    const [a, b] = await Promise.all([sf.run("k1", fn1), sf.run("k2", fn2)]);
    expect(a).toBe("a");
    expect(b).toBe("b");
    expect(fn1).toHaveBeenCalledTimes(1);
    expect(fn2).toHaveBeenCalledTimes(1);
  });

  it("after the in-flight resolves, the next call with the same key runs again", async () => {
    const sf = new SingleFlightRefresh<number>();
    let counter = 0;
    const fn = async () => ++counter;
    await sf.run("k", fn);
    await sf.run("k", fn);
    expect(counter).toBe(2);
  });

  it("after the in-flight rejects, the next call with the same key runs again", async () => {
    const sf = new SingleFlightRefresh<number>();
    let counter = 0;
    const fn = async () => {
      counter++;
      if (counter === 1) throw new Error("first call fails");
      return counter;
    };
    await expect(sf.run("k", fn)).rejects.toThrow("first call fails");
    expect(await sf.run("k", fn)).toBe(2);
  });
});
```

- [ ] **Step 6.6: Write `packages/auth/src/__tests__/dev-jwt.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { mintDevJwt } from "../dev-jwt.js";
import { verifyAccessToken } from "../verify.js";
import { InMemoryRevocationRepo } from "../revocation-repo.js";

const SECRET = "d".repeat(64);

describe("mintDevJwt", () => {
  it("mints a valid token in development", async () => {
    const repo = new InMemoryRevocationRepo();
    const tokens = await mintDevJwt({ env: "development", secret: SECRET, repo });
    const claims = await verifyAccessToken({
      token: tokens.access_token, secret: SECRET, env: "development", repo,
    });
    expect(claims.env).toBe("development");
    expect(claims.roles).toContain("platform_admin");
  });

  it("refuses to mint in production", async () => {
    const repo = new InMemoryRevocationRepo();
    await expect(
      mintDevJwt({ env: "production", secret: SECRET, repo }),
    ).rejects.toThrow(/refused/i);
  });

  it("dev token rejected by prod backend (WRONG_ENVIRONMENT)", async () => {
    const repo = new InMemoryRevocationRepo();
    const tokens = await mintDevJwt({ env: "development", secret: SECRET, repo });
    // Prod backend would verify with env='production'; dev token has env='development'
    await expect(
      verifyAccessToken({ token: tokens.access_token, secret: SECRET, env: "production", repo }),
    ).rejects.toMatchObject({ code: "WRONG_ENVIRONMENT" });
  });
});
```

- [ ] **Step 6.7: Update `packages/auth/src/index.ts`**

Add to exports:

```ts
export { performRefresh, type RefreshAdapterOptions } from "./refresh-adapter.js";
export { SingleFlightRefresh, readJtiUnsafe } from "./single-flight.js";
export { mintDevJwt, DEV_IDENTITY, type DevJwtOptions } from "./dev-jwt.js";
```

- [ ] **Step 6.8: Verify**

```
npm run typecheck
npm --workspace=@infinityrx/auth test
npm run lint:root
```

Expected: typecheck exit 0, ~39 tests pass (28 from prior + 4 refresh + 4 single-flight + 3 dev-jwt = 39), lint exit 0.

- [ ] **Step 6.9: Commit**

```bash
git add packages/auth/
git commit -m "feat(auth): refresh adapter + single-flight + dev JWT per SD-1 §7/§8.6/§11

refresh-adapter.ts: performRefresh() implements SD-1 §8.6 — full verify
chain → atomic consume → mint new pair. Atomic-consume winners proceed
to mint; replay returns REFRESH_REPLAY. Distinct from REVOKED_TOKEN
(logout/admin/password-reset) per §8.5/§8.6.

single-flight.ts: SingleFlightRefresh<T> coalesces concurrent refresh
attempts keyed by refresh jti so two simultaneous tab refreshes don't
race the atomic-consume. readJtiUnsafe() extracts the jti without
verifying (test/observability only — never for security decisions).

dev-jwt.ts: mintDevJwt() — single source of truth for dev/test JWT
issuance per SD-1 §7. Refuses in production. Mints with env != production
so prod backends reject via WRONG_ENVIRONMENT cryptographic tripwire.

11 vitest tests: refresh happy path, replay rejection on serial reuse,
concurrent race (exactly 1 wins / 1 REFRESH_REPLAY), revoked refresh
returns REVOKED_TOKEN (not REFRESH_REPLAY), single-flight coalescing,
different-key isolation, post-resolve re-run, post-reject re-run, dev
mint accepted in dev, dev mint refused in prod, dev token rejected
by prod backend.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: framework-agnostic tests + CI extension + acceptance doc

**Files:**
- Create: `packages/contract/src/__tests__/framework-agnostic.test.ts`
- Create: `packages/auth/src/__tests__/framework-agnostic.test.ts`
- Modify: `.github/workflows/sp0-foundation.yml` (extend test step)
- Modify: `package.json` root scripts (add `test:packages`)
- Create: `docs/superpowers/plans/2026-05-15-sp0-plan-b-status.md`

- [ ] **Step 7.1: Write `packages/contract/src/__tests__/framework-agnostic.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const SRC_DIR = join(here, "..");

function walk(dir: string, files: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === "__tests__") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, files);
    else if (entry.endsWith(".ts")) files.push(full);
  }
  return files;
}

const FORBIDDEN_IMPORTS = [
  /from\s+["']next\//,
  /from\s+["']next-auth\//,
  /from\s+["']@auth\//,
  /require\(\s*["']next\//,
  /require\(\s*["']next-auth\//,
  /require\(\s*["']@auth\//,
];

describe("framework-agnostic enforcement", () => {
  const tsFiles = walk(SRC_DIR);

  it("there is at least one .ts file under packages/contract/src/", () => {
    expect(tsFiles.length).toBeGreaterThan(0);
  });

  for (const file of tsFiles) {
    it(`${file.replace(SRC_DIR, "")} does not import Next.js / next-auth / @auth/*`, () => {
      const contents = readFileSync(file, "utf8");
      for (const pattern of FORBIDDEN_IMPORTS) {
        expect(contents, `forbidden import matching ${pattern} in ${file}`).not.toMatch(pattern);
      }
    });
  }
});
```

- [ ] **Step 7.2: Write `packages/auth/src/__tests__/framework-agnostic.test.ts`**

Same content as Task 7.1's test, but with SRC_DIR resolving to `packages/auth/src/`. Adapt the path math accordingly.

- [ ] **Step 7.3: Extend `package.json` root scripts**

Add a `test:packages` script that runs every workspace's `test`:

```json
"test:packages": "npm run test --workspaces --if-present"
```

Keep the existing `test` script (which points at `@infinityrx/scripts test` from Plan A) — or update it to also fan out. Decide based on existing wiring; safe choice: leave existing `test` alone and add `test:packages` as the multi-workspace one.

- [ ] **Step 7.4: Extend `.github/workflows/sp0-foundation.yml` test step**

Find this block:

```yaml
      - name: Scripts tests (vitest)
        run: npm --workspace=@infinityrx/scripts test
```

Replace with:

```yaml
      - name: All package tests (vitest)
        run: npm run test:packages
```

Verify `package-lock.json` isn't accidentally broken by the script rename.

- [ ] **Step 7.5: Run full CI sequence locally**

```bash
npm install
npm run lint:root
npm run typecheck
npm run manifest:validate
npm run manifest:validate:standalone
npm run test:packages
```

Expected: all exit 0. test:packages runs scripts (10) + contract (25) + auth (~39) tests = ~74 total. All pass.

- [ ] **Step 7.6: Write acceptance status doc**

Create `docs/superpowers/plans/2026-05-15-sp0-plan-b-status.md` following the Plan A status doc pattern. Include:
- Status: Complete <date>
- Final commit SHA (filled in after the commit)
- Table of task SHAs (Plan B Tasks 1-7)
- What ships (both packages, list each surface module)
- What is NOT in Plan B (the other 12 backend clients per-vertical; portal/operator wiring per Plan C; backend Python implementation of refresh endpoint + Redis repo per separate wave)
- Verification commands + results
- Note on known pre-existing portal/operator lint warnings (still 3 issues unrelated to Plan B)
- Decision: ready for Plan C (packages/ui + packages/qa-harness + packages/shell)

- [ ] **Step 7.7: Commit Task 7 + Plan B status doc**

```bash
git add packages/contract/ packages/auth/ package.json .github/workflows/sp0-foundation.yml docs/superpowers/plans/2026-05-15-sp0-plan-b-status.md
git commit -m "feat(sp-0): Plan B Task 7 — framework-agnostic tests + CI extension + status doc

framework-agnostic.test.ts in both packages: walks src/ and asserts
no file matches /from ['\"]next\\// or /from ['\"]next-auth\\// or
/from ['\"]@auth\\//, including require() forms. This is a
belt-and-suspenders check on top of Plan A's ESLint Block B which
already bans these imports in packages/**.

test:packages root script runs every workspace's test. CI workflow's
test step replaced with npm run test:packages so contract + auth
suites both run on every push.

Plan B status doc records all 7 task SHAs, ships list, deferred-scope
list, verification commands. Decision: ready for Plan C.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Plan B — Done

After Task 7's commit, Plan B is complete. The repo now has packages/contract + packages/auth wired through the workspace, both passing tests, both lint-clean, both type-checked, and integrated into the CI workflow.

Plan C scope: packages/ui + packages/qa-harness + packages/shell — written after Plan B execution lands.

---

## Self-Review Checklist (applied 2026-05-15)

### Spec coverage

| Spec section | Plan B covers? | Notes |
|---|---|---|
| Main spec §6.1 packages/contract | YES | Error envelope, cache policy, base client, 1 reference client (prescriber-directory) |
| Main spec §6.2 packages/auth (SUPERSEDED BY SD-1) | YES | All SD-1 §2-§8 contract surfaces shipped in TypeScript |
| SD-1 §2 access claims | YES | AccessClaimsSchema with all 10 claims |
| SD-1 §3 refresh claims | YES | RefreshClaimsSchema without tid/roles |
| SD-1 §4 crypto | YES | HS256, per-env JWT_SECRET, assertJwtSecret, env claim |
| SD-1 §5 expiry & refresh | YES | mintTokenPair clamping, performRefresh atomic consume |
| SD-1 §6 cookie/session | PARTIAL — types only | Cookie config is Plan C (portal/operator next-auth wiring) |
| SD-1 §7 dev JWT | YES | mintDevJwt with prod refusal + env mismatch |
| SD-1 §8 backend validation | YES (TypeScript shape) | verifyAccessToken implements the §8 check chain; Python backend implementation is separate wave |
| SD-1 §8.5 revocation repo | INTERFACE ONLY | TypeScript interface + InMemoryRepo for tests; Redis Python impl is separate wave |
| SD-1 §8.6 refresh endpoint | YES (client side) | performRefresh implements the §8.6 ordering; the backend endpoint itself is Python |
| SD-1 §11 portal adoption | PARTIAL | TypeScript helpers (performRefresh, SingleFlightRefresh, readJtiUnsafe) ready for Plan C portal wiring |
| Main spec §11 scope discipline | YES | One reference client; modules-as-products not duplicated here |

The PARTIAL items are intentional — they live in Plan C (portal/operator wiring) or a separate Python backend wave.

### Placeholder scan

Searched the plan for "TBD", "TODO", "implement later", "fill in", "Add appropriate", "similar to". None found. Every step has either complete code, exact commands, or an exact file path with content elsewhere in the plan.

### Type consistency

- `AccessClaims`, `RefreshClaims`, `MintedTokens`, `RevocationRepo`, `EnvClaim`, `AuthError`, `AuthErrorCode` are defined in Task 4-5 and referenced consistently in Tasks 5-6.
- `BaseClient`, `ClientConfig`, `ClientFactory`, `CachePolicy`, `ErrorEnvelope` are defined in Task 2 and referenced consistently in Task 3.
- `PrescriberDirectoryClient` extends `BaseClient` with `name: "prescriber-directory"` literal.
- All imports use `.js` extensions (NodeNext + verbatimModuleSyntax requirement).

No issues found.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-15-sp0-plan-b-contract-auth.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, two-stage review, same pattern as Plan A.

**2. Inline Execution** — batch via executing-plans.

Which approach?
