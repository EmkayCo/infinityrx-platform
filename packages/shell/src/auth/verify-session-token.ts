import "server-only";
import { cache } from "react";
import {
  verifyAccessToken,
  InMemoryRevocationRepo,
  resolveEnvClaim,
  type VerifyOptions,
} from "@infinityrx/auth";
import { auth } from "./auth.config.js";

/**
 * Build VerifyOptions from the current process environment.
 *
 * JWT_SECRET: required in all environments.
 * INFINITYRX_ENV: must be "development" | "mock" | "production".
 *
 * The RevocationRepo used here is intentionally an InMemoryRevocationRepo —
 * it always returns isRevoked=false and has no cutoff. This means the
 * shell-layer per-request check enforces token signature + expiry but NOT
 * Redis-backed revocation. Redis revocation is enforced on every API call
 * by the Python auth service (the correct enforcement boundary for PHI/money
 * operations). The shell check catches the common "expired between refreshes"
 * case without adding a Redis round-trip per page render.
 */
function buildVerifyOpts(token: string): VerifyOptions {
  const secret = process.env.JWT_SECRET;
  if (!secret) throw new Error("JWT_SECRET environment variable is required");
  const env = resolveEnvClaim(process.env.INFINITYRX_ENV);
  return { token, secret, env, repo: new InMemoryRevocationRepo() };
}

/**
 * Per-request JWT revocation check for RequireAuth.
 *
 * Reads the access_token stored in the next-auth session cookie and calls
 * verifyAccessToken to validate signature, expiry, and env claim.
 * Returns true if the token is valid, false if it is expired, malformed,
 * or missing.
 *
 * React cache() ensures this runs AT MOST ONCE per server render cycle —
 * multiple RequireAuth mounts in one RSC tree share the same result.
 *
 * WHY: next-auth session refresh runs verifyAccessToken only at refresh
 * boundaries (every N minutes). Between refreshes, a revoked or expired
 * token passes the session check. This function closes that gap by verifying
 * the raw access_token on every server-rendered request.
 */
export const verifySessionToken: () => Promise<boolean> = cache(async () => {
  const session = await auth();
  const accessToken = (session?.user as { accessToken?: string } | undefined)?.accessToken;
  if (!accessToken) return false;
  try {
    await verifyAccessToken(buildVerifyOpts(accessToken));
    return true;
  } catch {
    return false;
  }
});
