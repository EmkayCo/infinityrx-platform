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
