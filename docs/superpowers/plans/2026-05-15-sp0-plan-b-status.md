# SP-0 Plan B — Status

**Status:** Complete 2026-05-15
**Branch:** `wave/B10-w5-plan-b`
**Final HEAD SHA:** (see Task 7 commit below — filled after commit)
**Plan doc:** `docs/superpowers/plans/2026-05-15-sp0-plan-b-contract-auth.md`
**Base:** Plan A foundation (commit `a7b838c`)

---

## Task SHAs

| Task | SHA | Description |
|---|---|---|
| Task 1 | `db47269` | packages/contract + packages/auth scaffolds |
| Task 2 | `c0880aa` | contract: error envelope + cache policy + base client |
| Task 3 | `7bd2258` | contract: reference client — prescriber-directory |
| Task 4 | `ae512e6` | auth: claim types + crypto + env claim per SD-1 §2-§4 |
| Task 5 | `6a177b1` | auth: mint + verify chain + revocation repo per SD-1 §5/§8 |
| Task 6 | `1e3d61e` | auth: refresh adapter + single-flight + dev JWT per SD-1 §7/§8.6/§11 |
| Task 7 | (this commit) | framework-agnostic tests + CI extension + status doc |

---

## What Ships in Plan B

### packages/contract
- `error-envelope.ts` — `ErrorEnvelopeSchema` + `isErrorEnvelope` type guard
- `cache-policy.ts` — `CachePolicySchema` (ttl_seconds, key, invalidation_tags, backend_down)
- `client-base.ts` — `BaseClient` interface + `ClientConfig` + `ClientFactory`
- `impls/prescriber-directory/types.ts` — `PrescriberSchema`, `NpiSchema`, search request/response
- `impls/prescriber-directory/client.ts` — `PrescriberDirectoryClient` + cache policies
- `impls/prescriber-directory/real.ts` — `createRealPrescriberDirectoryClient` (undici, bearer auth, zod validation)
- `impls/prescriber-directory/mock.ts` — `createMockPrescriberDirectoryClient` (fixture-backed)
- `__tests__/framework-agnostic.test.ts` — enforces zero Next.js/next-auth/@auth imports in src/

### packages/auth
- `errors.ts` — `AuthError` class + `AUTH_ERROR_MESSAGES` + `AuthErrorCode` union
- `env-claim.ts` — `EnvClaimSchema` + `resolveEnvClaim`
- `claims.ts` — `AccessClaimsSchema` (.strict()) + `RefreshClaimsSchema` (.strict())
- `crypto.ts` — `signAccessToken`, `signRefreshToken`, `verifyTokenRaw`, `assertJwtSecret`
- `revocation-repo.ts` — `RevocationRepo` interface + `InMemoryRevocationRepo`
- `mint.ts` — `mintTokenPair` with SD-1 §8.5 post-reset iat clamping
- `verify.ts` — `verifyAccessToken` + `verifyRefreshToken` (full §8 chain)
- `refresh-adapter.ts` — `performRefresh` (§8.6 verify → atomic consume → mint)
- `single-flight.ts` — `SingleFlightRefresh<T>` + `readJtiUnsafe`
- `dev-jwt.ts` — `mintDevJwt` (refuses production) + `DEV_IDENTITY`
- `__tests__/framework-agnostic.test.ts` — enforces zero Next.js/next-auth/@auth imports in src/

---

## What Is NOT in Plan B (explicitly deferred)

- The other 12 typed backend clients in `packages/contract` — ship per-vertical in SP-1+
- Python backend implementation of `POST /api/v1/auth/token/refresh` — separate Python wave
- Redis `RevocationRepo` implementation — separate Python wave
- Per-backend JWT middleware refactor (Python) — per SD-1 §11 backend checklist, separate wave
- Wiring `packages/auth` into `portal/operator` next-auth config — Plan C
- `packages/ui`, `packages/qa-harness`, `packages/shell` — Plan C
- Reference module `packages/modules/reclaimrx` — Plan D
- Transport header-vs-body test for refresh — Plan C (BFF route handler integration)

---

## Verification Commands + Results

```bash
# From worktree root: packages/contract + packages/auth + packages/scripts
npm run test:packages
# scripts: 10/10, contract: 35/35, auth: 51/51 = 96 total, 0 failing

npm run typecheck
# exit 0

npm run lint:root
# exit 0

npm run manifest:validate
# ✓ operator-dev.yml validates clean

npm run manifest:validate:standalone
# ✓ example-reclaimrx-standalone.yml validates clean
```

### Test breakdown
| Package | Test files | Tests |
|---|---|---|
| @infinityrx/scripts | 1 | 10 |
| @infinityrx/contract | 4 (error-envelope, cache-policy, prescriber-directory, framework-agnostic) | 35 |
| @infinityrx/auth | 7 (claims, crypto, mint-and-verify, refresh-rotation, single-flight, dev-jwt, framework-agnostic) | 51 |
| **Total** | **12** | **96** |

---

## Known Pre-existing Issues (Not Plan B)

- `ifx-operator-portal` (portal/operator) vitest startup fails in the worktree with `Cannot find native binding` for `@rolldown/binding-win32-x64-msvc` — a pre-existing optional-dep worktree issue. `test:packages` scopes explicitly to the three `packages/*` workspaces to avoid this. The CI workflow (`sp0-foundation.yml`) uses `npm run test:packages` which is clean.

---

## Decision

Plan B is complete and ready for Plan C (packages/ui + packages/qa-harness + packages/shell).

Plan C prerequisites met:
- `@infinityrx/contract` public surface stable and exported
- `@infinityrx/auth` full SD-1 TypeScript contract exported
- Framework-agnostic enforcement active in both packages
- CI extended to run all package test suites on every push/PR
