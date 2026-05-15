import { mintTokenPair, type MintedTokens } from "./mint.js";
import { verifyRefreshToken } from "./verify.js";
import { AuthError, AUTH_ERROR_MESSAGES } from "./errors.js";
import type { EnvClaim } from "./env-claim.js";
import type { RevocationRepo } from "./revocation-repo.js";

const CONSUMED_TTL_SECONDS = 8 * 60 * 60 + 60; // refresh TTL + 60s skew margin per SD-1 §8.5

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
  } catch {
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
