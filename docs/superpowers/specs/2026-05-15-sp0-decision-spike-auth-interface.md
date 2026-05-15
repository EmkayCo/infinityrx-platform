# SP-0 Decision Spike — Auth Interface v4

**Status:** v4 drafted 2026-05-15 incorporating codex pass-3 findings (3 new BLOCK + 3 CONCERN on top of v3). v3 closed all 7 pass-2 findings outright; v4 closes the 3 BLOCKs codex introduced by v3's own fixes (refresh-checks-skipped, contract-test-wrong-code, portal-handling-ambiguous). After v4 ships, any further codex findings fold into the SP-0 spec revision (task #13) and adoption checklist — auth-interface iteration ends here.
**Outcome:** Will fold into SP-0 spec §6.2 when the full decision spike completes.
**Inputs locked by user:**
- D-spike-auth-1: Access TTL = 15 min (matches HIPAA-2026 idle rule)
- D-spike-auth-2: Refresh rotation = rotate-on-use (revoke prior `jti`)
- D-spike-auth-3: `iss` = single constant `"infinityrx"`

## Addresses codex BLOCK #4 from the main spec gate review

> "B12 folds here once tactical fixes land" invites redo. … define a non-negotiable minimal auth interface now: claim names, token issuer/audience, expiry/refresh semantics, cookie/session boundary, dev JWT behavior, and backend validation contract. B12 may implement only an adapter/shim against that interface.

## v3 → v4 changes (codex pass-3 response)

| Pass-3 finding | v4 fix |
|---|---|
| BLOCK: refresh endpoint skipped `auth:revoked:` + `tokens_valid_since` checks (regression v3 introduced) | §8.6: refresh endpoint runs §8 step 9 + §8.5 cutoff check + Redis reachability check BEFORE atomic consume; only `auth:consumed:` already-set maps to `REFRESH_REPLAY`, everything else maps to `REVOKED_TOKEN` / `REVOCATION_CHECK_FAILED` |
| BLOCK: §11 contract test expected `REVOKED_TOKEN` but v3 rotation produces `REFRESH_REPLAY` | §11: rotation test now expects `REFRESH_REPLAY`; added distinct refresh-after-logout, refresh-after-password-reset, refresh-Redis-unreachable tests |
| BLOCK: portal `REFRESH_REPLAY` handling ambiguous; NextAuth Set-Cookie race could overwrite winning refresh | §11 portal: explicit single-flight refresh (coalesce concurrent jwt() invocations by refresh `jti`); `REFRESH_REPLAY` → re-read session or force re-auth, NEVER retry same token; `REVOKED_TOKEN`/`REVOCATION_CHECK_FAILED` → force re-auth without writing stale cookie |
| CONCERN: atomic-consume crash/timeout/unknown-result semantics undocumented | §5 step 2 + §8.5: explicit failure-mode table; unknown consume result → `REVOCATION_CHECK_FAILED`, never mint; Redis durability requirements (AOF, replication) stated |
| CONCERN: inclusive `<=` rejects legitimate same-second post-reset new tokens | §8.5 + §11: mint paths fetch `tokens_valid_since[sub]` and set `iat = max(now, tokens_valid_since[sub] + 1)`; same-second test added |
| CONCERN: contract tests incomplete | §11: added 6 new tests (refresh-after-logout, refresh-after-pw-reset, Redis-unreachable, header-transport, portal single-flight, same-second post-reset) |

## v2 → v3 changes (codex pass-2 response)

| Pass-2 finding | v3 fix |
|---|---|
| BLOCK: refresh rotation raceable (concurrent refreshes both succeed) | §5 step 1 + §8.5 + §8.6: atomic Redis check-and-mark (`SET auth:consumed:<jti> consumed NX EX <ttl>`); loser gets new `REFRESH_REPLAY` (401) |
| BLOCK: `tokens_valid_since` same-second hole | §8.5: inclusive comparison (`iat <= tokens_valid_since[sub]`) |
| BLOCK: refresh endpoint transport (portal sends body, spec says inverse-bearer) | §8.6: refresh sent via `Authorization: Bearer <refresh_jwt>`, body empty; §11 adoption updates `auth.ts:295-321` |
| CONCERN: `env` claim overclaimed | §4: honest wording — `env` is defense-in-depth, NOT cryptographic; per-env secret separation IS the cryptographic defense |
| CONCERN: sliding cookie needs `updateAge: 0` | §6 + §11: explicit `session.updateAge: 0` requirement; without it next-auth renews on `updateAge` intervals (default 24h), not "every request" |
| CONCERN: cookie naming "confirm or document" not contractual | §11: explicit `cookies.sessionToken.name` override adoption item |
| NIT: TTL wording mixes absolute exp + TTL duration | §8.5: `ttl_seconds = (exp - now + 60)` |
| (PARTIAL) B4 env defense overclaimed | folded into the CONCERN above |
| (PARTIAL) C3 revocation correctness holes | folded into the two new BLOCKs above |
| (PARTIAL) C5 sliding-renewal precision | folded into the `updateAge: 0` CONCERN above |

## v1 → v2 changes (codex pass-1 response)

| v1 problem | v2 fix |
|---|---|
| `typ=refresh` could reach protected routes | §8 bearer middleware mandates `typ=access`; refresh route only accepts `typ=refresh`; new error code `WRONG_TOKEN_TYPE` |
| `s.access_token` exposed to client JS via session callback | §6 + §11: session callback returns NO tokens; tokens live only in encrypted JWT payload |
| Rotated refresh token not persisted | §11: refresh endpoint MUST return new refresh + new access; portal jwt callback MUST persist both |
| Dev tokens cryptographically valid against prod backends if secret leaks | §2/§4/§8: `env` claim added; per-environment `JWT_SECRET` enforced; backend rejects on `env` mismatch (`WRONG_ENVIRONMENT`) |
| roles required/optional ambiguity | §8: `roles` required for `typ=access` (may be empty array) |
| Claim-name mismatch with main spec (`scopes`/`module_entitlements` vs `roles`) | §12: reconciliation note — main spec gets updated in task #13 |
| Revocation underspecified | §8.5: shared Redis revocation repo, fail-closed, logout/pw-reset/user-disable semantics, cross-backend consistency |
| §9 MUSTs not mechanically checkable | §9 rewritten with concrete bullets each adapter must satisfy |
| Cookie 8h max-age vs 15-min idle | §6: cookie max-age = 15 min sliding (matches next-auth `session.maxAge`); 8h is refresh TTL inside encrypted JWT, not cookie life |
| "8 failure modes" but 7 codes | §8 now has 9 codes (added `WRONG_TOKEN_TYPE`, `WRONG_ENVIRONMENT`); §11 matches |
| "Three Credentials providers" (four exist) | §1 corrected |
| Dev refresh path uses `typ=access` | §7 explicitly states dev path is access-only; refresh unused in dev |

---

## 1. Ground truth (today)

- **Backend** `shared/auth/jwt_tokens.py`: claims `sub`, `tid`, `roles`, `typ`, `iat`, `exp`, `jti`. HS256. `tid` currently optional. No `iss`/`aud`/`env`.
- **Portal** `portal/shared/lib/auth.ts`: `mintDevJwt` matches backend claim shape; 8h dev expiry; next-auth `session.maxAge = 15*60`. **Four** Credentials providers: `dev-bypass`, `b10-test`, `credentials`, `mfa`.
- **Dev backend path** `shared/auth/dev_trust_jwt.py`: hard-refuses in prod; synthesizes `CurrentUser` without DB lookup.
- **Refresh route**: `POST /api/v1/auth/token/refresh` (core-platform).
- **Seeded admin** `infrastructure/scripts/seed_admin.py`: `DEV_ADMIN_ID`, `DEV_TENANT_ID`.

SP-0's job: **pin the contract, formalize the gaps, don't redesign.**

---

## 2. Access token — claim shape (REQUIRED)

| Claim | Type | Notes |
|---|---|---|
| `sub` | string (UUID) | user_id |
| `tid` | string (UUID) | tenant_id — **tightened from optional → REQUIRED for `typ=access`** |
| `roles` | string[] | required field, may be empty array |
| `typ` | `"access"` | literal |
| `iat` | int (unix seconds) | issued-at |
| `exp` | int (unix seconds) | `iat + 15 minutes` (prod) / `iat + 8h` (dev) |
| `jti` | string (UUID) | unique per token, revocation key |
| `iss` | `"infinityrx"` | **NEW — constant** |
| `aud` | `"infinityrx-backend"` | **NEW — constant** |
| `env` | `"production"` \| `"mock"` \| `"development"` | **NEW — must match the issuing environment's `INFINITYRX_ENV`** |

## 3. Refresh token — claim shape (REQUIRED)

| Claim | Type | Notes |
|---|---|---|
| `sub` | string (UUID) | user_id |
| `typ` | `"refresh"` | literal |
| `iat` | int (unix seconds) | issued-at |
| `exp` | int (unix seconds) | `iat + 8h` |
| `jti` | string (UUID) | unique per token, **rotates on every use** |
| `iss` | `"infinityrx"` | constant |
| `aud` | `"infinityrx-backend"` | constant |
| `env` | `"production"` \| `"mock"` \| `"development"` | matches issuing environment |

No `tid`, no `roles` on refresh.

---

## 4. Crypto

- Algorithm: **HS256** (locked default; `JWT_ALGORITHM` config preserved for future RS256 rotation)
- Secret: **`JWT_SECRET` env var**, ≥32 chars
- **Per-environment, per-instance `JWT_SECRET` is REQUIRED — this is the primary cryptographic defense against cross-environment token reuse.** Each customer instance × each environment (`development`/`mock`/`production`) has a distinct secret.
  - **Startup check (every backend + the portal BFF):** if `JWT_SECRET` equals a hardcoded dev placeholder list (e.g. `"changeme"`, `"dev-secret"`, last-committed value from `.env.example`) → process refuses to start in `INFINITYRX_ENV=production`.
  - **Startup check (every process):** if `INFINITYRX_ENV` is missing, empty, or not in `{development, mock, production}` → process refuses to start.
  - **CI check:** scan `.env.prod` for any `JWT_SECRET` value that appears in `.env.dev` or `.env.mock` → fail the build.
- **The `env` claim (§2/§3) is defense-in-depth, NOT a cryptographic defense.** It catches misconfiguration and accidental cross-environment token reuse: a token already minted with `env="development"` cannot satisfy a prod backend's validator (the backend rejects on `env` mismatch). It does **NOT** defend against an attacker who has the prod `JWT_SECRET` and can sign arbitrary claims — per-environment secret separation (above) is what defends against that. Two layers, deliberately.

## 5. Expiry & refresh semantics

| Setting | Prod | Dev |
|---|---|---|
| Access TTL | **15 min** | 8h |
| Refresh TTL | **8h** | 8h (unused — see §7) |
| Portal cookie max-age | **15 min, sliding** (matches `session.maxAge`) | 15 min, sliding |
| Refresh-token lifetime within the encrypted session payload | 8h (absolute upper bound) | 8h |
| Clock skew tolerance | 30s | 30s |

**Refresh rotation: rotate-on-use, with atomic consume.** Every refresh exchange:
1. Validates incoming refresh: signature, `iss`/`aud`/`env`, `typ=refresh`, exp.
2. **Runs the full revocation suite** (see §8.5): check `auth:revoked:<jti>` → `REVOKED_TOKEN` if present; check `iat <= tokens_valid_since[sub]` → `REVOKED_TOKEN` if true; check Redis reachable → `REVOCATION_CHECK_FAILED` if not.
3. **Atomically marks the `jti` as consumed in Redis**: `SET auth:consumed:<jti> <reason> NX EX <ttl_seconds>`.
   - If the atomic mark **succeeds** (NX wins): proceed to step 4 (mint).
   - If the atomic mark **fails** (key already exists): refresh replay — reject with `REFRESH_REPLAY` (401), do NOT mint. Exactly one of N simultaneous refresh calls wins this race.
   - If the atomic mark **result is unknown** (Redis timeout, connection dropped mid-op): reject with `REVOCATION_CHECK_FAILED` (401). **Never mint with unknown consume state** — the alternative reopens the replay window.
4. Mints a **new** access token + a **new** refresh token (new `jti`s). If mint or response transport fails after a successful consume, the refresh chain is broken and the user must re-login. Acceptable security trade.
5. Returns BOTH new tokens to the portal. Portal MUST persist both (§11).

If a refresh token leaks and the legitimate user refreshes once, the leaked token is dead (OAuth2 BCP). Two concurrent attempts to refresh the same token (e.g., browser tab race) produce exactly one new pair and one `REFRESH_REPLAY` rejection — never two valid forked sessions.

## 6. Cookie / session boundary

- **One cookie:** name `__Secure-infinityrx-session`, attributes `httpOnly`, `Secure`, `SameSite=Lax`, `Path=/`.
- **Cookie max-age = 15 minutes, sliding** (matches next-auth `session.maxAge = 15*60`). After 15 min idle, cookie expires and user must re-login.
- **Sliding renewal requires `session.updateAge: 0` in next-auth config** — without it, next-auth only renews the cookie at `updateAge` intervals (default 24h), which is NOT "sliding on every request." Adoption item in §11 sets this explicitly.
- The cookie wraps the next-auth session payload, **encrypted with `NEXTAUTH_SECRET`** (a separate secret from `JWT_SECRET`).
- The encrypted payload contains: `{ access_token: <JWT>, refresh_token: <JWT>, expires_at: <int>, user_id, tenant_id, roles, mfa_enrolled }`.
- The **8-hour refresh-token lifetime is the inner-JWT lifetime**, not the cookie's. Within a 15-min idle window, the user's session refreshes; after 8h of *continuous activity*, the refresh token itself expires and the user must re-login.
- **The next-auth `session()` callback MUST NOT include `access_token` or `refresh_token` (or any JWT) in its returned session object.** The session object exposed to client-side code (via `useSession()`, `getSession()`, etc.) carries only non-sensitive identity (`user.id`, `user.role`, `user.tenant_id`, `mfa_enrolled`, error flag) — never raw tokens.
- BFF reads tokens from the *server-side* encrypted session payload (via the `auth()` wrapper on route handlers / server components). BFF → backend: `Authorization: Bearer <access_jwt>`.

## 7. Dev JWT behavior

Dev-bypass exists for two reasons: the core-platform auth path uses a SQLite shim in dev (not the live Postgres `core` schema), and tests need to mint valid backend-accepted JWTs without a real login flow.

**Gating (both ends must agree):**
- Portal: `NODE_ENV !== "production"` **AND** `DEV_AUTH_BYPASS === "true"`
- Backend: `INFINITYRX_ENV !== "production"` (refuses to wire `configure_auth_trust_jwt` in prod)

**Dev JWT claim shape: identical schema to prod**, with the values that distinguish a dev token:
- `env = "development"` (or `"mock"` per environment) — this is the cryptographic tripwire; prod backend (with `INFINITYRX_ENV=production`) rejects any token with `env != "production"` regardless of secret.
- `exp = iat + 8h` instead of 15 min (ergonomics).
- `sub = DEV_ADMIN_ID`, `tid = DEV_TENANT_ID` (seeded admin from `seed_admin.py`).
- `roles = ["platform_admin"]` (dev grants admin).
- Backend skips DB user-lookup (`configure_auth_trust_jwt` synthesizes a `CurrentUser`).

**Dev refresh is unused.** The dev path mints a single `typ=access` token with 8h TTL — longer than any dev session — so the refresh exchange is never exercised. The current code's "refresh_token" slot stores another `typ=access` token (legacy artifact). v2 contract: the dev `refresh_token` field is either omitted from the session payload or explicitly typed as a non-token marker. **Dev path may not call `/api/v1/auth/token/refresh`.**

**b10-test path** (B10 wave mechanism): same gating principle, distinct env var (`B10_TEST_MODE` + `B10_TEST_TOKEN`), same claim shape including `env`. B12 S3 implements against this contract.

## 8. Backend validation contract (every FastAPI service implements identically)

Every backend has the same JWT middleware. The contract — checked in this order:

| # | Check | Failure | HTTP | Error code |
|---|---|---|---|---|
| 1 | `Authorization: Bearer <token>` header present | missing | 401 | `MISSING_BEARER` |
| 2 | Signature verifies against `JWT_SECRET` (HS256) | mismatch | 401 | `INVALID_TOKEN` |
| 3 | Required claims present: `exp`, `iat`, `sub`, `typ`, `jti`, `iss`, `aud`, `env`. For `typ=access`: also `tid`, `roles` | missing | 401 | `MALFORMED_TOKEN` |
| 4 | `iss == "infinityrx"` | mismatch | 401 | `WRONG_ISSUER` |
| 5 | `aud == "infinityrx-backend"` | mismatch | 401 | `WRONG_AUDIENCE` |
| 6 | `env == backend's INFINITYRX_ENV` | mismatch | 401 | `WRONG_ENVIRONMENT` |
| 7 | `typ == "access"` (for protected routes; the `/auth/token/refresh` endpoint inverts this — see §8.6) | mismatch | 401 | `WRONG_TOKEN_TYPE` |
| 8 | `exp > now() - 30s` | expired | 401 | `EXPIRED_TOKEN` |
| 9 | `jti` not in revocation repo (§8.5) | revoked | 401 | `REVOKED_TOKEN` |

On success (for `typ=access`):
- Pull `tid` into request-scoped tenant context (`shared.db.tenant_context.set_tenant`).
- Pull `sub` into request-scoped user context.
- Pull `roles` into request-scoped authz context.

**Errors NEVER expose** PyJWT internal messages. Every failure surfaces as the project's structured error envelope `{error:{code, message, correlation_id}}` with `code` from the table above. The `message` is fixed per code (no leak of which jti or which claim). If revocation-repo unreachable (Redis down), fail closed with `REVOCATION_CHECK_FAILED` (401) — never silently allow.

### 8.5 Revocation repo

- **Shared single source of truth per instance:** Redis-backed, two key families:
  - `auth:revoked:<jti>` — for access tokens revoked via logout/admin action. Value = revocation reason + timestamp.
  - `auth:consumed:<jti>` — for refresh tokens atomically consumed during rotation (§5). Set via `SET … NX EX …`; success means "this caller consumed it", failure means replay.
- **Cross-backend consistency:** every backend reads from the *same* Redis instance. A revocation written by core-platform is immediately visible to billing, reclaimrx, etc.
- **Fail-closed:** if Redis is unreachable, backends reject all tokens with `REVOCATION_CHECK_FAILED` (401). No "best-effort allow" — HIPAA + the spec's project rules forbid silent skip.
- **Logout:** portal calls `POST /api/v1/auth/logout` with current access token (`Authorization: Bearer <access_jwt>`). Core-platform extracts both access `jti` and refresh `jti` (from the next-auth session payload, server-side) and writes both to `auth:revoked:` with reason `logout`.
- **Password reset / user-disabled:** rather than enumerate every outstanding `jti`, core-platform writes a per-user timestamp key: `auth:tokens_valid_since:<user_id>` = `<unix_ts>`. Every backend checks: if a token's `iat <= tokens_valid_since[sub]` → reject with `REVOKED_TOKEN`. **The comparison is inclusive (`<=`)** to close the same-second hole (a token minted in the same second as the reset/disable event is rejected).
- **Post-reset mint protection:** to avoid auto-rejecting a legitimate login that happens in the same second as a just-completed reset, mint paths fetch `tokens_valid_since[sub]` at issuance time and set `iat = max(now, tokens_valid_since[sub] + 1)`. The new token's `iat` is therefore strictly greater than the cutoff, so the inclusive `<=` check passes.
- **TTL on revocation entries:** `ttl_seconds = (exp - now) + 60` — entries auto-expire at the same wall-clock moment the token itself would have expired, plus a 60s skew margin. Avoids unbounded Redis growth.
- **Redis durability:** the Redis instance backing `auth:revoked:`, `auth:consumed:`, `auth:tokens_valid_since:` MUST be configured with AOF persistence (`appendonly yes`, `appendfsync everysec` minimum). Loss of consumed/revoked writes after acknowledged success would reopen replay windows. Replication (Redis Sentinel / Redis Enterprise) recommended for production. Backends treat any Redis unreachability as fail-closed (`REVOCATION_CHECK_FAILED`), per the rule above.

### 8.6 The refresh endpoint

`POST /api/v1/auth/token/refresh` is the **only** endpoint that accepts `typ=refresh`. Its bearer middleware is the inverse: rejects `typ != refresh` with `WRONG_TOKEN_TYPE`.

**Transport: the refresh token is sent in the `Authorization: Bearer <refresh_jwt>` header, NOT in the request body.** This is consistent with every other authenticated route — refresh is just a normal Bearer-authenticated POST that happens to require `typ=refresh` instead of `typ=access`. The request body is empty (or carries non-token fields if needed, e.g., a `device_id` for future device-binding).

The refresh endpoint performs the §8 validation table with **two substitutions** and then runs the §5 rotation logic:
1. Steps 1-6 of §8 (signature, required claims, `iss`, `aud`, `env`).
2. Step 7 is replaced: require `typ == "refresh"` (the inverse of the protected-route rule). `typ != refresh` → `WRONG_TOKEN_TYPE` (401).
3. Step 8 of §8 (`exp` not in past).
4. **Step 9 still runs** — check `auth:revoked:<jti>` → `REVOKED_TOKEN` if present. (Logout / admin revoke must still bite refresh tokens.)
5. **Additional check from §8.5** — `iat <= tokens_valid_since[sub]` → `REVOKED_TOKEN`. (Password reset / user-disable must bite refresh tokens.)
6. **Redis reachability check** — if Redis is unreachable, return `REVOCATION_CHECK_FAILED` (401). No silent skip.
7. **Only after all six pass:** run §5 step 3's atomic consume. `auth:consumed:<jti>` already-set → `REFRESH_REPLAY` (401). Unknown result → `REVOCATION_CHECK_FAILED`.
8. Mint new pair, return both via response body.

**`REFRESH_REPLAY` is distinct from `REVOKED_TOKEN`.** Replay means a race or duplicate (this same refresh was already consumed by a sibling call); revoked means the session was deliberately killed (logout, password reset, user disable). The portal handles them differently — see §11.

## 9. What B12's adapter MUST and MUST NOT do

B12 S1 (`_shim/auth` refactor across 7 sub-routers) and B12 S3 (`b10-test` JWT minting + `mintDevJwt` dedup) implement *adapters against this contract*.

**B12 MUST:**
- Produce / accept JWTs in the exact claim shape of §2/§3 — including `iss`, `aud`, `env`.
- Use `JWT_SECRET` for sign/verify, no other secret.
- Honor the prod-refusal gates for dev paths (§7).
- Route ALL dev mint operations through a single `mintDevJwt` function (consolidate the four call sites in `portal/shared/lib/auth.ts:95, 96, 159, 160`).
- Produce identical claim shape from the `credentials`-provider short-circuit at `auth.ts:151-173` (currently a hand-rolled path).
- Surface errors via the structured envelope (§8), never raw exceptions.
- Reject `typ != access` at all bearer middleware in protected route mounts.
- Persist the rotated `refresh_token` in the portal's `jwt()` callback (§11).
- Remove `access_token`/`refresh_token` from the next-auth `session()` callback's returned object (§11).

**B12 MUST NOT:**
- Add new claims not in §2/§3.
- Change `iss`/`aud`/`env` values from §2.
- Bypass `jti` revocation checks (§8.5).
- Use a different algorithm than HS256 without an explicit SP-0 spec amendment.
- Skip the §8 required-claim validation list.
- Allow a single `JWT_SECRET` shared across environments (§4 startup check enforces this).

If B12 lands with deviations from this contract, SP-0's `packages/auth` implementation rejects them — B12 fixes its adapter, SP-0 does not absorb the deviation.

## 10. Out of v1 (deferred — tracked)

- **`module_entitlements` claim** — not in v1. The dedicated-per-customer-instance model + build-time composition (deployment manifest + tree-shaking, spike step 4) determines "what's deployed." Within a customer's instance, all available modules are accessible subject to `roles`-based authz. Add this claim only if sub-tenant feature flags become real.
- **`mfa_verified` claim** — not in v1. MFA-required tenants gate the *issuance* of any access token (existing `mfa_required: true` → `mfa_challenge_token` → `/auth/mfa/verify` flow). A token's existence implies post-MFA. Add only if route-level "this specific action requires fresh MFA" appears.
- **Per-instance `iss`** — not in v1. Per-instance `JWT_SECRET` provides cross-instance isolation cryptographically; the `env` claim provides cross-environment isolation. Per-instance `iss` would only duplicate the audit signal that the instance's deployment tag already captures.
- **Asymmetric crypto (RS256)** — not in v1. Symmetric HS256 fits the dedicated-instance model. Revisit if multi-region or a non-backend audience (mobile native, third-party integrations) appears.
- **Scope-claim model (`scopes: string[]`)** — not in v1. `roles` is the current authz dimension; finer-grained scopes can be derived from roles in code today. Promote to a JWT claim only if scope-based authz becomes load-bearing.

---

## 11. Adoption checklist (concrete tasks for the SP-0 plan)

### Backend (Python — `shared/auth/jwt_tokens.py`, every backend's middleware)
- [ ] Add `iss`, `aud`, `env` to `create_access_token` and `create_refresh_token` payloads.
- [ ] Tighten `tid` from optional → required for access tokens in `decode_token`'s `options={"require": [...]}`.
- [ ] Tighten `roles` from optional → required for access tokens (non-null list).
- [ ] Add `iss`/`aud`/`env` validation in `decode_token` — fail with `WRONG_ISSUER`/`WRONG_AUDIENCE`/`WRONG_ENVIRONMENT`.
- [ ] Add `typ` enforcement in protected-route bearer middleware (`typ=access` required); refresh endpoint inverts (`typ=refresh` required).
- [ ] New error code `WRONG_TOKEN_TYPE` + `WRONG_ENVIRONMENT` + `REVOCATION_CHECK_FAILED` in the error envelope codes.
- [ ] Implement refresh rotation in `POST /api/v1/auth/token/refresh`: revoke incoming `jti`, mint new access + new refresh, return both.
- [ ] Implement shared Redis revocation repo (§8.5): `auth:revoked:<jti>` keys, `auth:tokens_valid_since:<user_id>` keys, fail-closed on Redis unreachable.
- [ ] Implement `POST /api/v1/auth/logout` writing both jtis to revocation repo.
- [ ] On password reset / user-status → inactive: write `tokens_valid_since:<user_id>`.
- [ ] Backend bearer middleware enforces the `tokens_valid_since` rule: reject tokens where `iat <= tokens_valid_since[sub]` with `REVOKED_TOKEN` (per-request Redis read; cache short). Acceptance requires strict `iat > tokens_valid_since[sub]`, matching the §8.5 rejection rule.
- [ ] Startup check: refuse to boot with `INFINITYRX_ENV=production` if `JWT_SECRET` equals a dev placeholder.
- [ ] Startup check: refuse to boot if `INFINITYRX_ENV` is missing, empty, or not in `{development, mock, production}`.
- [ ] Refresh endpoint reads incoming refresh token from `Authorization: Bearer` header, not request body.
- [ ] Refresh endpoint runs full revocation suite (steps 4-6 of §8.6) BEFORE atomic consume: `auth:revoked:<jti>` check, `tokens_valid_since[sub]` cutoff, Redis reachability. Only after all three pass does atomic-consume run.
- [ ] Refresh endpoint uses atomic consume: `SET auth:consumed:<jti> <reason> NX EX <ttl>`. On `NX` failure → `REFRESH_REPLAY` (401). On unknown result (Redis timeout mid-op) → `REVOCATION_CHECK_FAILED` (401). Never proceed to mint on either failure mode.
- [ ] All mint paths (login, refresh) fetch `tokens_valid_since[sub]` at issuance and set `iat = max(now, tokens_valid_since[sub] + 1)`, so post-reset same-second logins are not auto-rejected.
- [ ] `tokens_valid_since` comparison uses `<=` (inclusive), not `<`, on second-precision `iat`.
- [ ] Revocation entry TTL set to `(exp - now + 60)` seconds at insert time.
- [ ] Redis persistence configured: AOF (`appendonly yes`, `appendfsync everysec`); replication recommended for prod.
- [ ] Two new error codes wired: `REFRESH_REPLAY` (refresh endpoint only), `REVOCATION_CHECK_FAILED` (Redis unreachable, all routes).

### Portal (TypeScript — `portal/shared/lib/auth.ts`, the BFF, next-auth config)
- [ ] Add `iss`, `aud`, `env` to `mintDevJwt`'s `SignJWT` payload.
- [ ] Consolidate all four dev-mint sites (`auth.ts:95-96, 159-160`) into a single `mintDevJwt` call path.
- [ ] Remove `s.access_token` and `s.refresh_token` from the `session()` callback's returned object (`auth.ts:325-345`). The session exposes only non-sensitive identity; tokens stay in the encrypted JWT payload, server-readable only.
- [ ] Update the `jwt()` callback's refresh logic (`auth.ts:295-321`) to persist BOTH new tokens returned by `/api/v1/auth/token/refresh`, not just `access_token`.
- [ ] Set next-auth `cookies.sessionToken.name` to `__Secure-infinityrx-session` via the `cookies` config block — the cookie name is contractual, not auto-generated.
- [ ] Set next-auth `session.updateAge: 0` so the cookie max-age renews on every authenticated request (current config sets `maxAge` only; without `updateAge: 0` next-auth uses its 24h default and the cookie is not actually sliding).
- [ ] Update `jwt()` callback's refresh logic (`auth.ts:295-321`) to send the refresh token via `Authorization: Bearer <refresh_jwt>` header — remove the `{refresh_token}` body.
- [ ] Implement **single-flight refresh** at the jwt() callback: concurrent invocations of jwt() that detect access expiry MUST coalesce on one in-flight Promise keyed by the current refresh `jti`. Same-tab and cross-tab refresh attempts share one POST. No coalescing → both consume attempts race, one wins atomically, the loser gets `REFRESH_REPLAY` and the user sees a spurious logout.
- [ ] Refresh-error handling, precise mapping:
  - `REFRESH_REPLAY` → **do NOT retry with the same refresh token** (atomic consume guarantees it's permanently dead). Either: (a) re-read the next-auth session via `getSession()` to pick up the winning sibling's updated tokens, or (b) force re-auth. Whichever path, **do not write a stale session cookie** — a losing replay response that overwrites a winning sibling's `Set-Cookie` produces a wrong-but-valid session.
  - `REVOKED_TOKEN` → force re-auth (clear session, redirect to /login). Do not write a stale cookie.
  - `REVOCATION_CHECK_FAILED` → force re-auth (Redis state unknown, safer to re-establish).
  - `EXPIRED_TOKEN` (on refresh) → force re-auth.
- [ ] Remove or explicitly mark-unused the `refresh_token` field in dev-bypass + credentials-shortcut return values (`auth.ts:96, 160`).
- [ ] CI check: `.env.prod`'s `JWT_SECRET` must not appear in `.env.dev`, `.env.mock`, or `.env.example`.

### Contract tests (in `packages/auth/tests/`)
- [ ] One contract test per failure-mode in §8 — verify every backend's middleware rejects with the right error code for each of the 9 modes.
- [ ] Refresh-rotation test (sequential): refresh once → succeeds, returns new pair. Then attempt refresh again with the now-consumed old refresh jwt → verify **`REFRESH_REPLAY`** (it lives in `auth:consumed:`, not `auth:revoked:`).
- [ ] Refresh-after-logout test: refresh once → logout → attempt refresh with the now-revoked refresh jwt → verify **`REVOKED_TOKEN`** (distinct path: `auth:revoked:` was written by logout).
- [ ] Refresh-after-password-reset test: mint refresh at T → write `tokens_valid_since[sub] = T` → attempt refresh → verify **`REVOKED_TOKEN`** via the `tokens_valid_since` path.
- [ ] Refresh-Redis-unreachable test: kill Redis → attempt refresh → verify **`REVOCATION_CHECK_FAILED`** (401), no token minted, no consume marker leaked.
- [ ] Refresh-race test: fire N concurrent refresh calls with the same incoming refresh token (use the atomic SET-NX semantics); verify exactly one succeeds, the other N-1 return `REFRESH_REPLAY` (401), and no two simultaneously-valid forked refresh chains exist.
- [ ] Refresh-transport test: POST `/api/v1/auth/token/refresh` with refresh token in body (no `Authorization` header) → verify `MISSING_BEARER` (401).
- [ ] Logout test (access tokens): logout → attempt protected request with old access token → verify `REVOKED_TOKEN`.
- [ ] Password-reset test (access tokens): reset → attempt protected request with pre-reset access token → verify `REVOKED_TOKEN` via `tokens_valid_since`.
- [ ] Same-second post-reset mint test: write `tokens_valid_since[sub] = T`, immediately mint a new access token at second T → verify `iat == T+1` (not T) and the token is accepted by the validator.
- [ ] `tokens_valid_since` same-second test: mint a token with explicit `iat = T`, write `tokens_valid_since[sub] = T`, verify the token is rejected with `REVOKED_TOKEN` (inclusive `<=` comparison).
- [ ] Dev/prod isolation test: mint a token with `env="development"`, attempt against a backend with `INFINITYRX_ENV=production`, verify `WRONG_ENVIRONMENT` (regardless of whether secrets happen to match).
- [ ] Sliding cookie test: with `session.updateAge: 0` set, verify the next-auth cookie's `Max-Age` advances on every authenticated request.
- [ ] Portal single-flight test: trigger two concurrent client-side requests that both need refresh; verify only one POST to `/api/v1/auth/token/refresh` fires, both callers receive the same new tokens.

---

## 12. Reconciliation with main SP-0 spec (task #13 input)

The main SP-0 spec (`docs/superpowers/specs/2026-05-14-sp0-integration-foundation-design.md`) currently references `{tenantId, userId, scopes, moduleEntitlements}` in §6.2 and §7.1. This auth interface is **authoritative**:

- "scopes" in the main spec → **`roles`** (this draft).
- "module_entitlements" → **out of v1** per §10. The main spec must be updated to say module availability is determined by the deployment manifest, not by a JWT claim.

Task #13 (SP-0 spec revision) must update main spec §6.2, §7.1, §7.2 to align with this draft.
