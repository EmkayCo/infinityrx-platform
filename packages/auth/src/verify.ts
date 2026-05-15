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
