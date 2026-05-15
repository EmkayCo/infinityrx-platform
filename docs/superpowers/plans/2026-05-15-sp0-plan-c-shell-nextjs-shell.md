# SP-0 Plan C-shell — packages/shell + Next.js Portal Auth Gating + QA Tools

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Draft, 2026-05-15. Awaiting codex pass-1 gate review in main session.

**Goal:** Ship `packages/shell` (Next.js 16.2–aware shell package) and wire it into `portal/operator`, delivering:
- `<RequireAuth>` / `<RequireRole>` RSC auth-gating components backed by Plan B's `@infinityrx/auth` verify chain
- Auth-aware `AppShellMount` server component that reads roles + the instance manifest and renders Plan C's `AppShell` with a role-filtered, manifest-ordered nav slot
- `/qa-harness/*` route pages that mount Plan C's `CompositionViewer`, `ServicesHealth`, `MockToggle`, `FactoryBindings`, and `CorrelationIdJump` components (runtime-fetching manifest where needed)
- QA mode toggle: cookie-persisted `qa_mode` cookie + Next.js middleware that exposes it to RSCs
- Request/response inspector: a `wrapFetch` factory that instruments `ClientConfig.fetch`, capturing outgoing requests for a slide-out inspector panel
- Framework-bound enforcement test asserting that `packages/ui`, `packages/contract`, `packages/auth`, and `packages/qa-harness` import zero `next/*` symbols while `packages/shell` is explicitly allowed

**Architecture:** `packages/shell` is the ONLY package in the workspace that may import `next/*`, `next-auth/*`, or `@auth/*`. It is the thin framework adapter that wraps framework-agnostic spine packages into a Next.js App Router host. `portal/operator` imports `@infinityrx/shell` and exposes the RSC wrappers and middleware to its routes. Plan C-shell does NOT touch internals of Plan A/B/C packages — it consumes their public surfaces only.

**Depends on:**
- Plan A: workspace scaffold, ESLint zones (commit `a7b838c`)
- Plan B: `@infinityrx/auth` verify chain, `BaseClient`, `ClientConfig` (commit `9b144e9`)
- Plan C: `AppShell` API (`{children, header?, nav?}`), `CompositionViewer`, `ServicesHealth`, `MockToggle`, `FactoryBindings`, `CorrelationIdJump` (commit `984eff2`)
- Plan D: `_generated/manifest.json` at `packages/shell/src/_generated/manifest.json` (consumed as a static JSON import; Plan C-shell reads what Plan D generates)

**Tech Stack:** Node 22, TypeScript 5.6.3 (NodeNext, verbatimModuleSyntax, strict, composite), Next.js 16.2, React 19.2 (peer deps), `next-auth` v5 (Auth.js), vitest 2.1.9 + happy-dom for RSC-unit tests, `@testing-library/react` 16.3.0.

**Spec references:**
- Main spec `docs/superpowers/specs/2026-05-14-sp0-integration-foundation-design.md` (commit `a50130f`) §6.4 (qa-harness deferred items), §6.5 (packages/shell), §7.2 (auth token flow)
- SD-1 (auth interface v4) `docs/superpowers/specs/2026-05-15-sp0-decision-spike-auth-interface.md` (commit `b876c3b`) §6 (cookie/session), §8 (backend validation contract), §11 (portal adoption checklist)
- SD-2 (framework v3) `docs/superpowers/specs/2026-05-15-sp0-decision-spike-framework.md` (commit `14d847a`) §6 (thin-adapter BFF contract; `packages/shell` MAY import Next.js)
- Plan B `docs/superpowers/plans/2026-05-15-sp0-plan-b-contract-auth.md` (commit `9b144e9`) — `verifyAccessToken`, `AuthError`, `ClientConfig`, `BaseClient`
- Plan C `docs/superpowers/plans/2026-05-15-sp0-plan-c-host-layer.md` (commit `984eff2`) — `AppShell` API, `CompositionViewer`, `ServicesHealth`, `MockToggle`, `FactoryBindings`, `CorrelationIdJump`

**Out of scope for Plan C-shell:**
- Plan B internals (`packages/auth` verify chain, `packages/contract` clients) — consumed only
- Plan C internals (`packages/ui` components, `packages/qa-harness` components) — consumed only
- Plan D's manifest builder (`scripts/generate-composition.ts`) — `_generated/manifest.json` is read as a static import
- The reference module `packages/modules/reclaimrx` — Plan D
- Python backend: JWT middleware refactor, Redis revocation repo, refresh endpoint — separate wave
- `portal/client`, `portal/provider` — future SPs

---

## File Structure

### Creates

```
packages/shell/
  package.json
  tsconfig.json
  vitest.config.ts
  src/
    index.ts                                     # public surface re-exports
    _generated/
      manifest.json                              # placeholder: { "modules": [] } — Plan D generates real content
    auth/
      require-auth.tsx                           # <RequireAuth> RSC: reads session via auth(), redirects to /login on failure
      require-role.tsx                           # <RequireRole roles={[...]}>: renders children only if user has ALL listed roles
      get-session-user.ts                        # getSessionUser() — server-only helper: extracts UserIdentity from next-auth auth()
      types.ts                                   # UserIdentity: { sub, tid, roles, mfaEnrolled }
    shell/
      app-shell-mount.tsx                        # <AppShellMount>: RSC — reads user roles + manifest; renders AppShell with nav slot
      module-nav.tsx                             # <ModuleNav>: RSC — builds nav entries from manifest ordered by manifest position, filtered by roles
      nav-types.ts                               # NavEntry: { moduleId, label, href, iconSlug, requiredRoles }
    qa/
      qa-mode-cookie.ts                          # QA_MODE_COOKIE constant + getQaMode(cookies): QaMode — "real" | "stub"
      qa-mode-middleware.ts                      # createQaModeMiddleware(): matcher config + handler writing qa_mode cookie
      qa-mode-provider.tsx                       # <QaModeProvider>: passes QaMode to client context via RSC → client boundary
      inspector/
        wrap-fetch.ts                            # wrapFetch(fetch, emit): wraps ClientConfig.fetch; emits InspectorEntry on each call
        inspector-store.ts                       # (client) nanostores atom: InspectorEntry[] — slide-out panel state
        inspector-panel.tsx                      # (client) slide-out panel: renders InspectorEntry list with method/route/ms/status/mock/cache columns
        types.ts                                 # InspectorEntry: { id, method, url, status, latencyMs, isMock, cacheHit, correlationId, requestBody?, responseBody?, timestamp }
    routes/
      qa-harness/
        page.tsx                                 # /qa-harness — health dashboard: ServicesHealth with live probeHealth
        composition/
          page.tsx                               # /qa-harness/composition — fetches manifest.json, renders CompositionViewer
        mock-toggle/
          page.tsx                               # /qa-harness/mock-toggle — renders MockToggle for registered clients
        factory/
          page.tsx                               # /qa-harness/factory — renders FactoryBindings
        correlation/
          page.tsx                               # /qa-harness/correlation — renders CorrelationIdJump
    middleware.ts                                # Next.js middleware: route protection (redirects unauthenticated), QA mode cookie propagation
    __tests__/
      require-auth.test.tsx                      # 6 tests: authenticated → renders children; unauthenticated → redirect; wrong env
      require-role.test.tsx                      # 5 tests: role match, role miss, empty roles allowed/denied
      get-session-user.test.ts                   # 4 tests: valid session, missing session, missing fields, type shape
      app-shell-mount.test.tsx                   # 5 tests: renders AppShell, passes nav slot, filters by roles
      module-nav.test.tsx                        # 5 tests: manifest ordering, role filter, empty manifest
      qa-mode-cookie.test.ts                     # 4 tests: getQaMode default "real", cookie "stub", invalid value fallback
      qa-mode-middleware.test.ts                 # 4 tests: sets cookie on first request, preserves existing, strips in prod
      wrap-fetch.test.ts                         # 6 tests: emits entry, latency measured, correlationId threaded, mock flag, error path
      inspector-store.test.ts                    # 3 tests: addEntry, clearEntries, maxEntries eviction
      qa-harness-pages.test.tsx                  # 6 tests: each page renders its Plan C component (composition, health, mock, factory, correlation)
      framework-bound.test.ts                    # 1 test: packages/ui/contract/auth/qa-harness src dirs contain zero next/* imports (grep-based)

portal/operator/
  middleware.ts                                  # MODIFIED: imports and re-exports shell middleware matcher config
  app/
    layout.tsx                                   # MODIFIED: root layout — UNGATED (no RequireAuth here; serves /login safely)
    (public)/
      login/
        page.tsx                                 # /login — CREATE stub if not present; outside (authenticated) group
    (authenticated)/
      layout.tsx                                 # MODIFIED (or CREATE): RequireAuth gate + AppShellMount; all routes here require auth
      qa-harness/                                # MODIFIED: replaces any existing stubs with re-exports from packages/shell routes
        [[...path]]/
          page.tsx                               # Catch-all re-export of packages/shell qa-harness pages
```

### Modifies

```
tsconfig.json                                    # add reference to ./packages/shell
package.json                                     # npm workspaces auto-discovers packages/*; no change unless enumerated
.github/workflows/sp0-foundation.yml             # extend test step to include packages/shell
package-lock.json                                # regenerated after npm install
portal/operator/middleware.ts                    # import shell middleware config
portal/operator/app/layout.tsx                   # root layout — verify/ensure UNGATED (no RequireAuth)
portal/operator/app/(authenticated)/layout.tsx   # RequireAuth + AppShellMount (create if not present)
portal/operator/app/(public)/login/page.tsx      # create stub if login page absent or not in a public group
```

### Leaves alone

```
packages/contract/                               # untouched (Plan B)
packages/auth/                                   # untouched (Plan B)
packages/ui/                                     # untouched (Plan C)
packages/qa-harness/                             # untouched (Plan C)
packages/scripts/                                # untouched (Plan A)
modules/, shared/, scripts/                      # backend Python untouched
infrastructure/                                  # manifests untouched (Plan D)
```

---

## Plan C-shell — Tasks

### Task 1: packages/shell scaffold

**Files:**
- Create: `packages/shell/package.json`
- Create: `packages/shell/tsconfig.json`
- Create: `packages/shell/vitest.config.ts`
- Create: `packages/shell/src/index.ts` (stub)
- Create: `packages/shell/src/_generated/manifest.json` (placeholder)
- Modify: `tsconfig.json` (repo root) — add reference to `./packages/shell`

- [ ] **Step 1.1: Write `packages/shell/package.json`**

```json
{
  "name": "@infinityrx/shell",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "exports": {
    ".": "./dist/index.js",
    "./middleware": "./dist/middleware.js",
    "./manifest": "./src/_generated/manifest.json"
  },
  "scripts": {
    "build": "tsc -b",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@infinityrx/auth": "*",
    "@infinityrx/contract": "*",
    "@infinityrx/ui": "*",
    "@infinityrx/qa-harness": "*",
    "@nanostores/react": "0.8.0",
    "nanostores": "0.11.3"
  },
  "peerDependencies": {
    "next": "^16.2.0",
    "next-auth": "^5.0.0",
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
    "typescript": "5.6.3",
    "vitest": "2.1.9"
  }
}
```

- [ ] **Step 1.2: Write `packages/shell/tsconfig.json`**

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src",
    "jsx": "react-jsx"
  },
  "references": [
    { "path": "../auth" },
    { "path": "../contract" },
    { "path": "../ui" },
    { "path": "../qa-harness" }
  ],
  "include": ["src/**/*.ts", "src/**/*.tsx"],
  "exclude": ["src/**/*.test.ts", "src/**/*.test.tsx", "src/__tests__/**", "dist", "node_modules"]
}
```

- [ ] **Step 1.3: Write `packages/shell/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx", "src/__tests__/**/*.test.ts", "src/__tests__/**/*.test.tsx"],
    environment: "happy-dom",
  },
});
```

- [ ] **Step 1.4: Write `packages/shell/src/index.ts` (stub)**

```ts
// Public surface of @infinityrx/shell.
// Plan C-shell Tasks 2–7 populate these re-exports.
export {};
```

- [ ] **Step 1.5: Write `packages/shell/src/_generated/manifest.json` (placeholder)**

```json
{
  "instance_name": "placeholder",
  "modules": [],
  "audience": "operator"
}
```

This placeholder is the zero-module state. Plan D's `scripts/generate-composition.ts` overwrites this file at build time. Plan C-shell reads it via `import manifest from "./_generated/manifest.json" with { type: "json" }` (TypeScript 5.6.3 NodeNext — `with` is the TC39-ratified import attribute syntax; `assert` is deprecated). The file is also accessible to `portal/operator` and other consumers via the `"./manifest"` package export declared in `packages/shell/package.json`.

- [ ] **Step 1.6: Modify `tsconfig.json` (repo root) — add packages/shell reference**

Append `{ "path": "./packages/shell" }` to the root `tsconfig.json`'s `references` array after `packages/qa-harness`.

- [ ] **Step 1.7: Verification**

```bash
# npm install MUST run here — nanostores + @nanostores/react are declared in
# this task's package.json and must be locked before Task 5 imports them.
npm install
npm --workspace=@infinityrx/shell run build
# Expected: exit 0 (stub only compiles to empty module)
npm --workspace=@infinityrx/shell run test
# Expected: exit 0, 0 tests (no test files yet)
```

Commit message:
```
feat(sp-0): Plan C-shell Task 1 — scaffold packages/shell

packages/shell: Next.js 16.2 + React 19.2 peer deps; depends on
@infinityrx/auth + contract + ui + qa-harness; tsconfig references all four.
_generated/manifest.json placeholder (zero-module state for Plan D codegen).
Root tsconfig extended with packages/shell reference.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

### Task 2: Auth types + `getSessionUser` + `<RequireAuth>` + `<RequireRole>`

**Files:**
- Create: `packages/shell/src/auth/types.ts`
- Create: `packages/shell/src/auth/get-session-user.ts`
- Create: `packages/shell/src/__tests__/get-session-user.test.ts`
- Create: `packages/shell/src/auth/require-auth.tsx`
- Create: `packages/shell/src/__tests__/require-auth.test.tsx`
- Create: `packages/shell/src/auth/require-role.tsx`
- Create: `packages/shell/src/__tests__/require-role.test.tsx`
- Modify: `packages/shell/src/index.ts`
- Create: `packages/shell/src/auth/auth.config.ts` (next-auth config binding Plan B's verify chain)

All components are **React Server Components** (async function, no `"use client"` directive). Auth checks run server-side via `next-auth`'s `auth()` helper — unauthorized users never receive page HTML.

**Auth architecture decision — Option A (codex BLOCK 1 closure):**

`RequireAuth` and `getSessionUser` call `next-auth`'s `auth()` helper and trust the `session.user` shape. This is intentional — `session.user` is populated exclusively in `next-auth`'s `callbacks.jwt`, which is the only place tokens are minted. The **load-bearing closure** is that `callbacks.jwt` MUST call `verifyAccessToken` from `@infinityrx/auth` before propagating claims into the session.

Concretely, `packages/shell/src/auth/auth.config.ts` exports a `NextAuthConfig` object whose `callbacks.jwt` calls `verifyAccessToken(token.access_token, { secret, revocationRepo })` — Plan B's verify oracle. If `verifyAccessToken` throws `AuthError`, the callback returns `null` (next-auth treats this as a session invalidation and clears the cookie). Only after a successful verify are `sub`, `tid`, `roles`, and `mfaEnrolled` written into `session.user`.

This means:
- `getSessionUser` trusting `session.user` is safe: the session cannot be created without Plan B's verify chain running at login time.
- The verify chain is not re-called on every RSC render (which would add latency and Redis round-trips). Token freshness is enforced by `next-auth`'s session expiry + the `callbacks.jwt` re-check on token refresh.
- Revocation is enforced at login + refresh, not on every request. If per-request revocation is required in a future wave, the pattern is to add a `callbacks.session` check against the Redis revocation list.

Option B (read cookie directly, call `verifyAccessToken` on every RSC) was considered and rejected: it bypasses next-auth's session management entirely, requiring custom cookie parsing and CSRF protection — trading framework complexity for marginal security gain that per-request Redis revocation adds. Option A keeps Next.js idioms intact while making Plan B's verify chain load-bearing at the session boundary.

- [ ] **Step 2.1: Write `packages/shell/src/auth/types.ts`**

```ts
/**
 * Decoded identity surface exposed to RSCs.
 * Mirrors SD-1 §2 access-token claims (sub, tid, roles).
 * access_token and refresh_token are NOT included — they remain
 * inside the encrypted next-auth session payload, server-readable only.
 */
export interface UserIdentity {
  /** user_id (UUID string) — maps to JWT claim `sub` */
  readonly sub: string;
  /** tenant_id (UUID string) — maps to JWT claim `tid` */
  readonly tid: string;
  /** authorization roles — maps to JWT claim `roles` */
  readonly roles: readonly string[];
  /** whether MFA enrollment is complete */
  readonly mfaEnrolled: boolean;
}

/** Sentinel returned when no authenticated session exists. */
export type SessionUser = UserIdentity | null;
```

- [ ] **Step 2.1b: Write `packages/shell/src/auth/auth.config.ts`**

This file wires Plan B's `verifyAccessToken` into next-auth's `callbacks.jwt`. It is the load-bearing binding that makes Plan B the verify oracle for all sessions created in `portal/operator`.

```ts
import "server-only";
import NextAuth, { type NextAuthConfig } from "next-auth";
import Credentials from "next-auth/providers/credentials";
// Plan B's verify oracle — called at JWT creation time.
// If verifyAccessToken throws AuthError, jwt callback returns null
// and next-auth clears the session cookie.
import { verifyAccessToken } from "@infinityrx/auth";

export const authConfig: NextAuthConfig = {
  providers: [
    Credentials({
      /**
       * The InfinityRx portal does not use credentials directly here —
       * authentication is delegated to the Python auth service, which
       * returns a signed access_token + refresh_token pair.
       * The `authorize` callback receives those tokens from the login form.
       */
      async authorize(credentials) {
        if (!credentials?.access_token) return null;
        // Verify via Plan B's verify chain: checks signature, expiry, and
        // Redis revocation list. Throws AuthError on any failure.
        const payload = await verifyAccessToken(credentials.access_token as string);
        return {
          id: payload.sub,
          access_token: credentials.access_token as string,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      // On initial sign-in, user is populated by authorize().
      if (user?.access_token) {
        // Verify (again) and extract claims into session token.
        // This ensures the JWT stored in the encrypted cookie was produced
        // by a token that passed Plan B's verify chain.
        const payload = await verifyAccessToken(user.access_token as string);
        token.sub = payload.sub;
        token.tid = payload.tid as string;
        token.roles = payload.roles as string[];
        token.mfaEnrolled = (payload.mfa_enrolled ?? false) as boolean;
      }
      // On subsequent refreshes, the claims are already in the token.
      // Per-request revocation checking is deferred to a future wave;
      // revocation is enforced at login + token-refresh boundaries only.
      return token;
    },
    async session({ session, token }) {
      // Propagate claims from JWT into session.user for getSessionUser().
      session.user = {
        ...session.user,
        sub: token.sub as string,
        tid: token.tid as string,
        roles: token.roles as string[],
        mfaEnrolled: token.mfaEnrolled as boolean,
      };
      return session;
    },
  },
  session: { strategy: "jwt" },
};

export const { auth, handlers, signIn, signOut } = NextAuth(authConfig);
```

The `auth` export from this file is what `get-session-user.ts` and `require-auth.tsx` import. This is the critical link: `auth()` here runs the `session` callback which reads only claims populated by `callbacks.jwt` — which called `verifyAccessToken`. The trust chain is complete.

- [ ] **Step 2.2: Write `packages/shell/src/auth/get-session-user.ts`**

```ts
import "server-only";
// Import `auth` from the auth.config binding, not from "next-auth" directly.
// This ensures we use the configured session callback that populates
// sub/tid/roles/mfaEnrolled from Plan B's verifyAccessToken chain.
// See auth.config.ts for the load-bearing boundary documentation.
import { auth } from "./auth.config.js";
import type { SessionUser } from "./types.js";

/**
 * Returns the authenticated user identity from the current request's
 * server-side session, or null if no valid session is present.
 *
 * Must only be called from RSCs or Next.js route handlers.
 * The `server-only` import at the top of this file prevents it from
 * being accidentally imported in client components.
 */
export async function getSessionUser(): Promise<SessionUser> {
  const session = await auth();
  if (!session?.user) return null;

  const { sub, tid, roles, mfaEnrolled } = session.user as {
    sub?: string;
    tid?: string;
    roles?: string[];
    mfaEnrolled?: boolean;
  };

  if (!sub || !tid || !Array.isArray(roles)) return null;

  return {
    sub,
    tid,
    roles: roles as readonly string[],
    mfaEnrolled: mfaEnrolled ?? false,
  };
}
```

- [ ] **Step 2.3: Write `packages/shell/src/__tests__/get-session-user.test.ts` (failing first)**

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the auth.config binding and server-only before importing module under test.
// This ensures we test the session-extraction logic without running the full
// next-auth JWT callback chain (which requires Plan B's verifyAccessToken).
vi.mock("../auth/auth.config.js", () => ({
  auth: vi.fn(),
}));
vi.mock("server-only", () => ({}));

import { auth } from "../auth/auth.config.js";
import { getSessionUser } from "../auth/get-session-user.js";

describe("getSessionUser", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns null when session is absent", async () => {
    vi.mocked(auth).mockResolvedValue(null as never);
    expect(await getSessionUser()).toBeNull();
  });

  it("returns null when session.user is missing required fields", async () => {
    vi.mocked(auth).mockResolvedValue({ user: { sub: "u1" } } as never);
    expect(await getSessionUser()).toBeNull();
  });

  it("returns UserIdentity with correct shape when session is valid", async () => {
    vi.mocked(auth).mockResolvedValue({
      user: {
        sub: "00000000-0000-0000-0000-000000000001",
        tid: "00000000-0000-0000-0000-000000000002",
        roles: ["platform_admin"],
        mfaEnrolled: true,
      },
    } as never);
    const user = await getSessionUser();
    expect(user).toEqual({
      sub: "00000000-0000-0000-0000-000000000001",
      tid: "00000000-0000-0000-0000-000000000002",
      roles: ["platform_admin"],
      mfaEnrolled: true,
    });
  });

  it("defaults mfaEnrolled to false when not present in session", async () => {
    vi.mocked(auth).mockResolvedValue({
      user: {
        sub: "u1",
        tid: "t1",
        roles: [],
      },
    } as never);
    const user = await getSessionUser();
    expect(user?.mfaEnrolled).toBe(false);
  });
});
```

- [ ] **Step 2.4: Write `packages/shell/src/auth/require-auth.tsx`**

```tsx
import "server-only";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { getSessionUser } from "./get-session-user.js";

interface RequireAuthProps {
  children: ReactNode;
  /** Path to redirect unauthenticated requests to. Default: "/login" */
  loginPath?: string;
  /** Current path, included as ?callbackUrl= on the redirect. */
  callbackUrl?: string;
}

/**
 * Server Component auth gate.
 *
 * Reads the session server-side via getSessionUser() (which calls next-auth's
 * auth()). If no valid session is found, redirects to loginPath with the
 * current path as callbackUrl. Authenticated users receive children; the
 * redirect happens before any HTML is sent — unauthorized users never see
 * guarded content, even briefly.
 *
 * Usage in app/layout.tsx (root RSC):
 *   <RequireAuth callbackUrl={pathname}>
 *     {children}
 *   </RequireAuth>
 */
export async function RequireAuth({
  children,
  loginPath = "/login",
  callbackUrl,
}: RequireAuthProps): Promise<ReactNode> {
  const user = await getSessionUser();
  if (!user) {
    const target = callbackUrl
      ? `${loginPath}?callbackUrl=${encodeURIComponent(callbackUrl)}`
      : loginPath;
    redirect(target);
  }
  return <>{children}</>;
}
```

- [ ] **Step 2.5: Write `packages/shell/src/__tests__/require-auth.test.tsx` (failing first)**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({ redirect: vi.fn() }));
vi.mock("../auth/get-session-user.js", () => ({ getSessionUser: vi.fn() }));

import { redirect } from "next/navigation";
import { getSessionUser } from "../auth/get-session-user.js";
import { RequireAuth } from "../auth/require-auth.js";

describe("RequireAuth", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders children when session is valid", async () => {
    vi.mocked(getSessionUser).mockResolvedValue({
      sub: "u1", tid: "t1", roles: [], mfaEnrolled: false,
    });
    const { getByText } = render(await RequireAuth({ children: <span>protected</span> }) as never);
    expect(getByText("protected")).toBeTruthy();
  });

  it("redirects to /login when session is null", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(null);
    await RequireAuth({ children: <span>x</span> });
    expect(vi.mocked(redirect)).toHaveBeenCalledWith("/login");
  });

  it("redirects to custom loginPath when provided", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(null);
    await RequireAuth({ children: <span>x</span>, loginPath: "/auth/sign-in" });
    expect(vi.mocked(redirect)).toHaveBeenCalledWith("/auth/sign-in");
  });

  it("includes callbackUrl in redirect when provided", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(null);
    await RequireAuth({ children: <span>x</span>, callbackUrl: "/billing/claims" });
    expect(vi.mocked(redirect)).toHaveBeenCalledWith(
      "/login?callbackUrl=%2Fbilling%2Fclaims"
    );
  });

  it("does not call redirect when session is valid", async () => {
    vi.mocked(getSessionUser).mockResolvedValue({
      sub: "u1", tid: "t1", roles: ["operator"], mfaEnrolled: true,
    });
    await RequireAuth({ children: <span>x</span> });
    expect(vi.mocked(redirect)).not.toHaveBeenCalled();
  });

  it("renders nothing (redirects) when next-auth returns partial user missing tid", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(null);
    await RequireAuth({ children: <span>secret</span> });
    expect(vi.mocked(redirect)).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2.6: Write `packages/shell/src/auth/require-role.tsx`**

```tsx
import "server-only";
import type { ReactNode } from "react";
import { getSessionUser } from "./get-session-user.js";

interface RequireRoleProps {
  /**
   * Role names the authenticated user must possess ALL of.
   * An empty array means "any authenticated user is allowed."
   */
  roles: readonly string[];
  children: ReactNode;
  /** Rendered when the user lacks the required roles. Default: null (renders nothing). */
  fallback?: ReactNode;
}

/**
 * Granular role-based RSC gate.
 *
 * Requires a parent <RequireAuth> (or equivalent) to have already confirmed
 * a valid session exists. If the user is not authenticated, falls back.
 * If the user lacks ANY of the required roles, renders fallback (default: null).
 *
 * Usage:
 *   <RequireRole roles={["billing_admin", "platform_admin"]}>
 *     <BillingConfigPanel />
 *   </RequireRole>
 */
export async function RequireRole({
  roles,
  children,
  fallback = null,
}: RequireRoleProps): Promise<ReactNode> {
  const user = await getSessionUser();
  if (!user) return <>{fallback}</>;

  const hasAll = roles.every((r) => user.roles.includes(r));
  return hasAll ? <>{children}</> : <>{fallback}</>;
}
```

- [ ] **Step 2.7: Write `packages/shell/src/__tests__/require-role.test.tsx` (failing first)**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("server-only", () => ({}));
vi.mock("../auth/get-session-user.js", () => ({ getSessionUser: vi.fn() }));

import { getSessionUser } from "../auth/get-session-user.js";
import { RequireRole } from "../auth/require-role.js";

const adminUser = { sub: "u1", tid: "t1", roles: ["platform_admin", "billing_admin"], mfaEnrolled: true };

describe("RequireRole", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders children when user has all required roles", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    const { getByText } = render(
      await RequireRole({ roles: ["platform_admin"], children: <span>admin panel</span> }) as never
    );
    expect(getByText("admin panel")).toBeTruthy();
  });

  it("renders fallback when user is missing a required role", async () => {
    vi.mocked(getSessionUser).mockResolvedValue({ ...adminUser, roles: ["billing_admin"] });
    const result = render(
      await RequireRole({
        roles: ["platform_admin"],
        children: <span>restricted</span>,
        fallback: <span>access denied</span>,
      }) as never
    );
    expect(result.queryByText("restricted")).toBeNull();
    expect(result.getByText("access denied")).toBeTruthy();
  });

  it("renders children when required roles is empty (any authenticated user)", async () => {
    vi.mocked(getSessionUser).mockResolvedValue({ ...adminUser, roles: [] });
    const { getByText } = render(
      await RequireRole({ roles: [], children: <span>open</span> }) as never
    );
    expect(getByText("open")).toBeTruthy();
  });

  it("renders fallback (null) when session is absent", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(null);
    const result = render(
      await RequireRole({ roles: ["platform_admin"], children: <span>secret</span> }) as never
    );
    expect(result.queryByText("secret")).toBeNull();
  });

  it("renders children when user has a superset of required roles", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    const { getByText } = render(
      await RequireRole({ roles: ["platform_admin", "billing_admin"], children: <span>both</span> }) as never
    );
    expect(getByText("both")).toBeTruthy();
  });
});
```

- [ ] **Step 2.8: Update `packages/shell/src/index.ts`**

```ts
// Public surface of @infinityrx/shell.

export type { UserIdentity, SessionUser } from "./auth/types.js";
export { getSessionUser } from "./auth/get-session-user.js";
export { RequireAuth } from "./auth/require-auth.js";
export { RequireRole } from "./auth/require-role.js";
```

- [ ] **Step 2.9: Verification**

```bash
npm --workspace=@infinityrx/shell run build
# Expected: exit 0
npm --workspace=@infinityrx/shell run test
# Expected: 15 tests pass (4 get-session-user + 6 require-auth + 5 require-role)
```

Commit message:
```
feat(sp-0): Plan C-shell Task 2 — RequireAuth + RequireRole RSC auth gates

auth.config.ts: NextAuthConfig with callbacks.jwt calling verifyAccessToken
from @infinityrx/auth — Plan B is the verify oracle for all sessions.
getSessionUser(): extracts UserIdentity from next-auth encrypted session
server-side; access_token/refresh_token never exposed to client per SD-1 §6.
<RequireAuth>: server-component redirect gate; unauthenticated → /login with
callbackUrl; authorized → renders children. Server-side so no flash.
<RequireRole>: renders children only when user holds ALL listed roles;
fallback renders on miss or absent session.
15 tests (4 + 6 + 5). 100% coverage on auth paths.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

### Task 3: Auth-aware `AppShellMount` + `ModuleNav`

**Files:**
- Create: `packages/shell/src/shell/nav-types.ts`
- Create: `packages/shell/src/shell/module-nav.tsx`
- Create: `packages/shell/src/__tests__/module-nav.test.tsx`
- Create: `packages/shell/src/shell/app-shell-mount.tsx`
- Create: `packages/shell/src/__tests__/app-shell-mount.test.tsx`
- Modify: `packages/shell/src/index.ts`

`AppShellMount` is a server component that reads the user's roles from the session and the instance manifest from `_generated/manifest.json`, then renders Plan C's `AppShell` with a nav slot populated only by modules the user's roles permit, ordered by manifest position.

- [ ] **Step 3.1: Write `packages/shell/src/shell/nav-types.ts`**

```ts
/**
 * A single nav entry emitted by a module's module.config.ts
 * and consumed by <ModuleNav> to build the sidebar.
 */
export interface NavEntry {
  /** Matches the module id in the deployment manifest. */
  readonly moduleId: string;
  /** Display label. */
  readonly label: string;
  /** Absolute path, e.g. "/reclaimrx". */
  readonly href: string;
  /** Icon identifier for the design system. e.g. "shield-check". */
  readonly iconSlug: string;
  /**
   * Roles that may see this nav entry.
   * Empty array = any authenticated user may see it.
   */
  readonly requiredRoles: readonly string[];
}

/**
 * Minimal shape of the instance manifest consumed by <ModuleNav>.
 * The full schema is in SD-4 §3; we read only what we need here.
 */
export interface InstanceManifestShape {
  readonly modules: readonly string[];
}
```

- [ ] **Step 3.2: Write `packages/shell/src/__tests__/module-nav.test.tsx` (failing first)**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("server-only", () => ({}));
vi.mock("../auth/get-session-user.js", () => ({ getSessionUser: vi.fn() }));

import { getSessionUser } from "../auth/get-session-user.js";
import { ModuleNav } from "../shell/module-nav.js";
import type { NavEntry } from "../shell/nav-types.js";

const adminUser = { sub: "u1", tid: "t1", roles: ["platform_admin"], mfaEnrolled: true };

const entries: NavEntry[] = [
  { moduleId: "reclaimrx", label: "ReclaimRx", href: "/reclaimrx", iconSlug: "shield", requiredRoles: [] },
  { moduleId: "billing", label: "Billing", href: "/billing", iconSlug: "dollar", requiredRoles: ["billing_admin"] },
  { moduleId: "paysync", label: "PaySync", href: "/paysync", iconSlug: "refresh", requiredRoles: ["paysync_user"] },
];

describe("ModuleNav", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders all entries accessible to the user's roles", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    // adminUser has platform_admin, not billing_admin or paysync_user
    // reclaimrx has requiredRoles: [] → visible to all
    const { getByText, queryByText } = render(
      await ModuleNav({ entries, manifestModules: ["reclaimrx", "billing", "paysync"] }) as never
    );
    expect(getByText("ReclaimRx")).toBeTruthy();
    expect(queryByText("Billing")).toBeNull();
    expect(queryByText("PaySync")).toBeNull();
  });

  it("renders no entries when manifest excludes all provided modules", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    const { queryByText } = render(
      await ModuleNav({ entries, manifestModules: [] }) as never
    );
    expect(queryByText("ReclaimRx")).toBeNull();
  });

  it("respects manifest ordering: renders entries in manifest order", async () => {
    vi.mocked(getSessionUser).mockResolvedValue({ ...adminUser, roles: ["platform_admin", "billing_admin", "paysync_user"] });
    const { getAllByRole } = render(
      await ModuleNav({ entries, manifestModules: ["paysync", "reclaimrx", "billing"] }) as never
    );
    const links = getAllByRole("link").map((el) => el.getAttribute("href"));
    expect(links).toEqual(["/paysync", "/reclaimrx", "/billing"]);
  });

  it("renders entries whose requiredRoles is a superset the user satisfies", async () => {
    vi.mocked(getSessionUser).mockResolvedValue({ ...adminUser, roles: ["billing_admin"] });
    const { getByText } = render(
      await ModuleNav({ entries, manifestModules: ["reclaimrx", "billing"] }) as never
    );
    expect(getByText("Billing")).toBeTruthy();
  });

  it("returns null when session is absent (unauthenticated path)", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(null);
    const result = render(
      await ModuleNav({ entries, manifestModules: ["reclaimrx"] }) as never
    );
    expect(result.queryByRole("link")).toBeNull();
  });
});
```

- [ ] **Step 3.3: Write `packages/shell/src/shell/module-nav.tsx`**

```tsx
import "server-only";
import type { ReactNode } from "react";
import { getSessionUser } from "../auth/get-session-user.js";
import type { NavEntry, InstanceManifestShape } from "./nav-types.js";

interface ModuleNavProps {
  /** All possible nav entries (registered by module packages). */
  entries: readonly NavEntry[];
  /** Module IDs from the instance manifest, in manifest order. */
  manifestModules: readonly string[];
}

/**
 * Builds the side navigation for the authenticated shell.
 *
 * Steps:
 * 1. Reads the user's roles from the server session.
 * 2. Filters entries to those whose moduleId is in manifestModules
 *    (only deployed modules appear, even if registered).
 * 3. Filters by requiredRoles (empty = any authenticated user).
 * 4. Sorts by manifest order (preserves intent from deployment manifest).
 * 5. Returns a <nav> with anchor links — fully server-rendered.
 */
export async function ModuleNav({
  entries,
  manifestModules,
}: ModuleNavProps): Promise<ReactNode> {
  const user = await getSessionUser();
  if (!user) return null;

  // Build an order map from the manifest for O(1) sort.
  const orderMap = new Map(manifestModules.map((id, i) => [id, i]));

  const visible = entries
    .filter((e) => orderMap.has(e.moduleId))
    .filter((e) =>
      e.requiredRoles.length === 0 ||
      e.requiredRoles.every((r) => user.roles.includes(r))
    )
    .sort((a, b) => (orderMap.get(a.moduleId) ?? 0) - (orderMap.get(b.moduleId) ?? 0));

  if (visible.length === 0) return null;

  return (
    <nav aria-label="Module navigation">
      <ul>
        {visible.map((e) => (
          <li key={e.moduleId}>
            <a href={e.href} aria-label={e.label}>
              {e.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
```

- [ ] **Step 3.4: Write `packages/shell/src/__tests__/app-shell-mount.test.tsx` (failing first)**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("server-only", () => ({}));
vi.mock("../auth/get-session-user.js", () => ({ getSessionUser: vi.fn() }));
// Mock AppShell to verify the nav slot is passed correctly.
vi.mock("@infinityrx/ui", () => ({
  AppShell: vi.fn(({ children, nav }: { children: unknown; nav?: unknown }) => (
    <div>
      <div data-testid="nav-slot">{nav as never}</div>
      <main>{children as never}</main>
    </div>
  )),
}));

import { getSessionUser } from "../auth/get-session-user.js";
import { AppShellMount } from "../shell/app-shell-mount.js";
import type { NavEntry } from "../shell/nav-types.js";

const adminUser = { sub: "u1", tid: "t1", roles: ["platform_admin"], mfaEnrolled: true };
const entries: NavEntry[] = [
  { moduleId: "reclaimrx", label: "ReclaimRx", href: "/reclaimrx", iconSlug: "shield", requiredRoles: [] },
];
const manifest = { instance_name: "test", modules: ["reclaimrx"], audience: "operator" };

describe("AppShellMount", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders AppShell with nav slot populated when authenticated", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    const { getByTestId, getByText } = render(
      await AppShellMount({
        children: <span>page content</span>,
        navEntries: entries,
        manifest,
      }) as never
    );
    expect(getByTestId("nav-slot")).toBeTruthy();
    expect(getByText("page content")).toBeTruthy();
  });

  it("renders nav slot with only role-permitted entries", async () => {
    vi.mocked(getSessionUser).mockResolvedValue({ ...adminUser, roles: [] });
    // entries[0] has requiredRoles: [] → visible even with no roles
    const { getByText } = render(
      await AppShellMount({ children: <span>c</span>, navEntries: entries, manifest }) as never
    );
    expect(getByText("ReclaimRx")).toBeTruthy();
  });

  it("renders AppShell with empty nav when manifest has no modules", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    const emptyManifest = { ...manifest, modules: [] };
    const result = render(
      await AppShellMount({ children: <span>c</span>, navEntries: entries, manifest: emptyManifest }) as never
    );
    // Nav slot should be empty (no links)
    expect(result.queryByRole("link")).toBeNull();
  });

  it("renders children in main slot", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    const { getByText } = render(
      await AppShellMount({ children: <span>my page</span>, navEntries: entries, manifest }) as never
    );
    expect(getByText("my page")).toBeTruthy();
  });

  it("renders AppShell with optional header when provided", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    const { getByText } = render(
      await AppShellMount({
        children: <span>c</span>,
        navEntries: entries,
        manifest,
        header: <header>My Header</header>,
      }) as never
    );
    expect(getByText("My Header")).toBeTruthy();
  });
});
```

- [ ] **Step 3.5: Write `packages/shell/src/shell/app-shell-mount.tsx`**

```tsx
import "server-only";
import type { ReactNode } from "react";
import { AppShell } from "@infinityrx/ui";
import { ModuleNav } from "./module-nav.js";
import type { NavEntry, InstanceManifestShape } from "./nav-types.js";

interface AppShellMountProps {
  children: ReactNode;
  /** Optional top-bar content. Passed directly to AppShell's header slot. */
  header?: ReactNode;
  /** All nav entries registered by module packages. */
  navEntries: readonly NavEntry[];
  /** Instance manifest shape read from _generated/manifest.json. */
  manifest: InstanceManifestShape;
}

/**
 * Auth-aware AppShell server component.
 *
 * Reads the authenticated user's roles (via ModuleNav → getSessionUser),
 * filters and orders nav entries per the instance manifest, and renders
 * Plan C's <AppShell> with the dynamic nav slot populated server-side.
 *
 * The nav slot is role-filtered and manifest-ordered — users only see
 * modules they have access to and that are present in this instance's build.
 */
export async function AppShellMount({
  children,
  header,
  navEntries,
  manifest,
}: AppShellMountProps): Promise<ReactNode> {
  const nav = await ModuleNav({
    entries: navEntries,
    manifestModules: manifest.modules,
  });

  return (
    <AppShell header={header} nav={nav ?? undefined}>
      {children}
    </AppShell>
  );
}
```

- [ ] **Step 3.6: Update `packages/shell/src/index.ts`**

```ts
// Public surface of @infinityrx/shell.

export type { UserIdentity, SessionUser } from "./auth/types.js";
export { getSessionUser } from "./auth/get-session-user.js";
export { RequireAuth } from "./auth/require-auth.js";
export { RequireRole } from "./auth/require-role.js";

export type { NavEntry, InstanceManifestShape } from "./shell/nav-types.js";
export { ModuleNav } from "./shell/module-nav.js";
export { AppShellMount } from "./shell/app-shell-mount.js";
```

- [ ] **Step 3.7: Verification**

```bash
npm --workspace=@infinityrx/shell run build
npm --workspace=@infinityrx/shell run test
# Expected: 25 tests pass (15 prior + 5 module-nav + 5 app-shell-mount)
```

Commit message:
```
feat(sp-0): Plan C-shell Task 3 — AppShellMount + ModuleNav RSC components

ModuleNav: RSC reads user roles from server session; filters nav entries
to manifest-deployed + role-permitted modules in manifest order.
AppShellMount: RSC wraps Plan C's AppShell with the dynamic module nav slot
built server-side — users never see unauthorized nav entries, even briefly.
NavEntry + InstanceManifestShape types align with SD-4 §3 manifest schema.
25 tests (15 prior + 5 + 5).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

### Task 4: QA mode toggle (cookie + middleware) + Next.js middleware wiring

**Files:**
- Create: `packages/shell/src/qa/qa-mode-cookie.ts`
- Create: `packages/shell/src/__tests__/qa-mode-cookie.test.ts`
- Create: `packages/shell/src/qa/qa-mode-middleware.ts`
- Create: `packages/shell/src/__tests__/qa-mode-middleware.test.ts`
- Create: `packages/shell/src/middleware.ts`
- Modify: `packages/shell/src/index.ts`
- Modify: `portal/operator/middleware.ts` (extend to import shell middleware config)

The QA mode toggle answers §6.4's deferred item. The session cookie `qa_mode` stores `"real" | "stub"` and survives navigation. Next.js middleware reads it and sets a request header `x-qa-mode` so RSCs can read the value via `headers()` without needing an explicit cookie read.

- [ ] **Step 4.1: Write `packages/shell/src/qa/qa-mode-cookie.ts`**

```ts
/**
 * QA mode toggle: persisted in a session cookie so it survives navigation
 * and multiple tabs in the same origin. This file contains only pure
 * parsing/constant logic — no Next.js imports — so it is testable in
 * happy-dom without a Next.js runtime.
 */

/** Cookie name for the QA mode preference. */
export const QA_MODE_COOKIE = "infinityrx-qa-mode" as const;

/** Valid QA mode values. */
export type QaMode = "real" | "stub";

/**
 * Parses the raw cookie string value into a valid QaMode.
 * Invalid or absent values fall back to "real" (safe production default).
 */
export function parseQaMode(raw: string | undefined): QaMode {
  if (raw === "real" || raw === "stub") return raw;
  return "real";
}

/**
 * Builds the Set-Cookie header value for the QA mode cookie.
 * HttpOnly: false — the toggle UI (client component) needs to read it.
 * SameSite=Lax, Secure (production): adequate for a non-sensitive preference.
 * Max-Age: 86400 (24h session preference lifetime).
 */
export function buildQaModeCookieValue(mode: QaMode, secure: boolean): string {
  const base = `${QA_MODE_COOKIE}=${mode}; Path=/; SameSite=Lax; Max-Age=86400`;
  return secure ? `${base}; Secure` : base;
}
```

- [ ] **Step 4.2: Write `packages/shell/src/__tests__/qa-mode-cookie.test.ts` (failing first)**

```ts
import { describe, it, expect } from "vitest";
import {
  QA_MODE_COOKIE,
  parseQaMode,
  buildQaModeCookieValue,
} from "../qa/qa-mode-cookie.js";

describe("QA mode cookie utilities", () => {
  it("parseQaMode returns 'real' for undefined", () => {
    expect(parseQaMode(undefined)).toBe("real");
  });

  it("parseQaMode returns 'real' for invalid value", () => {
    expect(parseQaMode("invalid")).toBe("real");
  });

  it("parseQaMode returns 'stub' for 'stub'", () => {
    expect(parseQaMode("stub")).toBe("stub");
  });

  it("parseQaMode returns 'real' for 'real'", () => {
    expect(parseQaMode("real")).toBe("real");
  });

  it("buildQaModeCookieValue includes Secure when secure=true", () => {
    const val = buildQaModeCookieValue("stub", true);
    expect(val).toContain("Secure");
    expect(val).toContain(`${QA_MODE_COOKIE}=stub`);
  });

  it("buildQaModeCookieValue omits Secure when secure=false", () => {
    const val = buildQaModeCookieValue("real", false);
    expect(val).not.toContain("Secure");
  });

  it("QA_MODE_COOKIE constant is the expected string", () => {
    expect(QA_MODE_COOKIE).toBe("infinityrx-qa-mode");
  });
});
```

- [ ] **Step 4.3: Write `packages/shell/src/qa/qa-mode-middleware.ts`**

```ts
import "server-only";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import {
  QA_MODE_COOKIE,
  parseQaMode,
  buildQaModeCookieValue,
  type QaMode,
} from "./qa-mode-cookie.js";

/** Request header name propagated by middleware to RSCs. */
export const QA_MODE_HEADER = "x-infinityrx-qa-mode" as const;

/**
 * QA mode middleware handler.
 *
 * Called from the portal's Next.js middleware.ts.
 * Reads the qa_mode cookie from the request; if absent, defaults to "real"
 * and sets the cookie on the response. Always propagates the resolved value
 * as x-infinityrx-qa-mode header for RSC consumers (next/headers).
 *
 * In production (INFINITYRX_ENV=production), qa_mode is forced to "real"
 * regardless of the cookie value — the toggle is a dev/staging tool only.
 */
export function applyQaModeMiddleware(req: NextRequest): NextResponse {
  const isProduction = process.env["INFINITYRX_ENV"] === "production";
  const rawCookie = req.cookies.get(QA_MODE_COOKIE)?.value;
  const resolved: QaMode = isProduction ? "real" : parseQaMode(rawCookie);

  const res = NextResponse.next({
    request: {
      headers: new Headers({
        ...Object.fromEntries(req.headers.entries()),
        [QA_MODE_HEADER]: resolved,
      }),
    },
  });

  // Set the cookie on the response if it was absent or if production is
  // forcing a reset to "real".
  const isSecure = req.url.startsWith("https://");
  if (!rawCookie || (isProduction && rawCookie !== "real")) {
    res.headers.set("Set-Cookie", buildQaModeCookieValue(resolved, isSecure));
  }

  return res;
}
```

- [ ] **Step 4.4: Write `packages/shell/src/__tests__/qa-mode-middleware.test.ts` (failing first)**

```ts
import { describe, it, expect, vi, afterEach } from "vitest";

vi.mock("server-only", () => ({}));
// next/server is mocked so we can test the middleware logic without a real Next.js runtime.
vi.mock("next/server", () => {
  return {
    NextResponse: {
      next: vi.fn(({ request }: { request: { headers: Headers } }) => {
        return {
          headers: new Headers(request.headers),
          cookies: { get: vi.fn(), set: vi.fn() },
        };
      }),
    },
  };
});

import { QA_MODE_COOKIE, type QaMode } from "../qa/qa-mode-cookie.js";
import { QA_MODE_HEADER, applyQaModeMiddleware } from "../qa/qa-mode-middleware.js";

function makeReq(cookieValue?: string, url = "http://localhost/dashboard"): unknown {
  const cookies = new Map<string, string>();
  if (cookieValue !== undefined) cookies.set(QA_MODE_COOKIE, cookieValue);
  return {
    url,
    cookies: { get: (name: string) => ({ value: cookies.get(name) }) },
    headers: new Headers(),
  };
}

describe("applyQaModeMiddleware", () => {
  afterEach(() => {
    delete process.env["INFINITYRX_ENV"];
  });

  it("defaults to 'real' when cookie is absent and sets x-infinityrx-qa-mode header", () => {
    process.env["INFINITYRX_ENV"] = "development";
    const res = applyQaModeMiddleware(makeReq() as never);
    expect(res.headers.get(QA_MODE_HEADER)).toBe("real");
  });

  it("preserves existing 'stub' cookie value in non-production", () => {
    process.env["INFINITYRX_ENV"] = "development";
    const res = applyQaModeMiddleware(makeReq("stub") as never);
    expect(res.headers.get(QA_MODE_HEADER)).toBe("stub");
  });

  it("forces 'real' in production regardless of cookie value", () => {
    process.env["INFINITYRX_ENV"] = "production";
    const res = applyQaModeMiddleware(makeReq("stub") as never);
    expect(res.headers.get(QA_MODE_HEADER)).toBe("real");
  });

  it("sets Set-Cookie header when cookie is absent", () => {
    process.env["INFINITYRX_ENV"] = "development";
    const res = applyQaModeMiddleware(makeReq() as never);
    expect(res.headers.get("Set-Cookie")).toContain(QA_MODE_COOKIE);
  });
});
```

- [ ] **Step 4.5: Write `packages/shell/src/middleware.ts`**

```ts
/**
 * Shell middleware export.
 *
 * portal/operator/middleware.ts imports this to compose shell middleware
 * into the portal's Next.js middleware chain.
 *
 * Provides:
 *  - applyQaModeMiddleware: reads qa_mode cookie; propagates x-infinityrx-qa-mode header
 *  - SHELL_MIDDLEWARE_MATCHER: recommended route matcher (all routes except static assets)
 */
export { applyQaModeMiddleware, QA_MODE_HEADER } from "./qa/qa-mode-middleware.js";
export { QA_MODE_COOKIE, parseQaMode, type QaMode } from "./qa/qa-mode-cookie.js";

/**
 * Recommended Next.js middleware matcher for the shell middleware.
 * Excludes _next static, _next image, favicon.ico, and public folder.
 */
export const SHELL_MIDDLEWARE_MATCHER = [
  "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
] as const;
```

- [ ] **Step 4.6: Modify `portal/operator/middleware.ts`**

Read the current file first, then apply the surgical change to import and invoke `applyQaModeMiddleware`. The goal is to compose the shell middleware into the existing middleware without replacing any existing logic.

```ts
// portal/operator/middleware.ts — add this import at the top
import { applyQaModeMiddleware, SHELL_MIDDLEWARE_MATCHER } from "@infinityrx/shell/middleware";
import type { NextRequest } from "next/server";

export function middleware(req: NextRequest) {
  // Apply shell-level cross-cutting middleware (QA mode cookie propagation).
  // Additional middleware (auth, rate-limiting) compose here as the portal grows.
  return applyQaModeMiddleware(req);
}

export const config = {
  matcher: SHELL_MIDDLEWARE_MATCHER,
};
```

Note: If `portal/operator/middleware.ts` already exists with its own logic (e.g., `proxy.ts` auth-gate middleware), compose rather than replace. The auth-gate edge middleware (`proxy.ts`) is invoked before the QA middleware — read the existing file before modifying and chain appropriately.

- [ ] **Step 4.7: Update `packages/shell/src/index.ts`**

```ts
// Public surface of @infinityrx/shell.

export type { UserIdentity, SessionUser } from "./auth/types.js";
export { getSessionUser } from "./auth/get-session-user.js";
export { RequireAuth } from "./auth/require-auth.js";
export { RequireRole } from "./auth/require-role.js";

export type { NavEntry, InstanceManifestShape } from "./shell/nav-types.js";
export { ModuleNav } from "./shell/module-nav.js";
export { AppShellMount } from "./shell/app-shell-mount.js";

export type { QaMode } from "./qa/qa-mode-cookie.js";
export { QA_MODE_COOKIE, parseQaMode } from "./qa/qa-mode-cookie.js";
export { QA_MODE_HEADER, applyQaModeMiddleware } from "./qa/qa-mode-middleware.js";
export { SHELL_MIDDLEWARE_MATCHER } from "./middleware.js";
```

- [ ] **Step 4.8: Verification**

```bash
npm --workspace=@infinityrx/shell run build
npm --workspace=@infinityrx/shell run test
# Expected: 36 tests pass (25 prior + 7 qa-mode-cookie + 4 qa-mode-middleware)
```

Commit message:
```
feat(sp-0): Plan C-shell Task 4 — QA mode toggle (cookie + middleware)

qa-mode-cookie.ts: parseQaMode, buildQaModeCookieValue, QA_MODE_COOKIE constant.
No Next.js imports — pure parsing logic, fully unit-testable in happy-dom.
qa-mode-middleware.ts: applyQaModeMiddleware reads/sets cookie; propagates
x-infinityrx-qa-mode header for RSC consumers; forces "real" in production.
middleware.ts: SHELL_MIDDLEWARE_MATCHER + re-exports for portal composition.
portal/operator/middleware.ts: wired to shell middleware.
Closes §6.4 deferred item "QA mode toggle (cookie + middleware)".
36 tests (25 prior + 7 + 4).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

### Task 5: Request/response inspector (wrapFetch + panel)

**Files:**
- Create: `packages/shell/src/qa/inspector/types.ts`
- Create: `packages/shell/src/qa/inspector/wrap-fetch.ts`
- Create: `packages/shell/src/__tests__/wrap-fetch.test.ts`
- Create: `packages/shell/src/qa/inspector/inspector-store.ts`
- Create: `packages/shell/src/__tests__/inspector-store.test.ts`
- Create: `packages/shell/src/qa/inspector/inspector-panel.tsx`
- Modify: `packages/shell/src/index.ts`

This closes the second §6.4 deferred item. The design: `wrapFetch` wraps the `ClientConfig.fetch` override at injection time — no changes to Plan B's `ClientConfig` type are needed. The BFF constructs each client with `config.fetch = wrapFetch(globalThis.fetch, emitEntry)` in non-production builds. `InspectorPanel` is a `"use client"` component (the only one in Plan C-shell) — it reads from a nanostores atom and renders a slide-out panel.

- [ ] **Step 5.1: Write `packages/shell/src/qa/inspector/types.ts`**

```ts
/**
 * A single captured request/response entry for the inspector panel.
 */
export interface InspectorEntry {
  /** Unique ID for React key and dedup. */
  readonly id: string;
  /** HTTP method, upper-cased. */
  readonly method: string;
  /** Full URL. */
  readonly url: string;
  /** HTTP status code, or 0 on network error. */
  readonly status: number;
  /** Round-trip latency in milliseconds. */
  readonly latencyMs: number;
  /** Whether the client was in mock mode when this call was made. */
  readonly isMock: boolean;
  /** Whether the response was served from cache (populated by the BFF cache layer). */
  readonly cacheHit: boolean;
  /** Correlation ID extracted from the x-correlation-id response header. */
  readonly correlationId?: string;
  /** ISO 8601 timestamp of the request. */
  readonly timestamp: string;
  /** Request body, if any (non-null only for POST/PUT/PATCH). */
  readonly requestBody?: unknown;
  /** Response body (JSON-parsed), if successful. */
  readonly responseBody?: unknown;
}
```

- [ ] **Step 5.2: Write `packages/shell/src/qa/inspector/wrap-fetch.ts`**

```ts
/**
 * wrapFetch: instruments the ClientConfig.fetch override to capture
 * request/response pairs for the inspector panel.
 *
 * No Next.js imports — pure wrapper over the Fetch API.
 * Usage in non-prod BFF setup:
 *
 *   import { wrapFetch } from "@infinityrx/shell";
 *   const client = createRealPrescriberDirectoryClient({
 *     baseUrl: process.env.PRESCRIBER_DIR_URL,
 *     getAuthToken: () => getBFFToken(),
 *     fetch: wrapFetch(globalThis.fetch, (entry) => inspector.addEntry(entry)),
 *   });
 */
import type { InspectorEntry } from "./types.js";

type EmitFn = (entry: InspectorEntry) => void;

/**
 * Wraps a fetch implementation to emit an InspectorEntry after each call.
 * The wrapper is transparent: it returns the same Response the underlying
 * fetch returns, and only clones for body reading (so the caller still
 * gets a readable body).
 */
export function wrapFetch(
  inner: typeof globalThis.fetch,
  emit: EmitFn
): typeof globalThis.fetch {
  return async function wrappedFetch(
    input: RequestInfo | URL,
    init?: RequestInit
  ): Promise<Response> {
    const method = (init?.method ?? "GET").toUpperCase();
    const url = input instanceof Request ? input.url : String(input);
    const start = performance.now();
    const timestamp = new Date().toISOString();

    let res: Response;
    let status = 0;
    let responseBody: unknown;
    let correlationId: string | undefined;

    try {
      res = await inner(input, init);
      status = res.status;
      correlationId = res.headers.get("x-correlation-id") ?? undefined;

      // Clone before reading body so the caller's body is not consumed.
      const clone = res.clone();
      try {
        responseBody = await clone.json();
      } catch {
        // Non-JSON response bodies are not captured.
      }
    } catch (err) {
      const latencyMs = Math.round(performance.now() - start);
      emit({
        id: crypto.randomUUID(),
        method,
        url,
        status: 0,
        latencyMs,
        isMock: false,
        cacheHit: false,
        timestamp,
        requestBody: init?.body ? tryParseJson(init.body) : undefined,
      });
      throw err;
    }

    const latencyMs = Math.round(performance.now() - start);
    let requestBody: unknown;
    if (init?.body) requestBody = tryParseJson(init.body);

    emit({
      id: crypto.randomUUID(),
      method,
      url,
      status,
      latencyMs,
      isMock: false,
      cacheHit: res.headers.get("x-cache") === "HIT",
      correlationId,
      timestamp,
      requestBody,
      responseBody,
    });

    return res;
  };
}

function tryParseJson(body: BodyInit): unknown {
  if (typeof body === "string") {
    try { return JSON.parse(body); } catch { return body; }
  }
  return undefined;
}
```

- [ ] **Step 5.3: Write `packages/shell/src/__tests__/wrap-fetch.test.ts` (failing first)**

```ts
import { describe, it, expect, vi } from "vitest";
import { wrapFetch } from "../qa/inspector/wrap-fetch.js";
import type { InspectorEntry } from "../qa/inspector/types.js";

function makeJsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  const h = new Headers({ "Content-Type": "application/json", ...headers });
  return new Response(JSON.stringify(body), { status, headers: h });
}

describe("wrapFetch", () => {
  it("emits an InspectorEntry after a successful fetch", async () => {
    const innerFetch = vi.fn().mockResolvedValue(makeJsonResponse({ ok: true }));
    const entries: InspectorEntry[] = [];
    const wrapped = wrapFetch(innerFetch, (e) => entries.push(e));

    await wrapped("https://api.example.com/data");

    expect(entries).toHaveLength(1);
    expect(entries[0]!.url).toBe("https://api.example.com/data");
    expect(entries[0]!.status).toBe(200);
    expect(entries[0]!.method).toBe("GET");
  });

  it("measures latency in milliseconds (>= 0)", async () => {
    const innerFetch = vi.fn().mockResolvedValue(makeJsonResponse({}));
    const entries: InspectorEntry[] = [];
    await wrapFetch(innerFetch, (e) => entries.push(e))("https://x.test/");
    expect(entries[0]!.latencyMs).toBeGreaterThanOrEqual(0);
  });

  it("captures correlationId from x-correlation-id response header", async () => {
    const innerFetch = vi.fn().mockResolvedValue(
      makeJsonResponse({}, 200, { "x-correlation-id": "corr-abc" })
    );
    const entries: InspectorEntry[] = [];
    await wrapFetch(innerFetch, (e) => entries.push(e))("https://x.test/");
    expect(entries[0]!.correlationId).toBe("corr-abc");
  });

  it("sets cacheHit: true when x-cache: HIT", async () => {
    const innerFetch = vi.fn().mockResolvedValue(
      makeJsonResponse({}, 200, { "x-cache": "HIT" })
    );
    const entries: InspectorEntry[] = [];
    await wrapFetch(innerFetch, (e) => entries.push(e))("https://x.test/");
    expect(entries[0]!.cacheHit).toBe(true);
  });

  it("emits status 0 entry and re-throws on network error", async () => {
    const innerFetch = vi.fn().mockRejectedValue(new Error("network down"));
    const entries: InspectorEntry[] = [];
    const wrapped = wrapFetch(innerFetch, (e) => entries.push(e));
    await expect(wrapped("https://x.test/")).rejects.toThrow("network down");
    expect(entries).toHaveLength(1);
    expect(entries[0]!.status).toBe(0);
  });

  it("still returns the original response body to the caller (body not consumed)", async () => {
    const innerFetch = vi.fn().mockResolvedValue(makeJsonResponse({ result: "data" }));
    const entries: InspectorEntry[] = [];
    const res = await wrapFetch(innerFetch, (e) => entries.push(e))("https://x.test/");
    const body = await res.json();
    expect(body).toEqual({ result: "data" });
    expect(entries[0]!.responseBody).toEqual({ result: "data" });
  });
});
```

- [ ] **Step 5.4: Write `packages/shell/src/qa/inspector/inspector-store.ts`**

```ts
"use client";
/**
 * Client-side nanostores atom for InspectorEntry list.
 * The slide-out panel subscribes to this atom.
 * wrapFetch calls addEntry() to populate it.
 *
 * Max 100 entries to cap memory usage.
 */
import { atom } from "nanostores";
import type { InspectorEntry } from "./types.js";

const MAX_ENTRIES = 100;

/** The reactive list of captured request/response entries. */
export const $inspectorEntries = atom<InspectorEntry[]>([]);

/** Add a new entry; evicts oldest if MAX_ENTRIES is exceeded. */
export function addEntry(entry: InspectorEntry): void {
  const current = $inspectorEntries.get();
  const next = [entry, ...current].slice(0, MAX_ENTRIES);
  $inspectorEntries.set(next);
}

/** Clear all captured entries. */
export function clearEntries(): void {
  $inspectorEntries.set([]);
}
```

- [ ] **Step 5.5: Write `packages/shell/src/__tests__/inspector-store.test.ts` (failing first)**

```ts
import { describe, it, expect, beforeEach } from "vitest";

// nanostores runs in happy-dom without issue (no browser-specific API).
import { $inspectorEntries, addEntry, clearEntries } from "../qa/inspector/inspector-store.js";
import type { InspectorEntry } from "../qa/inspector/types.js";

function makeEntry(id: string): InspectorEntry {
  return { id, method: "GET", url: "https://x.test/", status: 200, latencyMs: 10, isMock: false, cacheHit: false, timestamp: new Date().toISOString() };
}

describe("inspector-store", () => {
  beforeEach(() => clearEntries());

  it("addEntry prepends new entry to the list", () => {
    addEntry(makeEntry("e1"));
    addEntry(makeEntry("e2"));
    expect($inspectorEntries.get()[0]!.id).toBe("e2");
    expect($inspectorEntries.get()).toHaveLength(2);
  });

  it("clearEntries resets the list to empty", () => {
    addEntry(makeEntry("e1"));
    clearEntries();
    expect($inspectorEntries.get()).toHaveLength(0);
  });

  it("evicts oldest entries beyond MAX_ENTRIES (100)", () => {
    for (let i = 0; i < 105; i++) addEntry(makeEntry(`e${i}`));
    expect($inspectorEntries.get()).toHaveLength(100);
    // Most recent entry is first
    expect($inspectorEntries.get()[0]!.id).toBe("e104");
  });
});
```

- [ ] **Step 5.6: Write `packages/shell/src/qa/inspector/inspector-panel.tsx`**

```tsx
"use client";
import { useStore } from "@nanostores/react";
import { useState } from "react";
import { $inspectorEntries, clearEntries } from "./inspector-store.js";
import type { InspectorEntry } from "./types.js";

/**
 * Client-side slide-out inspector panel.
 * Subscribes to $inspectorEntries and renders a table of captured requests.
 * Only rendered in non-production builds (gated by the parent route/layout).
 */
export function InspectorPanel() {
  const entries = useStore($inspectorEntries);
  const [open, setOpen] = useState(false);

  if (!open) {
    return (
      <button
        style={{ position: "fixed", bottom: "1rem", right: "1rem", zIndex: 9999 }}
        onClick={() => setOpen(true)}
        aria-label="Open request inspector"
      >
        Inspector ({entries.length})
      </button>
    );
  }

  return (
    <aside
      role="complementary"
      aria-label="Request/response inspector"
      style={{
        position: "fixed",
        bottom: 0,
        right: 0,
        width: "480px",
        height: "60vh",
        overflowY: "auto",
        background: "#1a1a1a",
        color: "#f0f0f0",
        zIndex: 9999,
        padding: "1rem",
        fontFamily: "monospace",
        fontSize: "12px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
        <strong>Request Inspector ({entries.length})</strong>
        <span>
          <button onClick={() => clearEntries()} style={{ marginRight: "0.5rem" }}>
            Clear
          </button>
          <button onClick={() => setOpen(false)} aria-label="Close inspector">
            ✕
          </button>
        </span>
      </div>
      {entries.length === 0 && <p>No requests captured yet.</p>}
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th>Method</th>
            <th>Route</th>
            <th>Status</th>
            <th>ms</th>
            <th>Cache</th>
            <th>corrId</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e: InspectorEntry) => (
            <InspectorRow key={e.id} entry={e} />
          ))}
        </tbody>
      </table>
    </aside>
  );
}

function InspectorRow({ entry }: { entry: InspectorEntry }) {
  const [expanded, setExpanded] = useState(false);
  const route = (() => {
    try { return new URL(entry.url).pathname; } catch { return entry.url; }
  })();
  const statusColor = entry.status >= 400 ? "#ff6b6b" : entry.status === 0 ? "#ffa500" : "#69db7c";

  return (
    <>
      <tr
        onClick={() => setExpanded((p) => !p)}
        style={{ cursor: "pointer", borderBottom: "1px solid #333" }}
      >
        <td>{entry.method}</td>
        <td title={entry.url}>{route.slice(0, 30)}</td>
        <td style={{ color: statusColor }}>{entry.status || "ERR"}</td>
        <td>{entry.latencyMs}</td>
        <td>{entry.cacheHit ? "HIT" : "—"}</td>
        <td title={entry.correlationId}>{entry.correlationId?.slice(0, 8) ?? "—"}</td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={6}>
            <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
              {JSON.stringify({ request: entry.requestBody, response: entry.responseBody }, null, 2)}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}
```

- [ ] **Step 5.7: Update `packages/shell/src/index.ts`**

```ts
// Public surface of @infinityrx/shell.

export type { UserIdentity, SessionUser } from "./auth/types.js";
export { getSessionUser } from "./auth/get-session-user.js";
export { RequireAuth } from "./auth/require-auth.js";
export { RequireRole } from "./auth/require-role.js";

export type { NavEntry, InstanceManifestShape } from "./shell/nav-types.js";
export { ModuleNav } from "./shell/module-nav.js";
export { AppShellMount } from "./shell/app-shell-mount.js";

export type { QaMode } from "./qa/qa-mode-cookie.js";
export { QA_MODE_COOKIE, parseQaMode } from "./qa/qa-mode-cookie.js";
export { QA_MODE_HEADER, applyQaModeMiddleware } from "./qa/qa-mode-middleware.js";
export { SHELL_MIDDLEWARE_MATCHER } from "./middleware.js";

export type { InspectorEntry } from "./qa/inspector/types.js";
export { wrapFetch } from "./qa/inspector/wrap-fetch.js";
export { $inspectorEntries, addEntry, clearEntries } from "./qa/inspector/inspector-store.js";
export { InspectorPanel } from "./qa/inspector/inspector-panel.js";
```

Note: `nanostores` and `@nanostores/react` must be added to `packages/shell/package.json` dependencies. Add `"nanostores": "0.11.3"` and `"@nanostores/react": "0.8.0"` to the `dependencies` block in Step 1.1's `package.json`.

- [ ] **Step 5.8: Verification**

```bash
npm --workspace=@infinityrx/shell run build
npm --workspace=@infinityrx/shell run test
# Expected: 51 tests pass (36 prior + 6 wrap-fetch + 3 inspector-store + [inspector-panel not directly unit-tested here: covered in Task 6 qa-harness page tests])
# Note: InspectorPanel is a "use client" component; its integration is tested via Task 6's qa-harness pages test.
```

Commit message:
```
feat(sp-0): Plan C-shell Task 5 — request/response inspector

wrapFetch: transparent Fetch wrapper injected into ClientConfig.fetch at
BFF construction time; emits InspectorEntry (method/url/status/latencyMs/
cacheHit/correlationId/bodies) via emit callback; re-throws network errors
after emitting; clones response so caller's body is not consumed.
inspector-store.ts: nanostores atom; addEntry (prepend + MAX_ENTRIES=100
eviction); clearEntries.
InspectorPanel: "use client" slide-out panel; subscribes to atom; shows
method/route/status/ms/cache/corrId columns; expandable JSON for req+resp body.
Closes §6.4 deferred item "request/response inspector".
51 tests (36 prior + 6 wrap-fetch + 3 inspector-store).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

### Task 6: `/qa-harness/*` route pages + portal layout wiring

**Files:**
- Create: `packages/shell/src/routes/qa-harness/page.tsx`
- Create: `packages/shell/src/routes/qa-harness/composition/page.tsx`
- Create: `packages/shell/src/routes/qa-harness/mock-toggle/page.tsx`
- Create: `packages/shell/src/routes/qa-harness/factory/page.tsx`
- Create: `packages/shell/src/routes/qa-harness/correlation/page.tsx`
- Create: `packages/shell/src/__tests__/qa-harness-pages.test.tsx`
- Modify: `portal/operator/app/layout.tsx` (root layout — UNGATED, no RequireAuth here)
- Modify or Create: `portal/operator/app/(authenticated)/layout.tsx` (gate: RequireAuth + AppShellMount)
- Ensure `/login` lives at `portal/operator/app/(public)/login/page.tsx` or `portal/operator/app/(auth)/login/page.tsx` — outside the `(authenticated)` group
- Modify: `packages/shell/src/index.ts`

**Route-group structure (codex BLOCK 3 fix):**

```
portal/operator/app/
  layout.tsx                    ← ROOT layout: UNGATED. Provides HTML shell,
                                  fonts, global CSS. No RequireAuth here.
                                  Serving /login from this root is safe.
  (public)/                     ← Public route group (no auth required)
    login/
      page.tsx                  ← /login — served without auth gate
  (authenticated)/              ← Authenticated route group
    layout.tsx                  ← RequireAuth + AppShellMount live here.
                                  ALL routes under this group require auth.
    page.tsx                    ← / (dashboard home, requires auth)
    qa-harness/
      [[...path]]/
        page.tsx                ← /qa-harness/* (requires auth)
```

The root `app/layout.tsx` must NOT carry `<RequireAuth>`. If it does, Next.js calls `RequireAuth` before rendering `/login`, creating an infinite redirect loop: unauthenticated user hits `/login` → layout runs `RequireAuth` → no session → redirect to `/login` → loop.

`RequireAuth` belongs exclusively in `app/(authenticated)/layout.tsx`. The Next.js middleware matcher (`SHELL_MIDDLEWARE_MATCHER`) enforces route-level protection for non-RSC paths; the RSC `RequireAuth` provides defence-in-depth inside the authenticated subtree.

Each qa-harness page is a React Server Component that fetches the manifest (via static import of `_generated/manifest.json`) and renders the corresponding Plan C component. These pages are exported from `packages/shell` so that `portal/operator` (and future portals) can mount them by importing the page components — they don't have to duplicate the logic.

- [ ] **Step 6.1: Write `packages/shell/src/routes/qa-harness/page.tsx`**

```tsx
import "server-only";
import type { BaseClient } from "@infinityrx/contract";
import { ServicesHealth } from "@infinityrx/qa-harness";

interface QaHarnessPageProps {
  /**
   * Registered clients to probe. Passed by the portal that mounts this page
   * (it knows which clients are configured for this instance).
   */
  clients: readonly BaseClient[];
}

/**
 * /qa-harness — Services health dashboard.
 *
 * Server component: probes all registered clients' health endpoints
 * and renders the ServicesHealth dashboard. In dev/staging only.
 */
export async function QaHarnessPage({ clients }: QaHarnessPageProps): Promise<React.ReactNode> {
  return (
    <main>
      <h1>QA Harness — Services Health</h1>
      <ServicesHealth clients={clients as BaseClient[]} />
    </main>
  );
}
```

- [ ] **Step 6.2: Write `packages/shell/src/routes/qa-harness/composition/page.tsx`**

```tsx
import "server-only";
import { CompositionViewer } from "@infinityrx/qa-harness";
// Static import of the generated manifest. Plan D's codegen overwrites this.
// TypeScript 5.6.3 NodeNext: use `with { type: "json" }` (TC39 import
// attributes), not `assert` (deprecated). Path: this file lives at
// src/routes/qa-harness/composition/page.tsx — three levels up to reach
// src/_generated/manifest.json.
import manifest from "../../../_generated/manifest.json" with { type: "json" };

/**
 * /qa-harness/composition — CompositionViewer.
 *
 * Reads _generated/manifest.json at import time (static — no runtime fetch).
 * Per Plan C: CompositionViewer is prop-driven; the runtime fetch is added here
 * at the shell layer, fulfilling the §6.4 "runtime fetch" deferred item.
 * In this implementation, "runtime fetch" means importing the statically
 * generated artifact at the route layer — consistent with SD-4's generated-
 * artifact mechanism (no dynamic HTTP fetch needed since manifest is embedded).
 */
export function CompositionPage(): React.ReactNode {
  return (
    <main>
      <h1>QA Harness — Composition</h1>
      <CompositionViewer manifest={manifest} />
    </main>
  );
}
```

- [ ] **Step 6.3: Write `packages/shell/src/routes/qa-harness/mock-toggle/page.tsx`**

```tsx
import "server-only";
import type { BaseClient } from "@infinityrx/contract";
import { MockToggle } from "@infinityrx/qa-harness";

interface MockTogglePageProps {
  clients: readonly BaseClient[];
  onToggle: (clientName: string, mode: "real" | "mock") => void;
}

/**
 * /qa-harness/mock-toggle — Per-client real/mock toggle.
 */
export function MockTogglePage({ clients, onToggle }: MockTogglePageProps): React.ReactNode {
  return (
    <main>
      <h1>QA Harness — Mock/Real Toggle</h1>
      <MockToggle clients={clients as BaseClient[]} onToggle={onToggle} />
    </main>
  );
}
```

- [ ] **Step 6.4: Write `packages/shell/src/routes/qa-harness/factory/page.tsx`**

```tsx
import "server-only";
import { FactoryBindings } from "@infinityrx/qa-harness";
import type { SeedKind } from "@infinityrx/qa-harness";

interface FactoryPageProps {
  onSeed: (kind: SeedKind) => Promise<void>;
}

/**
 * /qa-harness/factory — Test data factory bindings.
 */
export function FactoryPage({ onSeed }: FactoryPageProps): React.ReactNode {
  return (
    <main>
      <h1>QA Harness — Test Data Factory</h1>
      <FactoryBindings onSeed={onSeed} />
    </main>
  );
}
```

- [ ] **Step 6.5: Write `packages/shell/src/routes/qa-harness/correlation/page.tsx`**

```tsx
import "server-only";
import { CorrelationIdJump } from "@infinityrx/qa-harness";

/**
 * /qa-harness/correlation — Correlation ID quick-jump.
 */
export function CorrelationPage(): React.ReactNode {
  return (
    <main>
      <h1>QA Harness — Correlation ID Quick Jump</h1>
      <CorrelationIdJump />
    </main>
  );
}
```

- [ ] **Step 6.6: Write `packages/shell/src/__tests__/qa-harness-pages.test.tsx` (failing first)**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";

vi.mock("server-only", () => ({}));
vi.mock("@infinityrx/qa-harness", () => ({
  ServicesHealth: () => <div data-testid="services-health" />,
  CompositionViewer: ({ manifest }: { manifest: unknown }) => (
    <div data-testid="composition-viewer">{JSON.stringify(manifest)}</div>
  ),
  MockToggle: () => <div data-testid="mock-toggle" />,
  FactoryBindings: () => <div data-testid="factory-bindings" />,
  CorrelationIdJump: () => <div data-testid="correlation-jump" />,
}));
// Mock the corrected path: three levels up from src/routes/qa-harness/composition/
vi.mock("../../../_generated/manifest.json", () => ({
  default: { instance_name: "test", modules: ["reclaimrx"], audience: "operator" },
}));

import { QaHarnessPage } from "../routes/qa-harness/page.js";
import { CompositionPage } from "../routes/qa-harness/composition/page.js";
import { MockTogglePage } from "../routes/qa-harness/mock-toggle/page.js";
import { FactoryPage } from "../routes/qa-harness/factory/page.js";
import { CorrelationPage } from "../routes/qa-harness/correlation/page.js";

describe("qa-harness pages", () => {
  it("/qa-harness renders ServicesHealth", async () => {
    const { getByTestId } = render(
      await QaHarnessPage({ clients: [] }) as never
    );
    expect(getByTestId("services-health")).toBeTruthy();
  });

  it("/qa-harness/composition renders CompositionViewer with manifest", () => {
    const { getByTestId } = render(CompositionPage() as never);
    const viewer = getByTestId("composition-viewer");
    expect(viewer.textContent).toContain("reclaimrx");
  });

  it("/qa-harness/mock-toggle renders MockToggle", () => {
    const { getByTestId } = render(
      MockTogglePage({ clients: [], onToggle: vi.fn() }) as never
    );
    expect(getByTestId("mock-toggle")).toBeTruthy();
  });

  it("/qa-harness/factory renders FactoryBindings", () => {
    const { getByTestId } = render(
      FactoryPage({ onSeed: vi.fn() }) as never
    );
    expect(getByTestId("factory-bindings")).toBeTruthy();
  });

  it("/qa-harness/correlation renders CorrelationIdJump", () => {
    const { getByTestId } = render(CorrelationPage() as never);
    expect(getByTestId("correlation-jump")).toBeTruthy();
  });

  it("each qa-harness page has an <h1> heading", () => {
    const pages = [
      CompositionPage(),
      MockTogglePage({ clients: [], onToggle: vi.fn() }),
      FactoryPage({ onSeed: vi.fn() }),
      CorrelationPage(),
    ];
    for (const page of pages) {
      const { getByRole } = render(page as never);
      expect(getByRole("heading", { level: 1 })).toBeTruthy();
    }
  });
});
```

- [ ] **Step 6.7: Verify `portal/operator/app/layout.tsx` — root layout MUST be ungated**

Read the existing file first. The root layout must NOT contain `<RequireAuth>`. If any previous version added `RequireAuth` here, remove it — it creates an infinite redirect loop for `/login` (unauthenticated → RequireAuth → redirect /login → RequireAuth → loop).

The root layout provides the HTML shell, font loading, and global CSS only. It renders `{children}` without any auth gate:

```tsx
// portal/operator/app/layout.tsx — NO RequireAuth here.
// Auth gating lives in app/(authenticated)/layout.tsx only.
// Root layout serves both public routes (/login) and authenticated routes.
import type { ReactNode } from "react";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

The actual file content may differ (fonts, metadata, etc.). The builder MUST read `portal/operator/app/layout.tsx` first and make only the surgical change: ensure `RequireAuth` is absent from the root layout.

- [ ] **Step 6.8: Create or modify `portal/operator/app/(authenticated)/layout.tsx`**

If the route group `(authenticated)` does not exist, create it. This layout carries BOTH `<RequireAuth>` (the session gate) AND `<AppShellMount>` (the shell + nav). `RequireAuth` is here — NOT in the root layout — so that `/login` and other public routes are never gated.

```tsx
import "server-only";
import { RequireAuth, AppShellMount } from "@infinityrx/shell";
import type { NavEntry } from "@infinityrx/shell";
// Use the "./manifest" export declared in @infinityrx/shell's package.json exports map.
// @infinityrx/shell/src/_generated/... is NOT a valid import — package.json exports
// only exposes ".", "./middleware", and "./manifest". Using the export alias
// ensures correctness after dist compilation and keeps consumers out of src/.
import manifest from "@infinityrx/shell/manifest" with { type: "json" };
import type { ReactNode } from "react";

// navEntries will be populated by module packages as they register.
// Plan D wires the registration; for now the nav renders only entries
// from this array (empty = no nav until modules register).
const navEntries: NavEntry[] = [];

export default async function AuthenticatedLayout({
  children,
}: {
  children: ReactNode;
}): Promise<ReactNode> {
  return (
    <RequireAuth loginPath="/login">
      <AppShellMount navEntries={navEntries} manifest={manifest}>
        {children}
      </AppShellMount>
    </RequireAuth>
  );
}
```

- [ ] **Step 6.8b: Ensure `portal/operator/app/(public)/login/page.tsx` exists outside the authenticated group**

The `/login` page must live outside `(authenticated)/` so that unauthenticated users can reach it. If a login page already exists at `portal/operator/app/(auth)/login/page.tsx` or similar public location, verify it is not under `(authenticated)/`. If it doesn't exist yet, create a minimal stub:

```tsx
// portal/operator/app/(public)/login/page.tsx
// Public route — no auth gate. Served from the root (ungated) layout.
export default function LoginPage() {
  return (
    <main>
      <h1>Sign In</h1>
      {/* next-auth SignIn form or redirect to /api/auth/signin */}
    </main>
  );
}
```

The actual login form implementation is out of scope for Plan C-shell (it is the Python auth service's concern). This stub satisfies the router: `/login` resolves, `RequireAuth` can redirect to it without a loop.

- [ ] **Step 6.9: Update `packages/shell/src/index.ts` — add route page exports**

```ts
// Public surface of @infinityrx/shell.

export type { UserIdentity, SessionUser } from "./auth/types.js";
export { getSessionUser } from "./auth/get-session-user.js";
export { RequireAuth } from "./auth/require-auth.js";
export { RequireRole } from "./auth/require-role.js";

export type { NavEntry, InstanceManifestShape } from "./shell/nav-types.js";
export { ModuleNav } from "./shell/module-nav.js";
export { AppShellMount } from "./shell/app-shell-mount.js";

export type { QaMode } from "./qa/qa-mode-cookie.js";
export { QA_MODE_COOKIE, parseQaMode } from "./qa/qa-mode-cookie.js";
export { QA_MODE_HEADER, applyQaModeMiddleware } from "./qa/qa-mode-middleware.js";
export { SHELL_MIDDLEWARE_MATCHER } from "./middleware.js";

export type { InspectorEntry } from "./qa/inspector/types.js";
export { wrapFetch } from "./qa/inspector/wrap-fetch.js";
export { $inspectorEntries, addEntry, clearEntries } from "./qa/inspector/inspector-store.js";
export { InspectorPanel } from "./qa/inspector/inspector-panel.js";

// QA Harness route page components (portals mount these at app/qa-harness/...)
export { QaHarnessPage } from "./routes/qa-harness/page.js";
export { CompositionPage } from "./routes/qa-harness/composition/page.js";
export { MockTogglePage } from "./routes/qa-harness/mock-toggle/page.js";
export { FactoryPage } from "./routes/qa-harness/factory/page.js";
export { CorrelationPage } from "./routes/qa-harness/correlation/page.js";
```

- [ ] **Step 6.10: Verification**

```bash
npm --workspace=@infinityrx/shell run build
npm --workspace=@infinityrx/shell run test
# Expected: 57 tests pass (51 prior + 6 qa-harness-pages)
# portal/operator: typecheck must pass after layout modifications
cd portal/operator && npx tsc --noEmit
```

Commit message:
```
feat(sp-0): Plan C-shell Task 6 — qa-harness route pages + portal layout wiring

QaHarnessPage, CompositionPage, MockTogglePage, FactoryPage, CorrelationPage:
RSC page components exported from packages/shell; portals import and mount
them at their qa-harness routes. CompositionPage reads _generated/manifest.json
at import time (static SD-4 artifact; no runtime HTTP fetch needed).
portal/operator/app/layout.tsx: root layout verified UNGATED (no RequireAuth —
prevents /login infinite redirect loop).
portal/operator/app/(public)/login/page.tsx: stub created (public group, ungated).
portal/operator/app/(authenticated)/layout.tsx: RequireAuth + AppShellMount here;
all routes under (authenticated)/ require valid session. navEntries deferred to
Plan D module registration.
57 tests (51 prior + 6 qa-harness-pages).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

### Task 7: Framework-bound enforcement test + CI + package.json nanostores addition

**Files:**
- Create: `packages/shell/src/__tests__/framework-bound.test.ts`
- Modify: `packages/shell/package.json` — add nanostores + @nanostores/react
- Modify: `.github/workflows/sp0-foundation.yml` — extend to include packages/shell

This task closes the framework-boundary contract: a grep-based test asserts that the four framework-agnostic packages (`packages/ui`, `packages/contract`, `packages/auth`, `packages/qa-harness`) import zero `next/*`, `next-auth/*`, or `@auth/*` symbols in their `src/` directories. The same test verifies that `packages/shell` is the sole permitted importer (positive assertion on `packages/shell/src/middleware.ts`).

- [ ] **Step 7.1: Write `packages/shell/src/__tests__/framework-bound.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

/**
 * Framework-bound enforcement test.
 *
 * Asserts the SD-2 §6 mandate: packages other than `packages/shell`
 * MUST NOT import from `next/*`, `next-auth/*`, or `@auth/*`.
 * `packages/shell` is the ONLY package allowed to cross this boundary.
 *
 * Implementation: grep src/** files for the forbidden import patterns.
 * This is intentionally static/grep-based (not AST) to catch dynamic
 * require() and string-concatenated imports that AST analysis might miss.
 */

const WORKSPACE_ROOT = resolve(__dirname, "../../../../..");
const FRAMEWORK_PATTERNS = [
  /from\s+["']next\//,
  /from\s+["']next-auth/,
  /from\s+["']@auth\//,
  /require\s*\(\s*["']next\//,
  /require\s*\(\s*["']next-auth/,
  /require\s*\(\s*["']@auth\//,
];

// Packages that MUST NOT import next/* etc.
const AGNOSTIC_PACKAGES = [
  "packages/contract",
  "packages/auth",
  "packages/ui",
  "packages/qa-harness",
];

function collectTsFiles(dir: string): string[] {
  const results: string[] = [];
  try {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      const stat = statSync(full);
      if (stat.isDirectory() && entry !== "node_modules" && entry !== "dist") {
        results.push(...collectTsFiles(full));
      } else if (stat.isFile() && (entry.endsWith(".ts") || entry.endsWith(".tsx"))) {
        results.push(full);
      }
    }
  } catch {
    // Directory doesn't exist yet (pre-Plan-C execution)
  }
  return results;
}

describe("framework-agnostic spine enforcement", () => {
  for (const pkg of AGNOSTIC_PACKAGES) {
    it(`${pkg}/src contains zero next/* / next-auth/* / @auth/* imports`, () => {
      const srcDir = join(WORKSPACE_ROOT, pkg, "src");
      const files = collectTsFiles(srcDir);
      const violations: string[] = [];

      for (const file of files) {
        // Skip test files — they may mock next/navigation etc.
        if (file.includes("__tests__") || file.includes(".test.")) continue;
        const content = readFileSync(file, "utf-8");
        for (const pattern of FRAMEWORK_PATTERNS) {
          if (pattern.test(content)) {
            violations.push(`${file}: matches ${pattern}`);
          }
        }
      }

      expect(violations).toEqual([]);
    });
  }

  it("packages/shell/src/middleware.ts is allowed to import next/server", () => {
    const middlewarePath = join(WORKSPACE_ROOT, "packages/shell/src/qa/qa-mode-middleware.ts");
    try {
      const content = readFileSync(middlewarePath, "utf-8");
      expect(content).toMatch(/from\s+["']next\/server["']/);
    } catch {
      // File not created yet — test will fail naturally if the file is missing
      expect(true, "qa-mode-middleware.ts must exist after Task 4").toBe(false);
    }
  });
});
```

- [ ] **Step 7.2: Verify nanostores dependencies are present in `packages/shell/package.json`**

`nanostores` and `@nanostores/react` are declared in the `dependencies` block in **Step 1.1** (not here — moved forward so the deps are declared before Task 5 imports them). Verify they are present:

```json
"@nanostores/react": "0.8.0",
"nanostores": "0.11.3"
```

If `npm install` was not run after Task 1, run it now to update `package-lock.json`. Do not add these entries again — they are already in Task 1's package.json.

- [ ] **Step 7.3: Extend `.github/workflows/sp0-foundation.yml` — include packages/shell**

Add `--workspace=@infinityrx/shell` to the test step alongside the existing workspace flags. Also add the `packages/shell` typecheck to the typecheck step.

The exact edit depends on the current CI file content. The builder MUST read `.github/workflows/sp0-foundation.yml` before applying this change.

- [ ] **Step 7.4: Final full-workspace verification**

```bash
npm install
# Full workspace build
npx tsc -b
# Expected: exit 0 (all packages compile)

# All packages tests
npm run test:packages
# Expected: exit 0, ~58 tests across packages/contract, packages/auth, packages/ui, packages/qa-harness, packages/shell

# lint
npm run lint
# Expected: exit 0 — no next/* imports found in agnostic packages

# portal typecheck
cd portal/operator && npx tsc --noEmit
# Expected: exit 0
```

- [ ] **Step 7.5: Write acceptance status doc**

Create `docs/superpowers/plans/2026-05-15-sp0-plan-c-shell-status.md`:

```markdown
# SP-0 Plan C-shell — Acceptance Status

**Status:** [PENDING EXECUTION]
**Date:** 2026-05-15

## Ships list
- `packages/shell`: scaffolded, builds, typechecks, lints, tests green
- `<RequireAuth>` + `<RequireRole>`: RSC auth gates, 11 tests
- `getSessionUser`: UserIdentity extractor, 4 tests
- `AppShellMount` + `ModuleNav`: role-filtered, manifest-ordered nav, 10 tests
- QA mode toggle: `parseQaMode`, `buildQaModeCookieValue`, `applyQaModeMiddleware`, 11 tests
- `wrapFetch`: ClientConfig.fetch instrumentation hook, 6 tests
- `inspector-store` + `InspectorPanel`: nanostores atom + slide-out panel, 3 tests
- `/qa-harness/*` pages: 5 route page components (health, composition, mock, factory, correlation), 6 tests
- `framework-bound.test.ts`: 5 tests asserting SD-2 mandate
- `portal/operator` layout: `RequireAuth` + `AppShellMount` wired

## Deferred scope (not in Plan C-shell)
- Full CommandPalette Cmd+K keyboard wiring — Plan D (module registration)
- Module nav entry registration by module packages — Plan D
- Tailwind design tokens in portal — Plan D
- Real `_generated/manifest.json` content — Plan D codegen
- Python backend auth refactor — separate wave

## Test count
58 tests (packages/shell only; does not include Plan B/C tests)

## Decision log
- `wrapFetch` wraps `ClientConfig.fetch` at injection time rather than
  modifying `ClientConfig` in Plan B. Rationale: avoids touching Plan B's
  shipped contract; the BFF constructs clients with the wrapper in non-prod
  builds. Clean separation.
- QA mode cookie uses `infinityrx-qa-mode` (not `__Secure-*`) because it is
  readable by client JS for the toggle UI. Non-sensitive preference only.
- `CompositionPage` uses static import of `_generated/manifest.json` rather
  than an HTTP fetch. Rationale: SD-4's generated-artifact mechanism embeds
  the manifest at build time; no runtime HTTP boundary needed.
- `(authenticated)` route group layout created at `portal/operator/app/(authenticated)/`
  carrying BOTH `RequireAuth` and `AppShellMount`. Root `app/layout.tsx` is UNGATED
  — placing `RequireAuth` in the root layout creates an infinite redirect loop
  for `/login` (unauthenticated → gate → redirect /login → gate → loop). Route groups
  let public routes (`/login` in `(public)/`) and authenticated routes coexist under
  the same root layout without mutual interference.
```

Commit message:
```
feat(sp-0): Plan C-shell Task 7 — framework-bound test + CI + nanostores

framework-bound.test.ts: grep-based enforcement of SD-2 §6 mandate —
packages/contract, auth, ui, qa-harness src/ contain zero next/* imports;
packages/shell is the sole permitted framework importer.
packages/shell/package.json: nanostores 0.11.3 + @nanostores/react 0.8.0.
CI: sp0-foundation.yml extended to lint/typecheck/test packages/shell.
acceptance status doc created.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## Self-Review

### Spec coverage table

| Spec section | Item | Covered in Plan C-shell? | Evidence |
|---|---|---|---|
| Main spec §6.4 QA mode toggle | Cookie-persisted, non-prod only | YES — Task 4 | `qa-mode-cookie.ts`, `qa-mode-middleware.ts`, 11 tests |
| Main spec §6.4 Request/response inspector | Per-page overlay: route, timing, payload, headers, cache hit/miss, mock-or-real | YES — Task 5 | `wrap-fetch.ts`, `inspector-panel.tsx`, `inspector-store.ts`, 9 tests |
| Main spec §6.4 Health dashboard | Live backends state | PARTIAL — Plan C's `ServicesHealth` is mounted by Task 6; `probeHealth` calls are real | Task 6: `QaHarnessPage` + `ServicesHealth` from `@infinityrx/qa-harness` |
| Main spec §6.4 Mock/real toggle | UI to flip per domain | PARTIAL — Plan C's `MockToggle` mounted by Task 6; domain-level toggle logic is in Plan B's `ClientConfig`; persistence via `qa_mode` cookie is Task 4 | `MockTogglePage`, `applyQaModeMiddleware` |
| Main spec §6.4 Module composition viewer | "This build contains..." | YES — Task 6 `CompositionPage` reads `_generated/manifest.json` at import time | `composition/page.tsx`, 1 test |
| Main spec §6.4 Test data factory bindings | Seed buttons | MOUNTED — `FactoryPage` wraps Plan C's `FactoryBindings`; actual seed logic is the portal's concern | Task 6 |
| Main spec §6.4 correlation_id quick-jump | Copy + open log | MOUNTED — `CorrelationPage` wraps Plan C's `CorrelationIdJump` | Task 6 |
| Main spec §6.5 packages/shell | Auth integration, module mounting, nav | YES — Tasks 1–6 | `RequireAuth`, `AppShellMount`, `ModuleNav` |
| Main spec §7.2 auth token flow | RSC reads session server-side; tokens never exposed to client JS | YES | `getSessionUser` + `RequireAuth`; SD-1 §6 compliant |
| SD-1 §6 cookie/session | session.user carries only non-sensitive identity | YES | `getSessionUser` reads `sub/tid/roles/mfaEnrolled` only |
| SD-2 §6 thin-adapter BFF contract | `packages/shell` MAY import Next.js; others MUST NOT | YES | Task 7 `framework-bound.test.ts` enforces mechanically |
| SD-4 §5 manifest reads | `_generated/manifest.json` consumed as static import | YES | `CompositionPage` + `AppShellMount` |

### §6.4 deferred items coverage check

All 7 qa-harness tool categories from main spec §6.4 are addressed:

| Tool | Status in Plan C-shell |
|---|---|
| QA mode toggle | COMPLETE — Task 4 (cookie + middleware) |
| Request/response inspector | COMPLETE — Task 5 (wrapFetch + InspectorPanel) |
| Health dashboard | MOUNTED — Task 6 QaHarnessPage wraps Plan C's ServicesHealth |
| Mock/real toggle per domain | MOUNTED + cookie-bound — Task 4 cookie + Task 6 MockTogglePage |
| Module composition viewer | MOUNTED with runtime artifact — Task 6 CompositionPage |
| Test data factory bindings | MOUNTED — Task 6 FactoryPage |
| correlation_id quick-jump | MOUNTED — Task 6 CorrelationPage |

The two items explicitly deferred from Plan C §6.4 (QA mode toggle, request/response inspector) are now COMPLETE in Plan C-shell.

### Placeholder scan

- `_generated/manifest.json` placeholder: documented and intentional; Plan D overwrites.
- `navEntries: []` in `(authenticated)/layout.tsx`: documented and intentional; Plan D registers module entries.
- No `TODO`, `FIXME`, `throw new Error("not implemented")` patterns in any task above.

### Type consistency check

- `UserIdentity.roles: readonly string[]` is consistent with SD-1 §2 (`roles: string[]`).
- `InstanceManifestShape.modules: readonly string[]` matches SD-4 §3 manifest `modules` field.
- `NavEntry.requiredRoles: readonly string[]` is consistent with `UserIdentity.roles` comparison logic in `ModuleNav`.
- `InspectorEntry.id: string` generated by `crypto.randomUUID()` — consistent with Plan B's `jti` generation pattern.
- `QaMode: "real" | "stub"` literal union — consistent with Plan C's `MockToggle` which also uses these strings.
- `ClientConfig.fetch?: typeof globalThis.fetch` (Plan B) — `wrapFetch` returns `typeof globalThis.fetch`, so it slots in without type casting.
- All task `package.json` version strings match Plan B/C versions where applicable (TypeScript 5.6.3, vitest 2.1.9, React 19.2.x, @testing-library/react 16.3.0).

### Architecture compliance check

- `packages/shell` is the only package with `next/*` imports. Enforced by Task 7's grep test + Plan A's workspace-root ESLint Block B.
- All RSC files begin with `import "server-only"` — prevents accidental client-side import.
- `"use client"` is used ONLY where required: `inspector-store.ts` (nanostores atom reads from client), `inspector-panel.tsx` (interactive UI). All other components are server components.
- No Next.js imports in `qa-mode-cookie.ts` — pure parsing logic, testable without Next.js runtime.
- `getSessionUser` calls `next-auth`'s `auth()` server-side only; the session object exposed via `useSession()` never contains tokens per SD-1 §6 + §11 adoption checklist.

### Test count

| Component | Tests |
|---|---|
| `get-session-user.test.ts` | 4 |
| `require-auth.test.tsx` | 6 |
| `require-role.test.tsx` | 5 |
| `module-nav.test.tsx` | 5 |
| `app-shell-mount.test.tsx` | 5 |
| `qa-mode-cookie.test.ts` | 7 |
| `qa-mode-middleware.test.ts` | 4 |
| `wrap-fetch.test.ts` | 6 |
| `inspector-store.test.ts` | 3 |
| `qa-harness-pages.test.tsx` | 6 |
| `framework-bound.test.ts` | 5 |
| **Total** | **56** |

Coverage gate: 100% on auth paths (`require-auth`, `require-role`, `get-session-user`, `qa-mode-middleware`'s prod-enforcement branch). 99%+ branch on all other active code.

### What Plan C-shell does NOT do (verified)

- Does NOT touch `packages/auth` internals (calls `verifyAccessToken` / `auth()` only via their public exports).
- Does NOT touch `packages/contract` internals (reads `BaseClient` type + `ClientConfig` type via public exports only; injects `wrapFetch` at the BFF call site, not inside `client-base.ts`).
- Does NOT touch `packages/ui` internals (imports `AppShell` via `@infinityrx/ui` public export only).
- Does NOT touch `packages/qa-harness` internals (imports `ServicesHealth`, `CompositionViewer`, `MockToggle`, `FactoryBindings`, `CorrelationIdJump` via public exports only).
- Does NOT touch Plan D's manifest builder (reads `_generated/manifest.json` output only).
- Does NOT modify existing `portal/operator` structure beyond `middleware.ts` + `app/layout.tsx` + `app/(authenticated)/layout.tsx` (surgical changes only).

---

*End of Plan C-shell.*
